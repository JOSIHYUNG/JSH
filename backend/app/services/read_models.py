import json
from collections import Counter

from sqlmodel import Session, select

from app.core.text import preview
from app.models import AnalysisJob, ChunkConcept, Concept, Document, DocumentChunk, DocumentKeyword
from app.schemas.common import AnalysisJobResponse, ConceptSummary, DocumentChunkResponse, DocumentSummary
from app.services.jobs import job_error


def keywords_for(session: Session, document_id: int) -> list[str]:
    rows = session.exec(select(DocumentKeyword).where(DocumentKeyword.document_id == document_id).order_by(DocumentKeyword.rank)).all()
    return [row.keyword for row in rows]


def counts_for(session: Session, document_id: int) -> tuple[int, int]:
    chunks = session.exec(select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)).all()
    chunk_ids = [value for value in chunks if value is not None]
    if not chunk_ids:
        return 0, 0
    concept_ids = session.exec(select(ChunkConcept.concept_id).where(ChunkConcept.chunk_id.in_(chunk_ids))).all()
    return len(chunk_ids), len(set(concept_ids))


def document_summary(session: Session, document: Document) -> DocumentSummary:
    chunk_count, concept_count = counts_for(session, document.id or 0)
    return DocumentSummary(id=document.id or 0, title=document.title, filename=document.original_filename, source_type=document.source_type, media_type=document.media_type, summary=document.summary, keywords=keywords_for(session, document.id or 0), status=document.status, character_count=document.character_count, chunk_count=chunk_count, concept_count=concept_count, created_at=document.created_at, updated_at=document.updated_at)


def chunk_response(session: Session, chunk: DocumentChunk) -> DocumentChunkResponse:
    concept_ids = session.exec(select(ChunkConcept.concept_id).where(ChunkConcept.chunk_id == chunk.id)).all()
    return DocumentChunkResponse(id=chunk.id or 0, document_id=chunk.document_id, chunk_index=chunk.chunk_index, content=chunk.content, preview=preview(chunk.content), start_char=chunk.start_char, end_char=chunk.end_char, concept_ids=[value for value in concept_ids if value is not None])


def job_response(job: AnalysisJob | None) -> AnalysisJobResponse | None:
    if job is None:
        return None
    return AnalysisJobResponse(id=job.id or 0, document_id=job.document_id, status=job.status, stage=job.stage, progress=job.progress, message=job.message, retry_count=job.retry_count, error=job_error(job), started_at=job.started_at, completed_at=job.completed_at)


def concept_summary(session: Session, concept: Concept) -> ConceptSummary:
    chunk_ids = session.exec(select(ChunkConcept.chunk_id).where(ChunkConcept.concept_id == concept.id)).all()
    document_ids = session.exec(select(DocumentChunk.document_id).where(DocumentChunk.id.in_([v for v in chunk_ids if v is not None]))).all() if chunk_ids else []
    return ConceptSummary(id=concept.id or 0, concept_type=concept.concept_type, canonical_name=concept.canonical_name, english_name=concept.english_name, abbreviation=concept.abbreviation, description=concept.description, document_count=len(set(document_ids)), chunk_count=len(set(chunk_ids)), visibility=concept.visibility)
