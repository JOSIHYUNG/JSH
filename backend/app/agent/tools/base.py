from dataclasses import dataclass, field
from typing import Any, Callable

from sqlmodel import Session

from app.agent.contracts import ToolResult


@dataclass
class ToolContext:
    session: Session
    local_hits: dict[str, Any] = field(default_factory=dict)
    related_node_ids: set[str] = field(default_factory=set)
    web_sources: dict[str, dict[str, str]] = field(default_factory=dict)

    def next_citation_key(self) -> str:
        return f"S{len(self.local_hits) + 1}"


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[ToolContext, dict[str, Any]], ToolResult]

    def response_schema(self) -> dict[str, Any]:
        return {"type": "function", "name": self.name, "description": self.description, "parameters": self.parameters, "strict": True}


class ToolRegistry:
    def __init__(self, definitions: list[ToolDefinition]):
        self._definitions = {item.name: item for item in definitions}

    def definitions(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def execute(self, context: ToolContext, name: str, arguments: dict[str, Any]) -> ToolResult:
        definition = self._definitions.get(name)
        if definition is None:
            return ToolResult(ok=False, tool=name, error={"code": "TOOL_NOT_FOUND", "message": f"Unknown tool: {name}", "retryable": False})
        try:
            return definition.handler(context, arguments)
        except Exception as exc:
            return ToolResult(ok=False, tool=name, error={"code": "TOOL_EXECUTION_FAILED", "message": f"Tool {name} failed: {type(exc).__name__}", "retryable": True, "suggested_action": "Retry with the same goal and valid arguments."})
