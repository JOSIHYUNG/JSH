from typing import Any

from app.agent.contracts import ToolResult
from app.agent.tools.base import ToolContext, ToolDefinition
from app.services.node_exploration import NodeExplorationService


def make_explore_tool(service: NodeExplorationService) -> ToolDefinition:
    return ToolDefinition(
        name="explore_node",
        description="Explore connected graph nodes and matching source excerpts.",
        parameters={
            "type": "object",
            "properties": {"node_ids": {"type": "array", "minItems": 1, "maxItems": service.max_nodes, "items": {"type": "string"}}},
            "required": ["node_ids"],
            "additionalProperties": False,
        },
        handler=lambda context, arguments: explore_node(context, arguments, service),
    )


def explore_node(context: ToolContext, arguments: dict[str, Any], service: NodeExplorationService) -> ToolResult:
    node_ids = arguments.get("node_ids")
    if not isinstance(node_ids, list) or not node_ids or len(node_ids) > service.max_nodes or any(not isinstance(value, str) for value in node_ids):
        return ToolResult(ok=False, tool="explore_node", error={"code": "TOOL_INPUT_INVALID", "message": f"node_ids must contain 1 to {service.max_nodes} strings.", "retryable": True, "suggested_action": "Use node ids returned by search_knowledge."})
    data = service.explore(context.session, node_ids)
    context.related_node_ids.update(node_ids)
    context.related_node_ids.update(item["node_id"] for item in data["nodes"])
    return ToolResult(ok=True, tool="explore_node", data=data, truncated=data["truncated"], result_count=len(data["nodes"]) + len(data["mentions"]))
