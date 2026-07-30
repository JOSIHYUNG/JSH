from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, func, select

from app.core.errors import DomainError, conflict, not_found
from app.core.text import chunk_text, fallback_keywords, normalize_name, normalize_text, sha256_text
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
        document = Document(source_type=source_type, original_filename=source_name, media_type=media_type, storage_key="pending", title=(title or Path(source_name or "자료").stem)[:255], title_source="user" if title and title.strip() else "pending", content_hash=digest, character_count=len(content), status="processing" if auto_analyze else "draft", created_at=now(), updated_at=now())
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

    def create_ai_generated(self, session: Session, *, question: str, answer: str, question_id: int) -> Document:
        """Persist a short general-answer artifact as a searchable document node.

        This intentionally uses the local ingestion primitives without another
        AI analysis pass: the answer already came from the model, so a second
        summarization/concept-extraction call would add latency and token cost.
        """
        content = normalize_text(f"질문\n{question.strip()}\n\nAI 답변\n{answer.strip()}")
        digest = sha256_text(content)
        existing = session.exec(
            select(Document).where(
                Document.content_hash == digest,
                Document.source_type == "ai_generated",
                Document.status != "deleted",
            )
        ).first()
        if existing:
            return existing

        title_question = " ".join(question.split())[:112]
        title = f"AI 생성 답변 · {title_question}"[:255]
        document = Document(
            source_type="ai_generated",
            original_filename=f"ai-generated-{question_id}.md",
            media_type="text/markdown",
            storage_key="pending",
            title=title,
            title_source="generated",
            summary="저장된 근거가 부족한 질문에 대해 AI가 생성한 보완 문서입니다.",
            content_hash=digest,
            character_count=len(content),
            status="ready",
            analysis_version=1,
            created_at=now(),
            updated_at=now(),
        )
        session.add(document)
        session.flush()
        document.storage_key = self.storage.put_document(document.id or 0, document.original_filename, content)
        session.add(document)
        keywords = fallback_keywords(content)
        for rank, keyword in enumerate(dict.fromkeys(keywords), 1):
            value = str(keyword).strip()
            if value:
                session.add(DocumentKeyword(
                    document_id=document.id or 0,
                    normalized_keyword=normalize_name(value),
                    keyword=value[:255],
                    rank=rank,
                    source="ai_generated",
                    created_at=now(),
                ))
        chunks = []
        for index, (start, end, chunk) in enumerate(chunk_text(content)):
            row = DocumentChunk(
                document_id=document.id or 0,
                chunk_index=index,
                start_char=start,
                end_char=end,
                content=chunk,
                character_count=len(chunk),
                content_hash=sha256_text(chunk),
                created_at=now(),
            )
            session.add(row)
            session.flush()
            chunks.append(row)
        connection = session.connection()
        connection.exec_driver_sql("DELETE FROM chunk_fts WHERE document_id = ?", (document.id,))
        for chunk in chunks:
            connection.exec_driver_sql(
                "INSERT INTO chunk_fts(chunk_id, document_id, title, content, keywords) VALUES (?, ?, ?, ?, ?)",
                (chunk.id, document.id, document.title, chunk.content, " ".join(keywords)),
            )
        session.commit()
        session.refresh(document)
        return document

    def get(self, session: Session, document_id: int, *, include_deleted: bool = False) -> Document:
        document = session.get(Document, document_id)
        if document is None or (not include_deleted and document.status in {"deleted", "deleting"}):
            raise not_found("DOCUMENT_NOT_FOUND", "문서를 찾을 수 없습니다.")
        return document

    def request_delete(self, session: Session, document_id: int) -> Document:
        document = self.get(session, document_id)
        if document.status == "deleting":
            raise conflict("DOCUMENT_BUSY", "이미 자료 삭제를 처리하고 있습니다.")
        if document.active_job_id:
            active = session.get(AnalysisJob, document.active_job_id)
            if active and active.status in {"queued", "running"}:
                active.status = "cancel_requested"
                active.cancel_requested_at = now()
                active.updated_at = now()
                session.add(active)
        document.status = "deleting"
        document.updated_at = now()
        session.add(document)
        session.commit()
        return document

    def update(self, session: Session, document_id: int, *, title: str | None, content: str | None, auto_analyze: bool) -> tuple[Document, AnalysisJob | None]:
        document = self.get(session, document_id)
        if document.status == "processing" or document.active_job_id:
            active = session.get(AnalysisJob, document.active_job_id) if document.active_job_id else None
            if active and active.status in {"queued", "running"}:
                raise conflict("DOCUMENT_BUSY", "분석 중인 자료는 분석 완료 후 수정할 수 있습니다.")
        if title is None and content is None:
            raise DomainError("INVALID_INPUT", "수정할 제목 또는 본문을 입력해 주세요.", 400)

        if title is not None:
            clean_title = title.strip()
            if not clean_title:
                raise DomainError("INVALID_INPUT", "제목은 비워둘 수 없습니다.", 400)
            document.title = clean_title[:255]
            document.title_source = "user"

        job = None
        if content is not None:
            normalized_content = normalize_text(content)
            if not normalized_content:
                raise DomainError("FILE_EMPTY", "비어 있는 자료는 저장할 수 없습니다.", 400)
            digest = sha256_text(normalized_content)
            duplicate = session.exec(select(Document).where(Document.content_hash == digest, Document.id != document_id, Document.status != "deleted")).first()
            if duplicate:
                raise conflict("DUPLICATE_DOCUMENT", "동일한 원문이 이미 저장되어 있습니다.", {"document_id": duplicate.id})
            document.content_hash = digest
            document.character_count = len(normalized_content)
            document.summary = ""
            document.vector_store_status = "stale" if document.vector_store_file_id else "not_uploaded"
            document.vector_store_error_code = None
            filename = document.original_filename or f"document-{document_id}.txt"
            document.storage_key = self.storage.put_document(document_id, filename, normalized_content)
            document.analysis_version += 1
            document.status = "processing" if auto_analyze else "draft"
            if auto_analyze:
                job = AnalysisJob(document_id=document_id, status="queued", stage="received", progress=0, message="수정된 자료 분석 대기 중", analysis_version=document.analysis_version, created_at=now(), updated_at=now())
                session.add(job)
                session.flush()
                document.active_job_id = job.id
            else:
                document.active_job_id = None
        document.updated_at = now()
        session.add(document)
        session.commit()
        session.refresh(document)
        if job:
            session.refresh(job)
        return document, job

    def request_reanalysis(self, session: Session, document_id: int) -> tuple[Document, AnalysisJob]:
        document = self.get(session, document_id)
        if document.active_job_id:
            active = session.get(AnalysisJob, document.active_job_id)
            if active and active.status in {"queued", "running"}:
                raise conflict("DOCUMENT_BUSY", "이미 분석 작업이 실행 중입니다.")
        document.status = "processing"
        if document.vector_store_file_id:
            document.vector_store_status = "stale"
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
