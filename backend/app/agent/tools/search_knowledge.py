from typing import Any

from pydantic import ValidationError
from sqlmodel import select

from app.agent.contracts import ToolResult
from app.agent.tools.base import ToolContext, ToolDefinition
from app.models import ChunkConcept, Concept
from app.services.read_models import concept_summary
from app.services.retrieval import RetrievalService


def make_search_tool(retrieval: RetrievalService) -> ToolDefinition:
    return ToolDefinition(
        name="search_knowledge",
        description="Search the local second brain for up to three relevant document chunks.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 1000}},
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=lambda context, arguments: search_knowledge(context, arguments, retrieval),
    )


def search_knowledge(context: ToolContext, arguments: dict[str, Any], retrieval: RetrievalService) -> ToolResult:
    query = str(arguments.get("query", "")).strip()
    if len(query) < 2 or len(query) > 1000:
        return ToolResult(ok=False, tool="search_knowledge", error={"code": "TOOL_INPUT_INVALID", "message": "query must be between 2 and 1000 characters.", "retryable": True, "suggested_action": "Provide a concise standalone search sentence."})
    result = retrieval.search(context.session, query, 3)
    hits: list[dict[str, Any]] = []
    for hit in result.hits[:3]:
        key = context.next_citation_key()
        context.local_hits[key] = hit
        chunk_id = hit.chunk.id or 0
        document_id = hit.document.id or 0
        context.related_node_ids.update({f"chunk:{chunk_id}", f"document:{document_id}"})
        concepts = []
        associations = context.session.exec(
            select(ChunkConcept, Concept).join(Concept, Concept.id == ChunkConcept.concept_id).where(ChunkConcept.chunk_id == chunk_id)
        ).all()
        for association, concept in associations:
            context.related_node_ids.add(f"concept:{concept.id}")
            concepts.append({
                "node_id": f"concept:{concept.id}",
                "concept_type": concept.concept_type,
                "canonical_name": concept.canonical_name,
                "english_name": concept.english_name,
                "abbreviation": concept.abbreviation,
                "description": concept.description,
            })
        hits.append({
            "citation_key": key,
            "chunk_node_id": f"chunk:{chunk_id}",
            "chunk_id": chunk_id,
            "document_id": document_id,
            "document_title": hit.document.title,
            "document_status": hit.document.status,
            "chunk_text": hit.chunk.content,
            "start_char": hit.chunk.start_char,
            "end_char": hit.chunk.end_char,
            "score": hit.score,
            "mapping_confidence": hit.mapping_confidence,
            "concepts": concepts,
        })
    return ToolResult(ok=True, tool="search_knowledge", data={"provider": result.provider, "candidate_count": result.candidate_count, "mapping_failures": result.mapping_failures, "hits": hits}, result_count=len(hits))
