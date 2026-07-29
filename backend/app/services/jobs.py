from datetime import datetime, timezone

from sqlmodel import Session

from app.models import AnalysisJob, Document


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
