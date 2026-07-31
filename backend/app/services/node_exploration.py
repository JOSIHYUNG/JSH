import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from app.models import ChunkConcept, Concept, ConceptAlias, ConceptRelation, Document, DocumentChunk


@dataclass(frozen=True)
class NodeRef:
    kind: str
    entity_id: int


class NodeExplorationService:
    def __init__(self, *, max_nodes: int = 8, max_excerpts_per_node: int = 12, max_output_chars: int = 24_000):
        self.max_nodes = max_nodes
        self.max_excerpts_per_node = max_excerpts_per_node
        self.max_output_chars = max_output_chars

    def explore(self, session: Session, node_ids: list[str]) -> dict[str, Any]:
        unique = list(dict.fromkeys(node_ids))[: self.max_nodes]
        nodes: list[dict[str, Any]] = []
        connections: list[dict[str, Any]] = []
        mentions: list[dict[str, Any]] = []
        skipped: list[str] = []
        for raw_id in unique:
            ref = self._parse(raw_id)
            if ref is None:
                skipped.append(raw_id)
                continue
            node = self._node(session, raw_id, ref)
            if node is None:
                skipped.append(raw_id)
                continue
            nodes.append(node)
            connections.extend(self._connections(session, raw_id, ref))
            mentions.extend(self._mentions(session, raw_id, ref))
        truncated = False
        total = 0
        bounded_mentions = []
        for item in mentions:
            if len(bounded_mentions) >= self.max_nodes * self.max_excerpts_per_node:
                truncated = True
                break
            excerpt = item["excerpt"]
            if total + len(excerpt) > self.max_output_chars:
                truncated = True
                break
            total += len(excerpt)
            bounded_mentions.append(item)
        return {"nodes": nodes, "connections": connections, "mentions": bounded_mentions, "skipped_node_ids": skipped, "truncated": truncated, "partial": bool(skipped)}

    @staticmethod
    def _parse(raw: str) -> NodeRef | None:
        match = re.fullmatch(r"(document|chunk|concept):(\d+)", raw.strip())
        return NodeRef(match.group(1), int(match.group(2))) if match else None

    def _node(self, session: Session, raw: str, ref: NodeRef) -> dict[str, Any] | None:
        if ref.kind == "document":
            item = session.get(Document, ref.entity_id)
            return {"node_id": raw, "name": item.title, "node_type": "document", "description": item.summary, "source_count": item.character_count} if item and item.status != "deleted" else None
        if ref.kind == "chunk":
            item = session.get(DocumentChunk, ref.entity_id)
            document = session.get(Document, item.document_id) if item else None
            return {"node_id": raw, "name": f"chunk {item.chunk_index + 1}", "node_type": "chunk", "description": item.content[:500], "source_count": 1, "document_id": document.id if document else None} if item and document and document.status != "deleted" else None
        item = session.get(Concept, ref.entity_id)
        return {"node_id": raw, "name": item.canonical_name, "node_type": "concept", "description": item.description, "english_name": item.english_name, "abbreviation": item.abbreviation, "source_count": len(session.exec(select(ChunkConcept.chunk_id).where(ChunkConcept.concept_id == ref.entity_id)).all())} if item and item.visibility == "visible" else None

    def _connections(self, session: Session, raw: str, ref: NodeRef) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if ref.kind == "document":
            chunks = session.exec(select(DocumentChunk).where(DocumentChunk.document_id == ref.entity_id)).all()
            for chunk in chunks:
                result.append({"source": raw, "target": f"chunk:{chunk.id}", "relation_type": "contains", "strength": 1.0, "evidence_chunk_id": chunk.id, "target_summary": chunk.content[:180]})
            concepts = session.exec(select(ChunkConcept, Concept).join(Concept, Concept.id == ChunkConcept.concept_id).where(ChunkConcept.chunk_id.in_([chunk.id for chunk in chunks if chunk.id]))).all() if chunks else []
            for _, concept in concepts:
                result.append({"source": raw, "target": f"concept:{concept.id}", "relation_type": "mentions", "strength": 1.0, "evidence_chunk_id": None, "target_summary": concept.description})
        elif ref.kind == "chunk":
            chunk = session.get(DocumentChunk, ref.entity_id)
            if chunk:
                result.append({"source": raw, "target": f"document:{chunk.document_id}", "relation_type": "belongs_to", "strength": 1.0, "evidence_chunk_id": chunk.id, "target_summary": "source document"})
                for _, concept in session.exec(select(ChunkConcept, Concept).join(Concept, Concept.id == ChunkConcept.concept_id).where(ChunkConcept.chunk_id == ref.entity_id)).all():
                    result.append({"source": raw, "target": f"concept:{concept.id}", "relation_type": "mentions", "strength": 1.0, "evidence_chunk_id": chunk.id, "target_summary": concept.description})
        else:
            for relation in session.exec(select(ConceptRelation).where((ConceptRelation.source_concept_id == ref.entity_id) | (ConceptRelation.target_concept_id == ref.entity_id))).all():
                target_id = relation.target_concept_id if relation.source_concept_id == ref.entity_id else relation.source_concept_id
                target = session.get(Concept, target_id)
                if target and target.visibility == "visible":
                    result.append({"source": raw, "target": f"concept:{target.id}", "relation_type": relation.relation_type, "strength": relation.strength, "evidence_chunk_id": relation.evidence_chunk_id, "target_summary": target.description})
        return result

    def _mentions(self, session: Session, raw: str, ref: NodeRef) -> list[dict[str, Any]]:
        if ref.kind != "concept":
            return []
        concept = session.get(Concept, ref.entity_id)
        if not concept:
            return []
        names = [concept.canonical_name, concept.english_name or "", concept.abbreviation or ""]
        names.extend(alias.alias for alias in session.exec(select(ConceptAlias).where(ConceptAlias.concept_id == ref.entity_id)).all())
        names = list(dict.fromkeys(value.strip() for value in names if value and value.strip()))
        chunks = session.exec(select(DocumentChunk, Document).join(Document, Document.id == DocumentChunk.document_id).join(ChunkConcept, ChunkConcept.chunk_id == DocumentChunk.id).where(ChunkConcept.concept_id == ref.entity_id, Document.status != "deleted")).all()
        output: list[dict[str, Any]] = []
        for chunk, document in chunks:
            ranges: list[tuple[int, int, str]] = []
            folded = chunk.content.casefold()
            for name in names:
                needle = name.casefold()
                start = 0
                while needle:
                    index = folded.find(needle, start)
                    if index < 0:
                        break
                    ranges.append((index, index + len(name), name))
                    start = index + max(1, len(needle))
            ranges.sort()
            merged: list[dict[str, Any]] = []
            for start, end, alias in ranges:
                window_start, window_end = max(0, start - 500), min(len(chunk.content), end + 500)
                if merged and window_start <= merged[-1]["end_char"]:
                    merged[-1]["end_char"] = max(merged[-1]["end_char"], window_end)
                    merged[-1]["matched_aliases"].append(alias)
                else:
                    merged.append({"start_char": window_start, "end_char": window_end, "matched_aliases": [alias]})
            for item in merged[: self.max_excerpts_per_node]:
                output.append({"node_id": raw, "chunk_node_id": f"chunk:{chunk.id}", "document_id": document.id, "document_title": document.title, "matched_aliases": list(dict.fromkeys(item["matched_aliases"])), "start_char": chunk.start_char + item["start_char"], "end_char": chunk.start_char + item["end_char"], "excerpt": chunk.content[item["start_char"] : item["end_char"]]})
        return output
