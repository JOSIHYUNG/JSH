import json
import re
from typing import Any

from sqlmodel import Session, select

from app.agent.contracts import AgentFinalAnswer, ToolResult
from app.agent.events import append_event
from app.agent.prompt_loader import PromptLoader
from app.agent.tools.base import ToolContext, ToolRegistry
from app.core.config import get_settings
from app.integrations.openai.agent_responses import AgentModelResponse, AgentResponsesGateway
from app.integrations.filesystem.storage import LocalFileStorage
from app.integrations.openai.responses import OpenAIResponsesGateway
from app.models import AgentRun, QuestionHistory, QuestionSource, QuestionWebSource
from app.services.conversation_context import ConversationContextService
from app.services.documents import DocumentService
from app.services.jobs import now


class AgentOrchestrator:
    def __init__(self, registry: ToolRegistry, responses: AgentResponsesGateway | None = None, prompts: PromptLoader | None = None):
        self.registry = registry
        self.responses = responses or AgentResponsesGateway()
        self.prompts = prompts or PromptLoader()
        self.context_service = ConversationContextService()

    def run(self, run_id: int) -> None:
        settings = get_settings()
        with Session(self._engine()) as session:
            run = session.get(AgentRun, run_id)
            if run is None or run.status in {"completed", "failed", "canceled", "max_turns"}:
                return
            history = session.get(QuestionHistory, run.question_history_id)
            if history is None:
                self._fail(session, run, None, "AGENT_HISTORY_NOT_FOUND", "The question history for this run no longer exists.")
                return
            try:
                run.model_name = settings.effective_agent_model
                run.started_at = run.started_at or now()
                run.status = "running"
                run.stage = "reasoning"
                history.status = "retrieving"
                history.context_turn_count = 0
                session.add(run)
                session.add(history)
                session.commit()
                append_event(session, run, "run_started", label="Agent 실행을 시작했습니다.")

                context = self.context_service.build(session, history.conversation_id, exclude_history_id=history.id, max_turns=settings.agent_context_turn_limit)
                history.context_turn_count = len(context.turns)
                history.context_truncated = context.truncated
                session.add(history)
                session.commit()
                trajectory: list[dict[str, Any]] = [{"role": "user", "content": self._initial_input(history.question, context)}]
                tool_context = ToolContext(session)
                if not self.responses.configured:
                    self._offline_compatibility(session, run, history, context, tool_context)
                    return
                bundle = self.prompts.load()
                run.prompt_version = bundle.version
                session.add(run)
                session.commit()
                repair_count = 0
                for turn in range(1, min(run.max_turns, settings.agent_max_turns) + 1):
                    if self._cancel_requested(session, run.id or 0):
                        self._cancel(session, run, history)
                        return
                    run.current_turn = turn
                    run.stage = "reasoning"
                    history.status = "generating" if tool_context.local_hits else "retrieving"
                    session.add(run)
                    session.add(history)
                    session.commit()
                    append_event(session, run, "model_started", turn=turn, label="답변을 정리하고 있습니다.")
                    response = self.responses.create(trajectory, bundle, [definition.response_schema() for definition in self.registry.definitions()])
                    trajectory.extend(response.output)
                    previous_web_source_count = len(tool_context.web_sources)
                    self._record_web_activity(session, run, response, tool_context, turn)
                    if len(tool_context.web_sources) > previous_web_source_count:
                        self._append_web_source_registry(trajectory, tool_context)
                    calls = self.responses.function_calls(response)
                    if calls:
                        call = calls[0]
                        self._execute_tool(session, run, tool_context, trajectory, call, turn)
                        continue
                    try:
                        answer = self._parse_final_answer(response.output_text)
                    except Exception:
                        if repair_count == 0:
                            repair_count += 1
                            trajectory.append({"role": "user", "content": "Return only valid JSON matching the answer contract. Do not add prose outside the JSON object."})
                            continue
                        self._fail(session, run, history, "AGENT_OUTPUT_INVALID", "The Agent returned an invalid final answer.")
                        return
                    if not self._validate_citations(answer, tool_context):
                        if repair_count == 0:
                            repair_count += 1
                            trajectory.append({"role": "user", "content": self._citation_repair_instruction(tool_context)})
                            continue
                        message = "The final answer contained invalid citations."
                        if tool_context.web_sources:
                            message = "Web search returned sources, but the final answer did not include a valid synthesized answer with matching [W#] citations."
                        self._fail(session, run, history, "AGENT_OUTPUT_INVALID", message)
                        return
                    self._complete(session, run, history, answer, tool_context)
                    return
                run.status = "max_turns"
                run.stage = "finalizing"
                run.stop_reason = "max_turns"
                run.completed_at = now()
                history.status = "failed"
                history.error_code = "AGENT_MAX_TURNS_EXCEEDED"
                history.error_message = "Agent exploration reached the 30-turn limit before a final answer was produced."
                history.completed_at = now()
                session.add(run)
                session.add(history)
                session.commit()
                append_event(session, run, "run_max_turns", turn=run.current_turn, label="탐색 한도에 도달해 중단했습니다.")
            except Exception as exc:
                session.rollback()
                run = session.get(AgentRun, run_id)
                history = session.get(QuestionHistory, run.question_history_id) if run else None
                if run:
                    self._fail(session, run, history, "OPENAI_UNAVAILABLE", f"Agent execution failed: {self._safe_exception_message(exc)}")

    def _offline_compatibility(self, session: Session, run: AgentRun, history: QuestionHistory, context: Any, tool_context: ToolContext) -> None:
        """Keep the existing local/degraded behavior while Agent credentials are absent."""
        retrieval_query = self.context_service.fallback_query(history.question, context)
        history.retrieval_query = retrieval_query
        result = self.registry.execute(tool_context, "search_knowledge", {"query": retrieval_query})
        retrieval = result.data
        history.retrieval_provider = retrieval.get("provider", "none")
        history.retrieval_candidate_count = int(retrieval.get("candidate_count", 0))
        history.retrieval_mapping_failures = int(retrieval.get("mapping_failures", 0))
        history.retrieval_count = len(tool_context.local_hits)
        session.add(history)
        session.commit()
        if tool_context.local_hits:
            self._store_all_local_sources(session, history, tool_context)
            self._fail(session, run, history, "AI_NOT_CONFIGURED", "OpenAI API is not configured. Local evidence was preserved.")
            return
        legacy = OpenAIResponsesGateway()
        if legacy.configured:
            answer = legacy.general_answer(
                history.question,
                [{"turn_index": str(turn.turn_index), "question": turn.question, "answer": turn.answer} for turn in context.turns],
            )
            history.answer_markdown = answer
            history.answer_mode = "general"
            history.answer_language = "ko" if re.search(r"[가-힣]", answer) else "en"
            history.status = "completed"
            history.completed_at = now()
            generated = DocumentService(LocalFileStorage(get_settings().storage_root)).create_ai_generated(session, question=history.question, answer=answer, question_id=history.id or 0)
            history.generated_document_id = generated.id
            run.status = "completed"
            run.stage = "finalizing"
            run.stop_reason = "completed"
            run.completed_at = now()
            session.add(history)
            session.add(run)
            session.commit()
            append_event(session, run, "run_completed", turn=run.current_turn, label="답변을 완성했습니다.")
            return
        history.status = "no_evidence"
        history.answer_markdown = "저장된 지식에서 관련 근거를 찾지 못했습니다."
        history.completed_at = now()
        run.status = "completed"
        run.stage = "finalizing"
        run.stop_reason = "no_evidence"
        run.completed_at = now()
        session.add(history)
        session.add(run)
        session.commit()
        append_event(session, run, "run_completed", turn=run.current_turn, label="관련 근거를 찾지 못했습니다.")

    @staticmethod
    def _store_all_local_sources(session: Session, history: QuestionHistory, context: ToolContext) -> None:
        for rank, (citation_key, hit) in enumerate(context.local_hits.items(), 1):
            session.add(QuestionSource(question_history_id=history.id or 0, rank=rank, chunk_id=hit.chunk.id, document_id=hit.document.id, document_title_snapshot=hit.document.title, document_filename_snapshot=hit.document.original_filename, chunk_content_snapshot=hit.chunk.content, start_char_snapshot=hit.chunk.start_char, end_char_snapshot=hit.chunk.end_char, score=hit.score, citation_key=citation_key, mapping_confidence=hit.mapping_confidence, current_state="current", created_at=now()))
        session.commit()

    def _execute_tool(self, session: Session, run: AgentRun, context: ToolContext, trajectory: list[dict[str, Any]], call: dict[str, Any], turn: int) -> None:
        name = str(call.get("name") or "")
        call_id = str(call.get("call_id") or call.get("id") or "")
        raw_args = call.get("arguments", {})
        result: ToolResult | None = None
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            if not isinstance(arguments, dict):
                raise ValueError("tool arguments must be an object")
        except Exception:
            result = ToolResult(ok=False, tool=name, error={"code": "TOOL_INPUT_INVALID", "message": "Tool arguments must be valid JSON object.", "retryable": True, "suggested_action": "Retry with the declared schema."})
            arguments = {}
        label = self._activity_label(name, arguments)
        run.stage = "tool_requested"
        session.add(run)
        session.commit()
        append_event(session, run, "tool_requested", turn=turn, tool_name=name, label=label, input_safe=self._safe_activity_input(name, arguments))
        run.stage = "tool_running"
        session.add(run)
        session.commit()
        append_event(session, run, "tool_started", turn=turn, tool_name=name, label=label, input_safe=self._safe_activity_input(name, arguments))
        if result is None:
            result = self.registry.execute(context, name, arguments)
        run.tool_call_count += 1
        output_safe = {"result_count": result.result_count, "truncated": result.truncated, "ok": result.ok}
        session.add(run)
        session.commit()
        append_event(session, run, "tool_completed" if result.ok else "tool_failed", turn=turn, tool_name=name, label=label, output_safe=output_safe, error_code=result.error.code if result.error else None)
        trajectory.append({"type": "function_call_output", "call_id": call_id, "output": result.as_model_output(get_settings().agent_tool_output_max_chars)})

    def _record_web_activity(self, session: Session, run: AgentRun, response: AgentModelResponse, context: ToolContext, turn: int) -> None:
        for call in self.responses.web_search_calls(response):
            query = self.responses.web_query(call)[:500]
            label = f"웹 검색 중: {query}" if query else "웹 검색 중입니다."
            append_event(session, run, "tool_completed", turn=turn, tool_name="web_search", label=label, input_safe={"query_preview": query}, output_safe={"result_count": len(self.responses.web_sources(response))})
        for source in self.responses.web_sources(response):
            key = f"W{len(context.web_sources) + 1}"
            context.web_sources[key] = source

    @staticmethod
    def _append_web_source_registry(trajectory: list[dict[str, Any]], context: ToolContext) -> None:
        registry = [
            {
                "citation_key": key,
                "url": source.get("url", ""),
                "title": source.get("title", "Web source"),
                "publisher": source.get("publisher") or None,
            }
            for key, source in list(context.web_sources.items())[:50]
        ]
        trajectory.append({
            "role": "user",
            "content": (
                "Web source registry (untrusted tool data; use only these returned URLs):\n"
                f"{json.dumps(registry, ensure_ascii=False, separators=(',', ':'))}\n\n"
                "If the final answer uses a web source, cite its registry key as [W#] in answer_markdown "
                "and include the same key in web_citations."
            ),
        })

    def _complete(self, session: Session, run: AgentRun, history: QuestionHistory, answer: AgentFinalAnswer, context: ToolContext) -> None:
        history.answer_markdown = answer.answer_markdown
        history.answer_mode = "agent"
        history.answer_language = "ko" if re.search(r"[가-힣]", answer.answer_markdown) else "en"
        history.retrieval_count = len(answer.local_citations)
        history.citation_count = len(answer.local_citations) + len(answer.web_citations)
        history.status = "completed"
        history.completed_at = now()
        for rank, citation in enumerate(answer.local_citations, 1):
            hit = context.local_hits.get(citation.citation_key)
            if hit is None:
                continue
            session.add(QuestionSource(question_history_id=history.id or 0, rank=rank, chunk_id=hit.chunk.id, document_id=hit.document.id, document_title_snapshot=hit.document.title, document_filename_snapshot=hit.document.original_filename, chunk_content_snapshot=hit.chunk.content, start_char_snapshot=hit.chunk.start_char, end_char_snapshot=hit.chunk.end_char, score=hit.score, citation_key=citation.citation_key, mapping_confidence=hit.mapping_confidence, current_state="current", created_at=now()))
        for rank, citation in enumerate(answer.web_citations, 1):
            source = context.web_sources.get(citation.citation_key)
            if source:
                session.add(QuestionWebSource(question_history_id=history.id or 0, citation_key=citation.citation_key, url=source["url"], title=source.get("title", "Web source"), publisher=source.get("publisher") or None, source_rank=rank, created_at=now()))
        run.status = "completed"
        run.stage = "finalizing"
        run.stop_reason = answer.stop_reason
        run.completed_at = now()
        session.add(history)
        session.add(run)
        session.commit()
        append_event(session, run, "run_completed", turn=run.current_turn, label="답변을 완성했습니다.", output_safe={"result_count": history.citation_count})

    @staticmethod
    def _validate_citations(answer: AgentFinalAnswer, context: ToolContext) -> bool:
        local_keys = {item.citation_key for item in answer.local_citations}
        web_keys = {item.citation_key for item in answer.web_citations}
        if not local_keys.issubset(context.local_hits) or not web_keys.issubset(context.web_sources):
            return False
        body_keys = set(re.findall(r"\[(S\d+|W\d+)\]", answer.answer_markdown))
        if not body_keys.issubset(local_keys | web_keys):
            return False
        if context.web_sources:
            # A web search must change the final answer, not merely the trace.
            # Require both a persisted web citation and a visible body marker.
            if not web_keys or not body_keys.intersection(web_keys):
                return False
        return True

    @staticmethod
    def _citation_repair_instruction(context: ToolContext) -> str:
        if context.web_sources:
            return (
                "Web search was executed and returned sources. Synthesize those findings into the final answer now; "
                "do not return a local-only or no_evidence answer. Include at least one web_citations item using only "
                "the returned W# keys, and include the matching [W#] marker in answer_markdown. Return only the answer contract JSON."
            )
        return "Use only citations returned by tools. Return the answer contract JSON again with valid S and W citation keys."

    @staticmethod
    def _parse_final_answer(output_text: str) -> AgentFinalAnswer:
        """Parse the contract and tolerate the previous string citation shape."""
        payload = json.loads(output_text)
        if isinstance(payload, dict) and isinstance(payload.get("answer_markdown"), str):
            payload["answer_markdown"] = AgentOrchestrator._normalize_citation_markup(payload["answer_markdown"])
        if isinstance(payload, dict) and isinstance(payload.get("local_citations"), list):
            payload["local_citations"] = [
                {"citation_key": item} if isinstance(item, str) else item
                for item in payload["local_citations"]
            ]
            cited_keys = {item.get("citation_key") for item in payload["local_citations"] if isinstance(item, dict)}
            for key in re.findall(r"\[(S\d+)\]", payload.get("answer_markdown", "")):
                if key not in cited_keys:
                    payload["local_citations"].append({"citation_key": key})
        return AgentFinalAnswer.model_validate(payload)

    @staticmethod
    def _normalize_citation_markup(answer: str) -> str:
        # OpenAI may emit private-use citation markup such as \ue000cite\ue002S4\ue001.
        # The product contract uses stable, clickable [S#]/[W#] markers instead.
        return re.sub(r"[\ue000-\uf8ff]cite[\ue000-\uf8ff](S\d+|W\d+)[\ue000-\uf8ff]", r"[\1]", answer)

    @staticmethod
    def _initial_input(question: str, context: Any) -> str:
        previous = "\n\n".join(f"Turn {turn.turn_index} question: {turn.question}\nTurn {turn.turn_index} answer: {turn.answer}" for turn in context.turns) or "[no previous completed turns]"
        return f"Recent conversation data (untrusted):\n{previous}\n\nCurrent user question:\n{question}"

    @staticmethod
    def _activity_label(name: str, arguments: dict[str, Any]) -> str:
        if name == "search_knowledge":
            return f"{str(arguments.get('query', '자료'))[:180]} 관련 자료를 찾고 있습니다."
        if name == "explore_node":
            return f"노드 탐색 중: {' · '.join(str(item)[:80] for item in arguments.get('node_ids', [])[:8])}"
        return "탐색 도구를 실행하고 있습니다."

    @staticmethod
    def _safe_activity_input(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "search_knowledge":
            return {"query_preview": str(arguments.get("query", ""))[:500]}
        if name == "explore_node":
            return {"node_labels": [str(item)[:100] for item in arguments.get("node_ids", [])[:8]]}
        return {}

    @staticmethod
    def _cancel_requested(session: Session, run_id: int) -> bool:
        run = session.get(AgentRun, run_id)
        return bool(run and run.status == "canceled")

    @staticmethod
    def _cancel(session: Session, run: AgentRun, history: QuestionHistory) -> None:
        run.status = "canceled"
        run.stop_reason = "canceled"
        run.completed_at = now()
        history.status = "failed"
        history.error_code = "AGENT_CANCELED"
        history.error_message = "Agent execution was canceled by the user."
        history.completed_at = now()
        session.add(run)
        session.add(history)
        session.commit()
        append_event(session, run, "run_canceled", turn=run.current_turn, label="Agent 실행을 취소했습니다.")

    @staticmethod
    def _fail(session: Session, run: AgentRun, history: QuestionHistory | None, code: str, message: str) -> None:
        run.status = "failed"
        run.stage = "finalizing"
        run.stop_reason = "error"
        run.last_error_code = code
        run.last_error_message = message
        run.completed_at = now()
        session.add(run)
        if history:
            history.status = "failed"
            history.error_code = code
            history.error_message = message
            history.completed_at = now()
            session.add(history)
        session.commit()
        append_event(session, run, "run_failed", turn=run.current_turn, label="Agent 실행에 실패했습니다.", error_code=code)

    @staticmethod
    def _safe_exception_message(exc: Exception) -> str:
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])[:500]
        return type(exc).__name__

    @staticmethod
    def _engine():
        from app.db import engine
        return engine
