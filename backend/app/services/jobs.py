from datetime import datetime, timezone

from sqlmodel import Session, select

from app.db import engine
from app.models import AnalysisJob, Document, DocumentChunk, QuestionHistory


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def update_job(session: Session, job_id: int, *, status: str | None = None, stage: str | None = None, progress: int | None = None, message: str | None = None, error_code: str | None = None, error_message: str | None = None) -> AnalysisJob:
    job = session.get(AnalysisJob, job_id)
    if job is None:
        raise ValueError("analysis job not found")
    if status:
        job.status = status
        if status == "running" and job.started_at is None:
            job.started_at = now()
        if status in {"completed", "failed", "canceled"}:
            job.completed_at = now()
    if stage is not None:
        job.stage = stage
    if progress is not None:
        job.progress = max(0, min(100, progress))
    if message is not None:
        job.message = message
    if error_code is not None:
        job.error_code = error_code
    if error_message is not None:
        job.error_message = error_message
    job.updated_at = now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def job_error(job: AnalysisJob) -> dict[str, str] | None:
    if not job.error_code and not job.error_message:
        return None
    return {"code": job.error_code or "INTERNAL_ERROR", "message": job.error_message or "분석 작업이 실패했습니다."}


def recover_interrupted_jobs() -> int:
    """Turn process-local work into an explicit retryable state after restart."""
    recovered = 0
    with Session(engine) as session:
        jobs = session.exec(
            select(AnalysisJob).where(
                AnalysisJob.status.in_(["queued", "running", "cancel_requested"])
            )
        ).all()
        for job in jobs:
            job.status = "failed"
            job.stage = "failed"
            job.error_code = "SERVICE_RESTARTED"
            job.error_message = "서버가 다시 시작되어 분석이 중단되었습니다. 다시 분석해 주세요."
            job.completed_at = now()
            job.updated_at = now()
            document = session.get(Document, job.document_id)
            if document and document.active_job_id == job.id:
                has_result = session.exec(
                    select(DocumentChunk.id)
                    .where(DocumentChunk.document_id == document.id)
                    .limit(1)
                ).first() is not None
                document.status = "ready" if has_result else "failed"
                document.active_job_id = None
                document.updated_at = now()
                session.add(document)
            session.add(job)
            recovered += 1
        session.commit()
    return recovered


def recover_interrupted_questions() -> int:
    """Mark in-process question turns failed after a server restart."""
    recovered = 0
    with Session(engine) as session:
        rows = session.exec(
            select(QuestionHistory).where(
                QuestionHistory.status.in_(["queued", "retrieving", "generating"])
            )
        ).all()
        for history in rows:
            history.status = "failed"
            history.error_code = "SERVICE_RESTARTED"
            history.error_message = "서버가 다시 시작되어 질문 처리가 중단되었습니다. 다시 시도해 주세요."
            history.completed_at = now()
            session.add(history)
            recovered += 1
        session.commit()
    return recovered
