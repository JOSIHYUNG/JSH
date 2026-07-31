import json
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    suggested_action: str | None = None


class ToolResult(BaseModel):
    ok: bool
    tool: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: ToolError | None = None
    truncated: bool = False
    result_count: int = 0

    def as_model_output(self, max_chars: int = 24_000) -> str:
        raw = self.model_dump_json(exclude_none=True)
        if len(raw) <= max_chars:
            return raw
        return safe_json({
            "ok": False,
            "tool": self.tool,
            "data": {"message": "Tool output was truncated. Retry with a narrower query or fewer nodes."},
            "error": {"code": "TOOL_OUTPUT_TRUNCATED", "message": "The tool output exceeded the configured size limit.", "retryable": True, "suggested_action": "Use a narrower query or fewer node IDs."},
        })


class ToolCallRequest(BaseModel):
    call_id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LocalCitation(BaseModel):
    citation_key: str = Field(pattern=r"^S[1-9][0-9]*$")


class WebCitation(BaseModel):
    citation_key: str = Field(pattern=r"^W[1-9][0-9]*$")
    url: str
    title: str = ""
    publisher: str | None = None


class AgentFinalAnswer(BaseModel):
    answer_markdown: str = Field(min_length=1, max_length=20_000)
    local_citations: list[LocalCitation] = Field(default_factory=list)
    web_citations: list[WebCitation] = Field(default_factory=list)
    related_node_ids: list[str] = Field(default_factory=list, max_length=50)
    stop_reason: Literal["completed", "no_evidence", "max_turns"] = "completed"


def safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
