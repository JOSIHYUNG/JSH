from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.utcnow()


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"
    __table_args__ = (UniqueConstraint("question_history_id", name="uq_agent_run_question"),)

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="chat_conversations.id", index=True)
    question_history_id: int = Field(foreign_key="question_histories.id", index=True)
    status: str = Field(default="queued", index=True, max_length=20)
    stage: str = Field(default="queued", index=True, max_length=30)
    current_turn: int = 0
    max_turns: int = 30
    tool_call_count: int = 0
    model_name: str = Field(max_length=120)
    prompt_version: str = Field(default="unknown", max_length=120)
    stop_reason: str | None = Field(default=None, max_length=30)
    last_error_code: str | None = Field(default=None, max_length=80)
    last_error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentEvent(SQLModel, table=True):
    __tablename__ = "agent_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_agent_event_run_sequence"),)

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="agent_runs.id", index=True)
    sequence: int = Field(index=True)
    turn: int = 0
    event_type: str = Field(max_length=40, index=True)
    tool_name: str | None = Field(default=None, max_length=40)
    activity_label: str | None = Field(default=None, max_length=500)
    input_safe_json: str | None = None
    output_safe_json: str | None = None
    error_code: str | None = Field(default=None, max_length=80)
    duration_ms: int | None = None
    created_at: datetime = Field(default_factory=utc_now, index=True)


class QuestionWebSource(SQLModel, table=True):
    __tablename__ = "question_web_sources"
    __table_args__ = (UniqueConstraint("question_history_id", "citation_key", name="uq_question_web_source_key"),)

    id: int | None = Field(default=None, primary_key=True)
    question_history_id: int = Field(foreign_key="question_histories.id", index=True)
    citation_key: str = Field(max_length=10)
    url: str = Field(max_length=2000)
    title: str = Field(max_length=500)
    publisher: str | None = Field(default=None, max_length=255)
    source_rank: int = 0
    created_at: datetime = Field(default_factory=utc_now, index=True)
