from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentRunCreate(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    conversation_id: int | None = Field(default=None, ge=1)


class AgentRunSummary(BaseModel):
    id: int
    question_id: int
    conversation_id: int
    turn_index: int | None
    status: str
    stage: str
    current_turn: int
    max_turns: int
    tool_call_count: int
    stop_reason: str | None = None
    error: dict[str, Any] | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AgentActivityEvent(BaseModel):
    sequence: int
    run_id: int
    turn: int
    type: str
    tool: str | None = None
    label: str | None = None
    status: Literal["started", "completed", "failed", "terminal"] | None = None
    query_preview: str | None = None
    node_labels: list[str] = Field(default_factory=list)
    result_count: int | None = None
    error_code: str | None = None
    created_at: datetime
