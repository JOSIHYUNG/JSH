import asyncio
import io
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pypdf import PdfReader
from sqlmodel import Session, delete, func, select

from app.api.dependencies import agent_run_service, analysis_workflow, document_service, graph_service, question_service, storage, vector_store
from app.core.config import get_settings
from app.core.envelope import ApiResponse, page_meta, success
from app.core.errors import DomainError, not_found
from app.core.text import normalize_text, preview
from app.db import engine, get_session
from app.integrations.filesystem.storage import LocalFileStorage
from app.models import AnalysisJob, AppSetting, ChatConversation, ChunkConcept, Concept, ConceptAlias, ConceptRelation, Document, DocumentChunk, DocumentKeyword, QuestionHistory, QuestionSource
from app.schemas.common import ConversationCreate, ConversationQuestionCreate, ConversationUpdate, ConceptDetailResponse, ConceptRelationResponse, DocumentCreate, DocumentDetailResponse, DocumentUpdate, GraphSnapshot, QuestionCreate, QuestionRerunRequest, ReanalyzeRequest
from app.services.analysis import AnalysisWorkflow
from app.services.agent_runs import AgentRunService
from app.services.documents import DocumentService
from app.services.graph import GraphService
from app.services.jobs import now, job_error
from app.services.questions import QuestionService
from app.services.read_models import chunk_response, concept_summary, document_summary, job_response

router = APIRouter(tags=["knowledge"])


def schedule(background: BackgroundTasks | None, workflow: AnalysisWorkflow, job: AnalysisJob | None) -> None:
    if background is not None and job and job.id:
        background.add_task(workflow.run, job.id)


@router.get("/health")
def health() -> ApiResponse[dict]:
    settings = get_settings()
    return success({"status": "ok", "service": "jsh-backend", "version": settings.app_version})


@router.get("/system/status")
def system_status(session: Session = Depends(get_session)) -> ApiResponse[dict]:
    settings = get_settings()
    try:
        session.exec(select(func.count()).select_from(Document)).one()
        database = "ready"
    except Exception:
        database = "degraded"
    root = LocalFileStorage(settings.storage_root).root
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        file_storage = "ready"
    except OSError:
        file_storage = "degraded"
    running = session.exec(select(func.count()).select_from(AnalysisJob).where(AnalysisJob.status.in_(["queued", "running"]))).one()
    stored_vector_store = session.get(AppSetting, "vector_store_id")
    vector_store_id = settings.openai_vector_store_id or (stored_vector_store.value if stored_vector_store else None)
    vector_store_configured = bool(settings.openai_api_key and (not vector_store_id or vector_store_id.startswith("vs_")))
    return success({"database": database, "file_storage": file_storage, "openai_configured": bool(settings.openai_api_key), "vector_store_configured": vector_store_configured, "analysis_running": int(running), "app_version": settings.app_version})


@router.get("/documents")
def list_documents(status_filter: str | None = Query(None, alias="status"), source_type: Literal["paste", "upload", "ai_generated"] | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), sort: Literal["created_at", "title", "updated_at"] = "created_at", order: Literal["asc", "desc"] = "desc", session: Session = Depends(get_session)) -> ApiResponse[dict]:
    query = select(Document).where(Document.status.notin_(["deleted", "deleting"]))
    if status_filter:
        query = query.where(Document.status.in_([v.strip() for v in status_filter.split(",") if v.strip()]))
    if source_type:
        query = query.where(Document.source_type == source_type)
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    column = {"created_at": Document.created_at, "title": Document.title, "updated_at": Document.updated_at}.get(sort, Document.created_at)
    query = query.order_by(column.asc() if order.lower() == "asc" else column.desc()).offset((page - 1) * page_size).limit(page_size)
    return success({"items": [document_summary(session, item) for item in session.exec(query).all()]}, pagination=page_meta(page, page_size, int(total)))


@router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
def create_document(payload: DocumentCreate, background: BackgroundTasks, session: Session = Depends(get_session), service: DocumentService = Depends(document_service), workflow: AnalysisWorkflow = Depends(analysis_workflow)) -> ApiResponse[dict]:
    document, job = service.create(session, content=payload.content, title=payload.title, source_name=payload.source_name, source_type="paste", media_type="text/plain", auto_analyze=payload.auto_analyze)
    schedule(background, workflow, job)
    return success({"document": document_summary(session, document), "job": job_response(job)})


def decode_upload(filename: str, raw: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.casefold()
    if suffix not in {".txt", ".md", ".pdf"}:
        raise DomainError("UNSUPPORTED_FILE_TYPE", "지원하는 파일은 .txt, .md, .pdf입니다.", 400)
    if suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(raw))
            return normalize_text("\n\n".join(page.extract_text() or "" for page in reader.pages)), "application/pdf"
        except Exception as exc:
            raise DomainError("INVALID_INPUT", "PDF에서 텍스트를 읽지 못했습니다.", 400) from exc
    try:
        return normalize_text(raw.decode("utf-8-sig")), "text/markdown" if suffix == ".md" else "text/plain"
    except UnicodeDecodeError as exc:
        raise DomainError("INVALID_INPUT", "UTF-8 텍스트 파일만 업로드할 수 있습니다.", 400) from exc


@router.post("/documents/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(file: UploadFile = File(...), title: str | None = Form(None), auto_analyze: bool = Form(True), background: BackgroundTasks = None, session: Session = Depends(get_session), service: DocumentService = Depends(document_service), workflow: AnalysisWorkflow = Depends(analysis_workflow)) -> ApiResponse[dict]:
    raw = await file.read()
    if len(raw) > get_settings().max_upload_bytes:
        raise DomainError("INVALID_INPUT", "업로드 파일 크기를 초과했습니다.", 400)
    if not raw:
        raise DomainError("FILE_EMPTY", "비어 있는 파일은 업로드할 수 없습니다.", 400)
    filename = Path(file.filename or "document.txt").name
    allowed_media_types = {
        ".txt": {"text/plain", "application/octet-stream"},
        ".md": {"text/plain", "text/markdown", "application/octet-stream"},
        ".pdf": {"application/pdf", "application/octet-stream"},
    }
    suffix = Path(filename).suffix.casefold()
    if suffix not in allowed_media_types or (file.content_type and file.content_type.casefold() not in allowed_media_types[suffix]):
        raise DomainError("UNSUPPORTED_FILE_TYPE", "파일 확장자와 형식이 지원 범위와 일치하지 않습니다.", 400)
    content, media_type = decode_upload(filename, raw)
    document, job = service.create(session, content=content, title=title, source_name=filename, source_type="upload", media_type=media_type, auto_analyze=auto_analyze)
    schedule(background, workflow, job)
    return success({"document": document_summary(session, document), "job": job_response(job)})


@router.get("/documents/{document_id}")
def get_document(document_id: int, include_chunks: bool = True, include_concepts: bool = True, chunks_page: int = Query(1, ge=1), chunks_page_size: int = Query(20, ge=1, le=100), session: Session = Depends(get_session), service: DocumentService = Depends(document_service)) -> ApiResponse[DocumentDetailResponse]:
    document = service.get(session, document_id)
    all_chunks = session.exec(select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)).all()
    selected = all_chunks[(chunks_page - 1) * chunks_page_size : chunks_page * chunks_page_size] if include_chunks else []
    concepts = []
    if include_concepts and all_chunks:
        ids = session.exec(select(ChunkConcept.concept_id).where(ChunkConcept.chunk_id.in_([c.id for c in all_chunks if c.id is not None]))).all()
        for concept_id in dict.fromkeys(v for v in ids if v is not None):
            concept = session.get(Concept, concept_id)
            if concept:
                concepts.append(concept_summary(session, concept))
    job = session.get(AnalysisJob, document.active_job_id) if document.active_job_id else session.exec(select(AnalysisJob).where(AnalysisJob.document_id == document_id).order_by(AnalysisJob.created_at.desc())).first()
    data = DocumentDetailResponse(document=document_summary(session, document), chunks=[chunk_response(session, c) for c in selected], chunks_pagination=page_meta(chunks_page, chunks_page_size, len(all_chunks)).model_dump(), concepts=concepts, latest_job=job_response(job), source={"storage_available": storage().exists(document.storage_key), "vector_store_status": document.vector_store_status})
    return success(data)


@router.patch("/documents/{document_id}", status_code=status.HTTP_202_ACCEPTED)
def update_document(document_id: int, payload: DocumentUpdate, background: BackgroundTasks, session: Session = Depends(get_session), service: DocumentService = Depends(document_service), workflow: AnalysisWorkflow = Depends(analysis_workflow)) -> ApiResponse[dict]:
    document, job = service.update(session, document_id, title=payload.title, content=payload.content, auto_analyze=payload.auto_analyze)
    schedule(background, workflow, job)
    return success({"document": document_summary(session, document), "job": job_response(job)})


@router.delete("/documents/{document_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_document(document_id: int, background: BackgroundTasks, session: Session = Depends(get_session), service: DocumentService = Depends(document_service)) -> ApiResponse[dict]:
    document = service.request_delete(session, document_id)
    background.add_task(finish_delete, document_id, document.storage_key, document.vector_store_file_id)
    return success({"document_id": document_id, "status": "deleting", "message": "자료 삭제를 처리하고 있습니다."})


def finish_delete(document_id: int, storage_key: str, file_id: str | None) -> None:
    vector_deleted = True
    storage_deleted = True
    try:
        if file_id:
            vector_store().delete(file_id)
    except Exception:
        vector_deleted = False
    try:
        storage().delete(storage_key)
    except (OSError, ValueError):
        storage_deleted = False
    with Session(engine) as session:
        session.connection().exec_driver_sql("DELETE FROM chunk_fts WHERE document_id = ?", (document_id,))
        document = session.get(Document, document_id)
        if document:
            for source in session.exec(select(QuestionSource).where(QuestionSource.document_id == document_id)).all():
                source.current_state = "document_deleted"
                source.chunk_id = None
                source.document_id = None
                session.add(source)
            session.exec(delete(DocumentKeyword).where(DocumentKeyword.document_id == document_id))
            session.exec(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            AnalysisWorkflow._sync_concept_visibility(session)
            document.status = "deleted"
            document.deleted_at = now()
            document.active_job_id = None
            document.vector_store_status = "deleted" if vector_deleted else "failed"
            document.vector_store_error_code = (
                "STORAGE_DELETE_FAILED"
                if not storage_deleted
                else (None if vector_deleted else "OPENAI_UNAVAILABLE")
            )
            document.updated_at = now()
            session.add(document)
            session.commit()


@router.post("/documents/{document_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED)
def reanalyze_document(document_id: int, payload: ReanalyzeRequest | None = None, background: BackgroundTasks = None, session: Session = Depends(get_session), service: DocumentService = Depends(document_service), workflow: AnalysisWorkflow = Depends(analysis_workflow)) -> ApiResponse[dict]:
    document, job = service.request_reanalysis(session, document_id)
    schedule(background, workflow, job)
    return success({"document": document_summary(session, document), "job": job_response(job)})


@router.get("/documents/{document_id}/analysis/events")
async def analysis_events(document_id: int, session: Session = Depends(get_session)) -> StreamingResponse:
    document = session.get(Document, document_id)
    if not document:
        raise not_found("DOCUMENT_NOT_FOUND", "문서를 찾을 수 없습니다.")
    job_id = document.active_job_id or session.exec(select(AnalysisJob.id).where(AnalysisJob.document_id == document_id).order_by(AnalysisJob.created_at.desc())).first()

    async def stream() -> AsyncIterator[str]:
        sequence = 0
        last_signature: tuple | None = None
        last_sent_at = 0.0
        while True:
            with Session(engine) as current:
                job = current.get(AnalysisJob, job_id) if job_id else None
                if not job:
                    return
                terminal = job.status in {"completed", "failed", "canceled"}
                event = "analysis.completed" if job.status == "completed" else "analysis.failed" if job.status == "failed" else "analysis.canceled" if job.status == "canceled" else "analysis.started" if job.status == "queued" else "analysis.progress"
                data = {"job_id": job.id, "document_id": document_id, "stage": job.stage, "progress": job.progress, "message": job.message}
                if job.error_code:
                    data["error"] = {"code": job.error_code, "message": job.error_message or "분석 실패"}
                signature = (job.status, job.stage, job.progress, job.message, job.error_code)
            current_time = time.monotonic()
            if signature != last_signature:
                sequence += 1
                yield f"id: {sequence}\nevent: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                last_signature = signature
                last_sent_at = current_time
            elif current_time - last_sent_at >= 15:
                sequence += 1
                yield f"id: {sequence}\nevent: heartbeat\ndata: {json.dumps({'server_time': now().isoformat() + 'Z'})}\n\n"
                last_sent_at = current_time
            if terminal:
                return
            await asyncio.sleep(get_settings().analysis_poll_interval_seconds)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@router.post("/documents/{document_id}/analysis/cancel", status_code=status.HTTP_202_ACCEPTED)
def cancel_analysis(document_id: int, session: Session = Depends(get_session)) -> ApiResponse[dict]:
    document = session.get(Document, document_id)
    job = session.get(AnalysisJob, document.active_job_id) if document and document.active_job_id else None
    if not job or job.status not in {"queued", "running"}:
        raise DomainError("ANALYSIS_NOT_CANCELABLE", "현재 취소할 수 없는 분석 상태입니다.", 409)
    job.status = "cancel_requested"
    job.cancel_requested_at = now()
    session.add(job)
    session.commit()
    return success({"document_id": document_id, "job_id": job.id, "status": "cancel_requested"})


@router.get("/documents/{document_id}/chunks/{chunk_id}")
def get_chunk(document_id: int, chunk_id: int, session: Session = Depends(get_session)) -> ApiResponse[dict]:
    chunk = session.get(DocumentChunk, chunk_id)
    if not chunk or chunk.document_id != document_id:
        raise not_found("DOCUMENT_NOT_FOUND", "문서 청크를 찾을 수 없습니다.")
    concepts = []
    for concept_id in session.exec(select(ChunkConcept.concept_id).where(ChunkConcept.chunk_id == chunk_id)).all():
        concept = session.get(Concept, concept_id)
        if concept:
            concepts.append(concept_summary(session, concept))
    neighbors = session.exec(select(DocumentChunk).where(DocumentChunk.document_id == document_id, DocumentChunk.chunk_index.in_([chunk.chunk_index - 1, chunk.chunk_index + 1]))).all()
    document = session.get(Document, document_id)
    return success({"chunk": chunk_response(session, chunk), "document_title": document.title if document else "", "concepts": concepts, "neighbors": [chunk_response(session, item) for item in neighbors]})


@router.get("/documents/{document_id}/original")
def get_original(document_id: int, start_char: int = Query(0, ge=0), end_char: int | None = Query(None, ge=0), context_chars: int = Query(1000, ge=0, le=10000), session: Session = Depends(get_session)) -> ApiResponse[dict]:
    document = session.get(Document, document_id)
    if not document or document.status in {"deleted", "deleting"}:
        raise not_found("DOCUMENT_NOT_FOUND", "문서를 찾을 수 없습니다.")
    if not storage().exists(document.storage_key):
        raise DomainError("DOCUMENT_SOURCE_UNAVAILABLE", "원문 파일을 찾을 수 없습니다.", 409)
    content, actual_start, actual_end, total = storage().read_range(document.storage_key, max(0, start_char - context_chars), (end_char + context_chars) if end_char is not None else None)
    return success({"document_id": document_id, "content": content, "start_char": actual_start, "end_char": actual_end, "total_character_count": total, "highlight_start_char": max(0, start_char - actual_start) if end_char is not None else None, "highlight_end_char": min(len(content), end_char - actual_start) if end_char is not None else None})


@router.get("/concepts/{concept_id}")
def get_concept(concept_id: int, include_sources: bool = True, include_related: bool = True, sources_page_size: int = Query(20, ge=1, le=100), session: Session = Depends(get_session)) -> ApiResponse[ConceptDetailResponse]:
    concept = session.get(Concept, concept_id)
    if not concept:
        raise not_found("CONCEPT_NOT_FOUND", "개념을 찾을 수 없습니다.")
    aliases = [{"alias": a.alias, "alias_type": a.alias_type, "source_chunk_id": a.source_chunk_id, "confidence": a.confidence} for a in session.exec(select(ConceptAlias).where(ConceptAlias.concept_id == concept_id)).all()]
    chunks = []
    if include_sources:
        ids = session.exec(select(ChunkConcept.chunk_id).where(ChunkConcept.concept_id == concept_id)).all()[:sources_page_size]
        chunks = [chunk_response(session, c) for value in ids if (c := session.get(DocumentChunk, value))]
    related = []
    if include_related:
        for relation in session.exec(select(ConceptRelation).where((ConceptRelation.source_concept_id == concept_id) | (ConceptRelation.target_concept_id == concept_id))).all():
            other_id = relation.target_concept_id if relation.source_concept_id == concept_id else relation.source_concept_id
            other = session.get(Concept, other_id)
            if other:
                related.append(ConceptRelationResponse(concept=concept_summary(session, other), relation_type=relation.relation_type, strength=relation.strength, evidence_chunk_id=relation.evidence_chunk_id, explanation=relation.explanation))
    return success(ConceptDetailResponse(**concept_summary(session, concept).model_dump(), aliases=aliases, source_chunks=chunks, related_concepts=related))


@router.get("/graph")
def get_graph(include_chunks: bool = False, node_types: str = "document,concept", concept_types: str | None = None, focus_type: str | None = None, focus_id: int | None = None, depth: int = Query(1, ge=1, le=2), recent_days: int | None = Query(None, ge=1), min_strength: float = Query(0, ge=0, le=1), limit_nodes: int | None = Query(None, ge=1, le=2000), limit_edges: int | None = Query(None, ge=1, le=5000), session: Session = Depends(get_session), service: GraphService = Depends(graph_service)) -> ApiResponse[GraphSnapshot]:
    return success(service.build(session, include_chunks=include_chunks, node_types=[v.strip() for v in node_types.split(",") if v.strip()], concept_types=[v.strip() for v in concept_types.split(",")] if concept_types else None, focus_type=focus_type, focus_id=focus_id, depth=depth, recent_days=recent_days, min_strength=min_strength, limit_nodes=limit_nodes, limit_edges=limit_edges))


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate | None = None, session: Session = Depends(get_session), service: QuestionService = Depends(question_service)) -> ApiResponse:
    return success(service.conversation_summary(service.create_conversation(session, payload.title.strip() if payload and payload.title else None)))


@router.get("/conversations")
def list_conversations(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), session: Session = Depends(get_session)) -> ApiResponse[dict]:
    query = select(ChatConversation).where(ChatConversation.status != "deleted")
    total = session.exec(select(func.count()).select_from(ChatConversation).where(ChatConversation.status != "deleted")).one()
    rows = session.exec(
        query.order_by(func.coalesce(ChatConversation.last_turn_at, ChatConversation.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return success({"items": [QuestionService.conversation_summary(row) for row in rows]}, pagination=page_meta(page, page_size, int(total)))


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, session: Session = Depends(get_session), service: QuestionService = Depends(question_service)) -> ApiResponse:
    return success(service.conversation_detail(session, conversation_id))


@router.patch("/conversations/{conversation_id}")
def update_conversation(conversation_id: int, payload: ConversationUpdate, session: Session = Depends(get_session), service: QuestionService = Depends(question_service)) -> ApiResponse:
    conversation = service.get_conversation(session, conversation_id)
    conversation.title = payload.title.strip()
    conversation.title_source = "user"
    conversation.updated_at = now()
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return success(service.conversation_summary(conversation))


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: int, session: Session = Depends(get_session), service: QuestionService = Depends(question_service)) -> None:
    conversation = service.get_conversation(session, conversation_id)
    history_ids = session.exec(select(QuestionHistory.id).where(QuestionHistory.conversation_id == conversation_id)).all()
    ids = [value for value in history_ids if value is not None]
    if ids:
        session.exec(delete(QuestionSource).where(QuestionSource.question_history_id.in_(ids)))
        session.exec(delete(QuestionHistory).where(QuestionHistory.id.in_(ids)))
    session.delete(conversation)
    session.commit()


@router.post("/conversations/{conversation_id}/questions", status_code=status.HTTP_202_ACCEPTED)
def ask_conversation_question(conversation_id: int, payload: ConversationQuestionCreate, background: BackgroundTasks, session: Session = Depends(get_session), service: AgentRunService = Depends(agent_run_service)) -> ApiResponse:
    run, history = service.enqueue(session, payload.question, conversation_id)
    background.add_task(service.orchestrator.run, run.id)
    return success(service.questions.to_response(session, history))


@router.post("/questions", status_code=status.HTTP_202_ACCEPTED)
def ask_question(payload: QuestionCreate, background: BackgroundTasks, session: Session = Depends(get_session), service: AgentRunService = Depends(agent_run_service)) -> ApiResponse:
    run, history = service.enqueue(session, payload.question.strip(), payload.conversation_id)
    background.add_task(service.orchestrator.run, run.id)
    return success(service.questions.to_response(session, history))


@router.get("/questions")
def list_questions(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), session: Session = Depends(get_session)) -> ApiResponse[dict]:
    total = session.exec(select(func.count()).select_from(QuestionHistory)).one()
    rows = session.exec(select(QuestionHistory).order_by(QuestionHistory.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = [{"id": row.id, "conversation_id": row.conversation_id, "turn_index": row.turn_index, "question_preview": preview(row.question, 160), "status": row.status, "answer_preview": preview(row.answer_markdown, 240) if row.answer_markdown else None, "evidence_count": row.retrieval_count, "created_at": row.created_at, "completed_at": row.completed_at} for row in rows]
    return success({"items": items}, pagination=page_meta(page, page_size, int(total)))


@router.get("/questions/{question_id}")
def get_question(question_id: int, session: Session = Depends(get_session), service: QuestionService = Depends(question_service)) -> ApiResponse:
    return success(service.to_response(session, service.get(session, question_id)))


@router.post("/questions/{question_id}/rerun", status_code=status.HTTP_202_ACCEPTED)
def rerun_question(question_id: int, background: BackgroundTasks, payload: QuestionRerunRequest | None = None, session: Session = Depends(get_session), service: AgentRunService = Depends(agent_run_service)) -> ApiResponse:
    original = service.questions.get(session, question_id)
    question = payload.question.strip() if payload and payload.question else original.question
    run, history = service.enqueue(session, question, original.conversation_id)
    background.add_task(service.orchestrator.run, run.id)
    return success(service.questions.to_response(session, history))


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: int, session: Session = Depends(get_session)) -> None:
    history = session.get(QuestionHistory, question_id)
    if not history:
        raise not_found("QUESTION_NOT_FOUND", "대화 기록을 찾을 수 없습니다.")
    session.delete(history)
    session.commit()
