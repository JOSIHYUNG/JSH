import re

from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.errors import conflict, not_found
from app.core.text import preview
from app.db import engine
from app.integrations.openai.responses import OpenAIResponsesGateway
from app.models import ChatConversation, ChunkConcept, Concept, Document, QuestionHistory, QuestionSource
from app.schemas.common import (
    ConversationDetailResponse,
    ConversationSummaryResponse,
    QuestionResultResponse,
    QuestionSourceResponse,
    RetrievalResponse,
)
from app.services.conversation_context import ConversationContextService
from app.services.documents import DocumentService
from app.services.jobs import now
from app.services.read_models import concept_summary, document_summary
from app.services.retrieval import RetrievalResult, RetrievalService


class QuestionService:
    def __init__(self, retrieval: RetrievalService, responses: OpenAIResponsesGateway, documents: DocumentService | None = None):
        self.retrieval = retrieval
        self.responses = responses
        self.documents = documents
        self.context = ConversationContextService()

    def create_conversation(self, session: Session, title: str | None = None) -> ChatConversation:
        timestamp = now()
        conversation = ChatConversation(
            title=(title or "새 대화").strip()[:255],
            title_source="user" if title else "auto",
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        return conversation

    def get_conversation(self, session: Session, conversation_id: int) -> ChatConversation:
        conversation = session.get(ChatConversation, conversation_id)
        if conversation is None or conversation.status == "deleted":
            raise not_found("CONVERSATION_NOT_FOUND", "대화 기록을 찾을 수 없습니다.")
        return conversation

    def enqueue(self, session: Session, question: str, conversation_id: int | None = None) -> QuestionHistory:
        normalized_question = question.strip()
        conversation = self.get_conversation(session, conversation_id) if conversation_id else self.create_conversation(session)
        if conversation.status != "active":
            raise conflict("CONVERSATION_NOT_ACTIVE", "현재 대화에는 질문을 추가할 수 없습니다.")
        previous_indexes = session.exec(
            select(QuestionHistory.turn_index).where(QuestionHistory.conversation_id == conversation.id)
        ).all()
        turn_index = max((value or 0 for value in previous_indexes), default=0) + 1
        timestamp = now()
        if conversation.title_source == "auto" and conversation.turn_count == 0:
            conversation.title = self._title_from_question(normalized_question)
        conversation.turn_count += 1
        conversation.last_turn_at = timestamp
        conversation.updated_at = timestamp
        history = QuestionHistory(
            conversation_id=conversation.id,
            turn_index=turn_index,
            question=normalized_question,
            status="queued",
            model_name=get_settings().openai_chat_model,
            created_at=timestamp,
        )
        session.add(history)
        session.add(conversation)
        session.commit()
        session.refresh(history)
        return history

    def process(self, history_id: int) -> None:
        with Session(engine) as session:
            history = session.get(QuestionHistory, history_id)
            if history is None or history.status in {"completed", "no_evidence", "failed"}:
                return
            result = None
            try:
                context = self.context.build(
                    session,
                    history.conversation_id,
                    exclude_history_id=history.id,
                )
                history.context_turn_count = len(context.turns)
                history.context_truncated = context.truncated
                history.status = "retrieving"
                session.add(history)
                session.commit()

                query = self._retrieval_query(history.question, context)
                history.retrieval_query = query
                session.add(history)
                session.commit()

                result = self.retrieval.search(session, query, 3)
                history.retrieval_provider = result.provider
                history.retrieval_candidate_count = result.candidate_count
                history.retrieval_mapping_failures = result.mapping_failures
                history.retrieval_count = len(result.hits)
                if not result.hits:
                    if self.responses.configured:
                        answer = self.responses.general_answer(
                            history.question,
                            [
                                {"turn_index": str(turn.turn_index), "question": turn.question, "answer": turn.answer}
                                for turn in context.turns
                            ],
                        )
                        history.answer_markdown = answer
                        history.answer_mode = "general"
                        history.answer_language = "ko" if re.search(r"[가-힣]", history.question) else "en"
                        history.status = "completed"
                        history.completed_at = now()
                        if self.documents and history.id:
                            generated = self.documents.create_ai_generated(
                                session,
                                question=history.question,
                                answer=answer,
                                question_id=history.id,
                            )
                            history.generated_document_id = generated.id
                        session.add(history)
                        session.commit()
                    else:
                        history.status = "no_evidence"
                        history.answer_markdown = "저장된 자료에서 관련 근거를 찾지 못했습니다."
                        history.completed_at = now()
                        session.add(history)
                        session.commit()
                    return

                history.status = "generating"
                session.add(history)
                session.commit()
                if not self.responses.configured:
                    self._store_sources(session, history, result)
                    self._mark_failed(
                        session,
                        history,
                        "AI_NOT_CONFIGURED",
                        "OpenAI API 키를 설정하면 찾은 근거를 바탕으로 답변을 생성할 수 있습니다.",
                    )
                    return

                evidence = [(f"S{index}", hit.chunk.content) for index, hit in enumerate(result.hits, 1)]
                answer = self.responses.grounded_answer(
                    history.question,
                    evidence,
                    [
                        {
                            "turn_index": str(turn.turn_index),
                            "question": turn.question,
                            "answer": turn.answer,
                        }
                        for turn in context.turns
                    ],
                )
                cited_keys = set(re.findall(r"\[(S\d+)]", answer))
                history.answer_markdown = answer
                history.answer_language = "ko" if re.search(r"[가-힣]", history.question) else "en"
                history.retrieval_count = sum(
                    1 for index, _hit in enumerate(result.hits, 1) if f"S{index}" in cited_keys
                )
                history.citation_count = len(cited_keys)
                history.status = "completed"
                history.completed_at = now()
                session.add(history)
                self._store_sources(session, history, result, cited_keys)
                session.commit()
            except Exception as exc:
                session.rollback()
                history = session.get(QuestionHistory, history_id)
                if history is None:
                    return
                if result is not None and result.hits:
                    self._store_sources(session, history, result)
                self._mark_failed(
                    session,
                    history,
                    "ANALYSIS_OUTPUT_INVALID" if isinstance(exc, ValueError) else "OPENAI_UNAVAILABLE",
                    "근거는 찾았지만 AI 답변을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                )

    def _retrieval_query(self, question: str, context) -> str:
        if not context.turns or not self.responses.configured:
            return self.context.fallback_query(question, context)
        if not self._needs_rewrite(question):
            return question.strip()[:1_000]
        turns = [
            {"turn_index": str(turn.turn_index), "question": turn.question, "answer": turn.answer}
            for turn in context.turns
        ]
        try:
            return self.responses.rewrite_question(question, turns)
        except Exception:
            return self.context.fallback_query(question, context)

    @staticmethod
    def _needs_rewrite(question: str) -> bool:
        normalized = " ".join(question.lower().split())
        if len(normalized) <= 80:
            return True
        markers = (
            "그 문서", "그 자료", "앞서", "이전", "방금", "해당", "그것", "이것", "저것",
            "두 번째", "첫 번째", "다시", "그 내용", "그 부분", "it ", "that ", "this ", "those ",
        )
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _title_from_question(question: str) -> str:
        first_line = next((line.strip() for line in question.splitlines() if line.strip()), question)
        return (first_line[:252] + "…") if len(first_line) > 255 else first_line

    @staticmethod
    def _mark_failed(session: Session, history: QuestionHistory, code: str, message: str) -> None:
        history.status = "failed"
        history.error_code = code
        history.error_message = message
        history.completed_at = now()
        session.add(history)
        session.commit()

    @staticmethod
    def _store_sources(
        session: Session,
        history: QuestionHistory,
        result: RetrievalResult,
        allowed_keys: set[str] | None = None,
    ) -> None:
        existing = {
            source.citation_key
            for source in session.exec(
                select(QuestionSource).where(QuestionSource.question_history_id == history.id)
            ).all()
        }
        for index, hit in enumerate(result.hits, 1):
            citation_key = f"S{index}"
            if citation_key in existing or (allowed_keys is not None and citation_key not in allowed_keys):
                continue
            session.add(
                QuestionSource(
                    question_history_id=history.id or 0,
                    rank=index,
                    chunk_id=hit.chunk.id,
                    document_id=hit.document.id,
                    document_title_snapshot=hit.document.title,
                    document_filename_snapshot=hit.document.original_filename,
                    chunk_content_snapshot=hit.chunk.content,
                    start_char_snapshot=hit.chunk.start_char,
                    end_char_snapshot=hit.chunk.end_char,
                    score=hit.score,
                    citation_key=citation_key,
                    mapping_confidence=hit.mapping_confidence,
                    current_state="current",
                    created_at=now(),
                )
            )

    def get(self, session: Session, question_id: int) -> QuestionHistory:
        history = session.get(QuestionHistory, question_id)
        if history is None:
            raise not_found("QUESTION_NOT_FOUND", "대화 기록을 찾을 수 없습니다.")
        return history

    def to_response(self, session: Session, history: QuestionHistory) -> QuestionResultResponse:
        sources = session.exec(
            select(QuestionSource)
            .where(QuestionSource.question_history_id == history.id)
            .order_by(QuestionSource.rank)
        ).all()
        source_models = []
        for source in sources:
            document = session.get(Document, source.document_id) if source.document_id is not None else None
            openable = (
                document is not None
                and document.status == "ready"
                and source.chunk_id is not None
                and source.current_state == "current"
            )
            current_state = source.current_state
            if not openable and current_state == "current":
                current_state = "document_deleted" if document is None else "mapping_unavailable"
            source_models.append(
                QuestionSourceResponse(
                    rank=source.rank,
                    citation_key=source.citation_key,
                    document_id=source.document_id,
                    chunk_id=source.chunk_id,
                    document_title=source.document_title_snapshot,
                    document_status="ready" if openable else current_state,
                    chunk_preview=preview(source.chunk_content_snapshot),
                    start_char=source.start_char_snapshot,
                    end_char=source.end_char_snapshot,
                    score=source.score,
                    mapping_confidence=source.mapping_confidence,
                    openable=openable,
                )
            )
        concept_ids = []
        for source in sources:
            if source.chunk_id:
                concept_ids.extend(
                    session.exec(select(ChunkConcept.concept_id).where(ChunkConcept.chunk_id == source.chunk_id)).all()
                )
        concepts = []
        for concept_id in dict.fromkeys(value for value in concept_ids if value is not None):
            concept = session.get(Concept, concept_id)
            if concept:
                concepts.append(concept_summary(session, concept))
        retrieval = RetrievalResponse(
            provider=history.retrieval_provider,
            candidate_count=history.retrieval_candidate_count,
            returned_count=len(sources),
            mapping_failures=history.retrieval_mapping_failures,
            top_score=max((source.score for source in sources), default=None),
            used_chunk_ids=[source.chunk_id for source in sources if source.chunk_id is not None],
        )
        error = (
            {
                "code": history.error_code,
                "message": history.error_message or "질문 처리에 실패했습니다.",
                "retryable": history.error_code != "AI_NOT_CONFIGURED",
            }
            if history.error_code
            else None
        )
        generated_document = session.get(Document, history.generated_document_id) if history.generated_document_id else None
        return QuestionResultResponse(
            id=history.id or 0,
            conversation_id=history.conversation_id,
            turn_index=history.turn_index,
            question=history.question,
            status=history.status,
            answer_markdown=history.answer_markdown,
            answer_mode=history.answer_mode,
            answer_language=history.answer_language,
            sources=source_models,
            related_concepts=concepts,
            retrieval=retrieval,
            error=error,
            context={
                "turn_count": history.context_turn_count,
                "truncated": history.context_truncated,
                "retrieval_query": history.retrieval_query,
            },
            generated_document=document_summary(session, generated_document) if generated_document else None,
            created_at=history.created_at,
            completed_at=history.completed_at,
        )

    def conversation_detail(self, session: Session, conversation_id: int) -> ConversationDetailResponse:
        conversation = self.get_conversation(session, conversation_id)
        rows = session.exec(
            select(QuestionHistory)
            .where(QuestionHistory.conversation_id == conversation.id)
            .order_by(QuestionHistory.turn_index, QuestionHistory.created_at)
        ).all()
        return ConversationDetailResponse(
            conversation=ConversationSummaryResponse(
                id=conversation.id or 0,
                title=conversation.title,
                title_source=conversation.title_source,
                status=conversation.status,
                turn_count=conversation.turn_count,
                last_turn_at=conversation.last_turn_at,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            ),
            turns=[self.to_response(session, row) for row in rows],
        )

    @staticmethod
    def conversation_summary(conversation: ChatConversation) -> ConversationSummaryResponse:
        return ConversationSummaryResponse(
            id=conversation.id or 0,
            title=conversation.title,
            title_source=conversation.title_source,
            status=conversation.status,
            turn_count=conversation.turn_count,
            last_turn_at=conversation.last_turn_at,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
