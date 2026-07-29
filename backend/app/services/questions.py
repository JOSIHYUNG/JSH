from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.errors import DomainError, not_found
from app.core.text import preview
from app.integrations.openai.responses import OpenAIResponsesGateway
from app.models import ChunkConcept, Concept, Document, QuestionHistory, QuestionSource
from app.schemas.common import QuestionResultResponse, QuestionSourceResponse, RetrievalResponse
from app.services.read_models import concept_summary
from app.services.retrieval import RetrievalResult, RetrievalService
from app.services.jobs import now


class QuestionService:
    def __init__(self, retrieval: RetrievalService, responses: OpenAIResponsesGateway):
        self.retrieval = retrieval
        self.responses = responses

    def ask(self, session: Session, question: str) -> QuestionResultResponse:
        history = QuestionHistory(question=question.strip(), status="retrieving", model_name=get_settings().openai_chat_model, created_at=now())
        session.add(history)
        session.commit()
        session.refresh(history)
        try:
            result = self.retrieval.search(session, question, 3)
            history.retrieval_count = len(result.hits)
            if not result.hits:
                history.status = "no_evidence"
                history.answer_markdown = "저장된 자료에서 관련 근거를 찾지 못했습니다."
                history.completed_at = now()
                session.add(history)
                session.commit()
                return self.to_response(session, history)
            history.status = "generating"
            session.add(history)
            session.commit()
            evidence = [(f"S{index}", hit.chunk.content) for index, hit in enumerate(result.hits, 1)]
            answer = self.responses.grounded_answer(question, evidence)
            history.answer_markdown = answer
            history.answer_language = "ko"
            history.citation_count = sum(answer.count(f"[S{index}]") for index in range(1, len(result.hits) + 1))
            history.status = "completed"
            history.completed_at = now()
            session.add(history)
            for index, hit in enumerate(result.hits, 1):
                session.add(QuestionSource(question_history_id=history.id or 0, rank=index, chunk_id=hit.chunk.id, document_id=hit.document.id, document_title_snapshot=hit.document.title, document_filename_snapshot=hit.document.original_filename, chunk_content_snapshot=hit.chunk.content, start_char_snapshot=hit.chunk.start_char, end_char_snapshot=hit.chunk.end_char, score=hit.score, citation_key=f"S{index}", mapping_confidence=hit.mapping_confidence, current_state="current", created_at=now()))
            session.commit()
            return self.to_response(session, history)
        except Exception:
            history.status = "failed"
            history.error_code = "OPENAI_UNAVAILABLE"
            history.error_message = "질문을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."
            history.completed_at = now()
            session.add(history)
            session.commit()
            return self.to_response(session, history)

    def get(self, session: Session, question_id: int) -> QuestionHistory:
        history = session.get(QuestionHistory, question_id)
        if history is None:
            raise not_found("QUESTION_NOT_FOUND", "질문 기록을 찾을 수 없습니다.")
        return history

    def to_response(self, session: Session, history: QuestionHistory) -> QuestionResultResponse:
        sources = session.exec(select(QuestionSource).where(QuestionSource.question_history_id == history.id).order_by(QuestionSource.rank)).all()
        source_models = [QuestionSourceResponse(rank=source.rank, citation_key=source.citation_key, document_id=source.document_id, chunk_id=source.chunk_id, document_title=source.document_title_snapshot, document_status="ready" if source.current_state == "current" else source.current_state, chunk_preview=preview(source.chunk_content_snapshot), start_char=source.start_char_snapshot, end_char=source.end_char_snapshot, score=source.score, mapping_confidence=source.mapping_confidence, openable=source.document_id is not None and source.current_state == "current") for source in sources]
        concept_ids = []
        for source in sources:
            if source.chunk_id:
                concept_ids.extend(session.exec(select(ChunkConcept.concept_id).where(ChunkConcept.chunk_id == source.chunk_id)).all())
        concepts = []
        for concept_id in dict.fromkeys(value for value in concept_ids if value is not None):
            concept = session.get(Concept, concept_id)
            if concept:
                concepts.append(concept_summary(session, concept))
        retrieval = RetrievalResponse(provider="none" if not sources else "vector_store" if get_settings().openai_api_key else "lexical_fallback", candidate_count=history.retrieval_count, returned_count=len(sources), mapping_failures=0, top_score=max((source.score for source in sources), default=None), used_chunk_ids=[source.chunk_id for source in sources if source.chunk_id is not None])
        return QuestionResultResponse(id=history.id or 0, question=history.question, status=history.status, answer_markdown=history.answer_markdown, answer_language=history.answer_language, sources=source_models, related_concepts=concepts, retrieval=retrieval, created_at=history.created_at, completed_at=history.completed_at)
