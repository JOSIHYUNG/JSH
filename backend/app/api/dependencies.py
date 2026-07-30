from app.core.config import get_settings
from app.integrations.filesystem.storage import LocalFileStorage
from app.integrations.openai.responses import OpenAIResponsesGateway
from app.integrations.openai.vector_store import OpenAIVectorStoreGateway
from app.db import engine
from app.models import AppSetting
from sqlmodel import Session
from app.services.analysis import AnalysisWorkflow
from app.services.documents import DocumentService
from app.services.graph import GraphService
from app.services.questions import QuestionService
from app.services.retrieval import RetrievalService


def storage() -> LocalFileStorage:
    return LocalFileStorage(get_settings().storage_root)


def vector_store() -> OpenAIVectorStoreGateway:
    vector_store_id = get_settings().openai_vector_store_id
    if not vector_store_id:
        with Session(engine) as session:
            setting = session.get(AppSetting, "vector_store_id")
            vector_store_id = setting.value if setting else None
    return OpenAIVectorStoreGateway(vector_store_id)


def analysis_workflow() -> AnalysisWorkflow:
    return AnalysisWorkflow(storage(), vector_store(), OpenAIResponsesGateway())


def document_service() -> DocumentService:
    return DocumentService(storage())


def question_service() -> QuestionService:
    return QuestionService(RetrievalService(vector_store()), OpenAIResponsesGateway(), DocumentService(storage()))


def graph_service() -> GraphService:
    return GraphService()
