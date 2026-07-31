"""STDIO MCP server exposing the existing read-only Agent knowledge tools."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


# Allow both `python -m app.mcp.server` from backend/ and direct execution of
# this file from Codex's MCP configuration. Settings and SQLite paths are
# resolved from backend/ in either mode.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from sqlmodel import Session

from app.agent.tools.base import ToolContext, ToolRegistry
from app.agent.tools.explore_node import make_explore_tool
from app.agent.tools.search_knowledge import make_search_tool
from app.api.dependencies import vector_store
from app.core.config import get_settings
from app.db import engine
from app.services.node_exploration import NodeExplorationService
from app.services.retrieval import RetrievalService


settings = get_settings()
retrieval = RetrievalService(vector_store())
explorer = NodeExplorationService(
    max_nodes=settings.agent_explore_node_limit,
    max_excerpts_per_node=settings.agent_explore_excerpt_limit,
    max_output_chars=settings.agent_tool_output_max_chars,
)
registry = ToolRegistry([
    make_search_tool(retrieval),
    make_explore_tool(explorer),
])

mcp = MCPServer(
    name="second-brain",
    title="JSH Second Brain",
    description="Read-only access to the local JSH second-brain knowledge graph.",
    instructions="Use search_knowledge for relevant local chunks and explore_node for graph relationships and source excerpts.",
    version="0.1.0",
)

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
)


def _execute(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Adapt an existing Agent ToolDefinition to the MCP structured result."""
    with Session(engine) as session:
        result = registry.execute(ToolContext(session), name, arguments)
        return result.model_dump(mode="json", exclude_none=True)


@mcp.tool(
    name="search_knowledge",
    description="Search the local second brain for up to three relevant document chunks, source documents, and connected concepts.",
    annotations=READ_ONLY,
    structured_output=True,
)
def search_knowledge(query: str) -> dict[str, Any]:
    """Search local knowledge using the existing Agent retrieval implementation."""
    return _execute("search_knowledge", {"query": query})


@mcp.tool(
    name="explore_node",
    description="Explore connected graph nodes and matching source excerpts using existing node exploration logic.",
    annotations=READ_ONLY,
    structured_output=True,
)
def explore_node(node_ids: list[str]) -> dict[str, Any]:
    """Explore graph nodes using the existing Agent exploration implementation."""
    return _execute("explore_node", {"node_ids": node_ids})


def main() -> None:
    """Run the server over MCP STDIO transport."""
    mcp.run("stdio")


if __name__ == "__main__":
    main()
