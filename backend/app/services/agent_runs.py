from typing import Any

from sqlmodel import Session, select

from app.agent.orchestrator import AgentOrchestrator
from app.core.config import get_settings
from app.core.errors import conflict, not_found
from app.models import AgentEvent, AgentRun, QuestionHistory, QuestionWebSource
from app.schemas.agent import AgentActivityEvent, AgentRunSummary
from app.services.jobs import now
from app.services.questions import QuestionService


class AgentRunService:
    def __init__(self, questions: QuestionService, orchestrator: AgentOrchestrator):
        self.questions = questions
        self.orchestrator = orchestrator

    def enqueue(self, session: Session, question: str, conversation_id: int | None = None) -> tuple[AgentRun, QuestionHistory]:
        if conversation_id:
            active = session.exec(
                select(AgentRun).where(AgentRun.conversation_id == conversation_id, AgentRun.status.in_(["queued", "running"]))
            ).first()
            if active:
                raise conflict("AGENT_BUSY", "This conversation already has a running Agent.")
        history = self.questions.enqueue(session, question, conversation_id)
        run = AgentRun(
            conversation_id=history.conversation_id or 0,
            question_history_id=history.id or 0,
            status="queued",
            stage="queued",
            max_turns=30,
            model_name=get_settings().effective_agent_model,
            prompt_version="pending",
            created_at=now(),
            updated_at=now(),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run, history

    def get(self, session: Session, run_id: int) -> AgentRun:
        run = session.get(AgentRun, run_id)
        if run is None:
            raise not_found("AGENT_RUN_NOT_FOUND", "Agent run was not found.")
        return run

    def summary(self, session: Session, run: AgentRun) -> AgentRunSummary:
        history = session.get(QuestionHistory, run.question_history_id)
        error = {"code": run.last_error_code, "message": run.last_error_message, "retryable": run.last_error_code not in {"AI_NOT_CONFIGURED", "AGENT_MAX_TURNS_EXCEEDED"}} if run.last_error_code else None
        return AgentRunSummary(id=run.id or 0, question_id=run.question_history_id, conversation_id=run.conversation_id, turn_index=history.turn_index if history else None, status=run.status, stage=run.stage, current_turn=run.current_turn, max_turns=run.max_turns, tool_call_count=run.tool_call_count, stop_reason=run.stop_reason, error=error, created_at=run.created_at, completed_at=run.completed_at)

    def events(self, session: Session, run_id: int, after_sequence: int = 0) -> list[AgentActivityEvent]:
        rows = session.exec(select(AgentEvent).where(AgentEvent.run_id == run_id, AgentEvent.sequence > after_sequence).order_by(AgentEvent.sequence)).all()
        from app.agent.events import safe_event_payload
        return [AgentActivityEvent.model_validate(safe_event_payload(row)) for row in rows]

    def result_payload(self, session: Session, run: AgentRun) -> dict[str, Any]:
        history = session.get(QuestionHistory, run.question_history_id)
        question = self.questions.to_response(session, history) if history else None
        web_sources = session.exec(select(QuestionWebSource).where(QuestionWebSource.question_history_id == run.question_history_id).order_by(QuestionWebSource.source_rank)).all()
        return {"run": self.summary(session, run), "result": question, "web_sources": [{"citation_key": source.citation_key, "url": source.url, "title": source.title, "publisher": source.publisher, "rank": source.source_rank} for source in web_sources]}

    def cancel(self, session: Session, run_id: int) -> AgentRun:
        run = self.get(session, run_id)
        if run.status in {"completed", "failed", "canceled", "max_turns"}:
            return run
        run.status = "canceled"
        run.stop_reason = "canceled"
        run.completed_at = now()
        run.updated_at = now()
        history = session.get(QuestionHistory, run.question_history_id)
        if history:
            history.status = "failed"
            history.error_code = "AGENT_CANCELED"
            history.error_message = "Agent execution was canceled by the user."
            history.completed_at = now()
            session.add(history)
        session.add(run)
        session.commit()
        from app.agent.events import append_event
        append_event(session, run, "run_canceled", turn=run.current_turn, label="Agent 실행을 취소했습니다.")
        return run
