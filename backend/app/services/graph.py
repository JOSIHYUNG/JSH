from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import ChunkConcept, Concept, ConceptRelation, Document, DocumentChunk
from app.schemas.common import GraphEdge, GraphNode, GraphSnapshot


class GraphService:
    def build(self, session: Session, *, include_chunks: bool = False, node_types: list[str] | None = None, concept_types: list[str] | None = None, focus_type: str | None = None, focus_id: int | None = None, depth: int = 1, recent_days: int | None = None, min_strength: float = 0.0, limit_nodes: int | None = None, limit_edges: int | None = None) -> GraphSnapshot:
        settings = get_settings()
        limit_nodes = min(limit_nodes or settings.graph_node_limit, 2000)
        limit_edges = min(limit_edges or settings.graph_edge_limit, 5000)
        requested = set(node_types or ["document", "concept"])
        documents = list(session.exec(select(Document).where(Document.status == "ready").order_by(Document.updated_at.desc())).all())
        if recent_days is not None:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=recent_days)
            documents = [document for document in documents if document.updated_at >= cutoff]
        document_ids = {document.id for document in documents}
        chunks = list(session.exec(select(DocumentChunk).where(DocumentChunk.document_id.in_([v for v in document_ids if v is not None]))).all()) if document_ids else []
        chunk_ids = {chunk.id for chunk in chunks}
        associations = list(session.exec(select(ChunkConcept).where(ChunkConcept.chunk_id.in_([v for v in chunk_ids if v is not None]))).all()) if chunk_ids else []
        concept_ids = {association.concept_id for association in associations}
        concepts = list(session.exec(select(Concept).where(Concept.id.in_([v for v in concept_ids if v is not None]), Concept.visibility == "visible")).all()) if concept_ids else []
        if concept_types:
            concepts = [concept for concept in concepts if concept.concept_type in concept_types]
            concept_ids = {concept.id for concept in concepts}
            associations = [association for association in associations if association.concept_id in concept_ids]
        nodes: list[GraphNode] = []
        if "document" in requested:
            for document in documents:
                nodes.append(GraphNode(id=f"document:{document.id}", entity_type="document", entity_id=document.id or 0, label=document.title, subtype=None, size=8, color_token="document", metadata={"title": document.title, "summary": document.summary, "status": document.status}))
        if include_chunks and "chunk" in requested:
            for chunk in chunks:
                nodes.append(GraphNode(id=f"chunk:{chunk.id}", entity_type="chunk", entity_id=chunk.id or 0, label=f"청크 {chunk.chunk_index + 1}", subtype=None, size=3, color_token="chunk", metadata={"document_id": chunk.document_id, "start_char": chunk.start_char, "end_char": chunk.end_char}))
        if "concept" in requested:
            degree = {concept.id: sum(association.concept_id == concept.id for association in associations) for concept in concepts}
            for concept in concepts:
                nodes.append(GraphNode(id=f"concept:{concept.id}", entity_type="concept", entity_id=concept.id or 0, label=concept.canonical_name, subtype=concept.concept_type, size=min(12, 4 + degree.get(concept.id, 0)), color_token=concept.concept_type, metadata={"description": concept.description, "connection_count": degree.get(concept.id, 0)}))
        node_ids = {node.id for node in nodes}
        edges: list[GraphEdge] = []
        for chunk in chunks:
            if include_chunks and f"document:{chunk.document_id}" in node_ids and f"chunk:{chunk.id}" in node_ids:
                edges.append(GraphEdge(id=f"contains:{chunk.document_id}:{chunk.id}", source=f"document:{chunk.document_id}", target=f"chunk:{chunk.id}", edge_type="contains", relation_type=None, strength=1.0, is_directed=True, evidence_chunk_id=chunk.id))
        for association in associations:
            source = f"chunk:{association.chunk_id}" if include_chunks else f"document:{next((chunk.document_id for chunk in chunks if chunk.id == association.chunk_id), 0)}"
            target = f"concept:{association.concept_id}"
            if source in node_ids and target in node_ids:
                edges.append(GraphEdge(id=f"mentions:{association.chunk_id}:{association.concept_id}:{association.mention}", source=source, target=target, edge_type="mentions", relation_type=None, strength=association.extraction_confidence, is_directed=False, evidence_chunk_id=association.chunk_id))
        relations = session.exec(select(ConceptRelation).where(ConceptRelation.evidence_chunk_id.in_([v for v in chunk_ids if v is not None]), ConceptRelation.strength >= min_strength)).all() if chunk_ids else []
        for relation in relations:
            source, target = f"concept:{relation.source_concept_id}", f"concept:{relation.target_concept_id}"
            if source in node_ids and target in node_ids:
                edges.append(GraphEdge(id=f"relates:{relation.id}", source=source, target=target, edge_type="relates", relation_type=relation.relation_type, strength=relation.strength, is_directed=relation.is_directed, evidence_chunk_id=relation.evidence_chunk_id))
        if focus_type and focus_id:
            focus = f"{focus_type}:{focus_id}"
            connected = {focus}
            for _ in range(max(1, min(depth, 2))):
                connected |= {edge.target for edge in edges if edge.source in connected}
                connected |= {edge.source for edge in edges if edge.target in connected}
            nodes = [node for node in nodes if node.id in connected]
            node_ids = {node.id for node in nodes}
            edges = [edge for edge in edges if edge.source in node_ids and edge.target in node_ids]
        truncated = len(nodes) > limit_nodes or len(edges) > limit_edges
        edges.sort(key=lambda edge: edge.strength, reverse=True)
        nodes = nodes[:limit_nodes]
        allowed = {node.id for node in nodes}
        edges = [edge for edge in edges[:limit_edges] if edge.source in allowed and edge.target in allowed]
        return GraphSnapshot(nodes=nodes, edges=edges, filters={"include_chunks": include_chunks, "node_types": list(requested), "concept_types": concept_types or [], "min_strength": min_strength}, truncated=truncated, node_count=len(nodes), edge_count=len(edges))
