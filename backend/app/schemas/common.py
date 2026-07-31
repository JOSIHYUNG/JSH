from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DocumentCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1)
    source_name: str | None = Field(default=None, max_length=255)
    auto_analyze: bool = True


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, min_length=1)
    auto_analyze: bool = True


class ReanalyzeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    force_vector_reindex: bool = False


class QuestionCreate(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    conversation_id: int | None = Field(default=None, ge=1)


class QuestionRerunRequest(BaseModel):
    question: str | None = Field(default=None, min_length=2, max_length=1000)


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ConversationQuestionCreate(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class DocumentSummary(SchemaBase):
    id: int
    title: str
    filename: str | None
    source_type: str
    media_type: str
    summary: str
    keywords: list[str]
    status: str
    character_count: int
    chunk_count: int
    concept_count: int
    created_at: datetime
    updated_at: datetime


class DocumentChunkResponse(SchemaBase):
    id: int
    document_id: int
    chunk_index: int
    content: str
    preview: str
    start_char: int
    end_char: int
    concept_ids: list[int]


class AnalysisJobResponse(SchemaBase):
    id: int
    document_id: int
    status: str
    stage: str
    progress: int
    message: str
    retry_count: int
    error: dict[str, str] | None = None
    started_at: datetime | None
    completed_at: datetime | None


class ConceptSummary(SchemaBase):
    id: int
    concept_type: str
    canonical_name: str
    english_name: str | None
    abbreviation: str | None
    description: str
    document_count: int
    chunk_count: int
    visibility: str


class ConceptAliasResponse(BaseModel):
    alias: str
    alias_type: str
    source_chunk_id: int | None
    confidence: float


class ConceptRelationResponse(BaseModel):
    concept: ConceptSummary
    relation_type: str
    strength: float
    evidence_chunk_id: int | None
    explanation: str


class ConceptDetailResponse(ConceptSummary):
    aliases: list[ConceptAliasResponse]
    source_chunks: list[DocumentChunkResponse]
    related_concepts: list[ConceptRelationResponse]


class DocumentDetailResponse(BaseModel):
    document: DocumentSummary
    chunks: list[DocumentChunkResponse]
    chunks_pagination: dict[str, Any]
    concepts: list[ConceptSummary]
    latest_job: AnalysisJobResponse | None
    source: dict[str, Any]


class GraphNode(BaseModel):
    id: str
    entity_type: str
    entity_id: int
    label: str
    subtype: str | None
    size: float
    color_token: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str
    relation_type: str | None
    strength: float
    is_directed: bool
    evidence_chunk_id: int | None


class GraphSnapshot(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    filters: dict[str, Any]
    truncated: bool
    node_count: int
    edge_count: int


class QuestionSourceResponse(BaseModel):
    rank: int
    citation_key: str
    document_id: int | None
    chunk_id: int | None
    document_title: str
    document_status: str
    chunk_preview: str
    start_char: int | None
    end_char: int | None
    score: float
    mapping_confidence: float
    openable: bool


class WebSourceResponse(BaseModel):
    citation_key: str
    url: str
    title: str
    publisher: str | None = None
    rank: int


class RetrievalResponse(BaseModel):
    provider: str
    candidate_count: int
    returned_count: int
    mapping_failures: int
    top_score: float | None
    used_chunk_ids: list[int]


class QuestionResultResponse(BaseModel):
    id: int
    conversation_id: int | None = None
    turn_index: int | None = None
    question: str
    status: str
    answer_markdown: str | None
    answer_mode: str
    answer_language: str | None
    sources: list[QuestionSourceResponse]
    web_sources: list[WebSourceResponse] = Field(default_factory=list)
    related_concepts: list[ConceptSummary]
    retrieval: RetrievalResponse
    error: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    generated_document: DocumentSummary | None = None
    created_at: datetime
    completed_at: datetime | None


class ConversationSummaryResponse(BaseModel):
    id: int
    title: str
    title_source: str
    status: str
    turn_count: int
    last_turn_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(BaseModel):
    conversation: ConversationSummaryResponse
    turns: list[QuestionResultResponse]


class QuestionHistorySummaryResponse(BaseModel):
    id: int
    question_preview: str
    status: str
    answer_preview: str | None
    evidence_count: int
    created_at: datetime
    completed_at: datetime | None
