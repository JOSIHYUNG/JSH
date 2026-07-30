from dataclasses import dataclass

from sqlmodel import Session, select

from app.core.text import normalize_name, preview
from app.integrations.openai.vector_store import OpenAIVectorStoreGateway, VectorSearchItem
from app.models import Document, DocumentChunk


@dataclass
class RetrievalHit:
    chunk: DocumentChunk
    document: Document
    score: float
    mapping_confidence: float


@dataclass
class RetrievalResult:
    provider: str
    candidate_count: int
    hits: list[RetrievalHit]
    mapping_failures: int


class RetrievalService:
    def __init__(self, vector_store: OpenAIVectorStoreGateway):
        self.vector_store = vector_store

    def search(self, session: Session, query: str, limit: int = 3) -> RetrievalResult:
        if self.vector_store.configured:
            try:
                candidates = self.vector_store.search(query, limit)
                hits, failures = self._map_vector_results(session, candidates)
                if hits:
                    return RetrievalResult("vector_store", len(candidates), hits[:limit], failures)
            except Exception:
                pass
        hits = self._search_fts(session, query, limit)
        return RetrievalResult("lexical_fallback" if hits else "none", len(hits), hits, 0)

    def _map_vector_results(self, session: Session, candidates: list[VectorSearchItem]) -> tuple[list[RetrievalHit], int]:
        hits: list[RetrievalHit] = []
        failures = 0
        for item in candidates:
            document = session.exec(
                select(Document).where(
                    Document.vector_store_file_id == item.file_id,
                    Document.vector_store_status == "indexed",
                    Document.status == "ready",
                )
            ).first()
            if document is None:
                failures += 1
                continue
            chunks = session.exec(select(DocumentChunk).where(DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index)).all()
            match = self._best_chunk(chunks, item.content)
            if match is None:
                failures += 1
                continue
            chunk, confidence = match
            hits.append(RetrievalHit(chunk, document, max(0.0, min(1.0, item.score)), confidence))
        return hits, failures

    def _search_fts(self, session: Session, query: str, limit: int) -> list[RetrievalHit]:
        query = " ".join(part for part in query.replace('"', " ").split() if part)
        if not query:
            rows = session.exec(select(DocumentChunk, Document).join(Document, Document.id == DocumentChunk.document_id).where(Document.status == "ready").order_by(Document.updated_at.desc()).limit(limit)).all()
            return [RetrievalHit(chunk, document, 0.1, 1.0) for chunk, document in rows]
        try:
            rows = session.connection().exec_driver_sql("SELECT chunk_id, bm25(chunk_fts) AS rank FROM chunk_fts WHERE chunk_fts MATCH ? ORDER BY rank LIMIT ?", (query, limit)).fetchall()
            output: list[RetrievalHit] = []
            for chunk_id, rank in rows:
                chunk = session.get(DocumentChunk, chunk_id)
                document = session.get(Document, chunk.document_id) if chunk else None
                if chunk and document and document.status == "ready":
                    score = 1.0 / (1.0 + max(float(rank), 0.0))
                    output.append(RetrievalHit(chunk, document, score, 1.0))
            if output:
                return output
        except Exception:
            pass
        terms = [normalize_name(term) for term in query.split() if normalize_name(term)]
        documents = session.exec(select(Document).where(Document.status == "ready")).all()
        ranked: list[RetrievalHit] = []
        for document in documents:
            chunks = session.exec(select(DocumentChunk).where(DocumentChunk.document_id == document.id)).all()
            for chunk in chunks:
                haystack = normalize_name(f"{document.title} {document.summary} {chunk.content}")
                score = sum(haystack.count(term) for term in terms) / max(len(terms), 1)
                if score:
                    ranked.append(RetrievalHit(chunk, document, min(1.0, score), 1.0))
        ranked.sort(key=lambda hit: hit.score, reverse=True)
        return ranked[:limit]

    @staticmethod
    def _best_chunk(chunks: list[DocumentChunk], content: str) -> tuple[DocumentChunk, float] | None:
        if not chunks:
            return None
        normalized = normalize_name(content)
        best: tuple[DocumentChunk, float] | None = None
        for chunk in chunks:
            candidate = normalize_name(chunk.content)
            if not candidate:
                continue
            if candidate in normalized or normalized in candidate:
                confidence = 1.0
            else:
                grams = {candidate[i : i + 12] for i in range(0, max(1, len(candidate) - 11), 12)}
                overlap = sum(1 for gram in grams if gram in normalized) / max(len(grams), 1)
                confidence = min(0.95, overlap)
            if best is None or confidence > best[1]:
                best = (chunk, confidence)
        return best if best and best[1] >= 0.2 else None
