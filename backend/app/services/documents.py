from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, func, select

from app.core.errors import DomainError, conflict, not_found
from app.core.text import normalize_text, sha256_text
from app.integrations.filesystem.storage import LocalFileStorage
from app.models import AnalysisJob, Document, DocumentChunk, DocumentKeyword
from app.services.jobs import now
from app.services.read_models import document_summary, job_response


class DocumentService:
    def __init__(self, storage: LocalFileStorage):
        self.storage = storage

    def create(self, session: Session, *, content: str, title: str | None, source_name: str | None, source_type: str, media_type: str, auto_analyze: bool) -> tuple[Document, AnalysisJob | None]:
        content = normalize_text(content)
        if not content:
            raise DomainError("FILE_EMPTY", "비어 있는 자료는 저장할 수 없습니다.", 400)
        digest = sha256_text(content)
        duplicate = session.exec(select(Document).where(Document.content_hash == digest, Document.status != "deleted")).first()
        if duplicate:
            raise conflict("DUPLICATE_DOCUMENT", "동일한 원문이 이미 저장되어 있습니다.", {"document_id": duplicate.id})
        document = Document(source_type=source_type, original_filename=source_name, media_type=media_type, storage_key="pending", title=(title or Path(source_name or "자료").stem)[:255], content_hash=digest, character_count=len(content), status="processing" if auto_analyze else "draft", created_at=now(), updated_at=now())
        session.add(document)
        session.flush()
        document.storage_key = self.storage.put_document(document.id or 0, source_name or f"document-{document.id}.txt", content)
        job = None
        if auto_analyze:
            job = AnalysisJob(document_id=document.id or 0, status="queued", stage="received", progress=0, message="분석 대기 중", analysis_version=document.analysis_version + 1, created_at=now(), updated_at=now())
            session.add(job)
            session.flush()
            document.active_job_id = job.id
        session.add(document)
        session.commit()
        session.refresh(document)
        if job:
            session.refresh(job)
        return document, job

    def get(self, session: Session, document_id: int, *, include_deleted: bool = False) -> Document:
        document = session.get(Document, document_id)
        if document is None or (not include_deleted and document.status in {"deleted", "deleting"}):
            raise not_found("DOCUMENT_NOT_FOUND", "문서를 찾을 수 없습니다.")
        return document

    def request_delete(self, session: Session, document_id: int) -> Document:
        document = self.get(session, document_id)
        if document.status == "processing":
            raise conflict("DOCUMENT_BUSY", "분석 중인 문서는 분석 완료 후 삭제할 수 있습니다.")
        document.status = "deleting"
        document.updated_at = now()
        session.add(document)
        session.commit()
        return document

    def request_reanalysis(self, session: Session, document_id: int) -> tuple[Document, AnalysisJob]:
        document = self.get(session, document_id)
        if document.active_job_id:
            active = session.get(AnalysisJob, document.active_job_id)
            if active and active.status in {"queued", "running"}:
                raise conflict("DOCUMENT_BUSY", "이미 분석 작업이 실행 중입니다.")
        document.status = "processing"
        document.analysis_version += 1
        document.updated_at = now()
        job = AnalysisJob(document_id=document.id or 0, status="queued", stage="received", progress=0, message="재분석 대기 중", analysis_version=document.analysis_version, created_at=now(), updated_at=now())
        session.add(job)
        session.flush()
        document.active_job_id = job.id
        session.add(document)
        session.commit()
        session.refresh(document)
        session.refresh(job)
        return document, job
