from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: int | None = Field(default=None, primary_key=True)
    source_type: str = Field(index=True, max_length=20)
    original_filename: str | None = Field(default=None, max_length=255)
    media_type: str = Field(default="text/plain", max_length=120)
    storage_key: str = Field(max_length=500, unique=True)
    title: str = Field(max_length=255)
    summary: str = ""
    content_hash: str = Field(max_length=64, index=True)
    character_count: int = 0
    status: str = Field(default="draft", index=True, max_length=30)
    analysis_version: int = 0
    active_job_id: int | None = Field(default=None, index=True)
    vector_store_file_id: str | None = Field(default=None, index=True, max_length=120)
    vector_store_status: str = Field(default="not_uploaded", max_length=30)
    vector_store_error_code: str | None = Field(default=None, max_length=80)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: datetime | None = None


class DocumentChunk(SQLModel, table=True):
    __tablename__ = "document_chunks"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    chunk_index: int = Field(index=True)
    start_char: int
    end_char: int
    content: str
    character_count: int
    content_hash: str = Field(max_length=64, index=True)
    created_at: datetime = Field(default_factory=utc_now)


class DocumentKeyword(SQLModel, table=True):
    __tablename__ = "document_keywords"

    document_id: int = Field(foreign_key="documents.id", primary_key=True)
    normalized_keyword: str = Field(primary_key=True, max_length=255)
    keyword: str = Field(max_length=255)
    rank: int = 0
    source: str = Field(default="ai", max_length=30)
    created_at: datetime = Field(default_factory=utc_now)


class Concept(SQLModel, table=True):
    __tablename__ = "concepts"

    id: int | None = Field(default=None, primary_key=True)
    concept_type: str = Field(index=True, max_length=40)
    canonical_name: str = Field(max_length=255)
    english_name: str | None = Field(default=None, max_length=255)
    abbreviation: str | None = Field(default=None, max_length=100)
    normalized_name: str = Field(index=True, max_length=255)
    description: str = Field(default="", max_length=500)
    merge_confidence: float = 1.0
    visibility: str = Field(default="visible", index=True, max_length=20)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ConceptAlias(SQLModel, table=True):
    __tablename__ = "concept_aliases"

    id: int | None = Field(default=None, primary_key=True)
    concept_id: int = Field(foreign_key="concepts.id", index=True)
    alias: str = Field(max_length=255)
    normalized_alias: str = Field(index=True, max_length=255)
    alias_type: str = Field(max_length=30)
    source_chunk_id: int | None = Field(default=None, foreign_key="document_chunks.id")
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=utc_now)


class ChunkConcept(SQLModel, table=True):
    __tablename__ = "chunk_concepts"

    chunk_id: int = Field(foreign_key="document_chunks.id", primary_key=True)
    concept_id: int = Field(foreign_key="concepts.id", primary_key=True)
    mention: str = Field(primary_key=True, max_length=255)
    mention_start: int | None = None
    mention_end: int | None = None
    extraction_confidence: float = 1.0
    description_snapshot: str = Field(default="", max_length=500)
    created_at: datetime = Field(default_factory=utc_now)


class ConceptRelation(SQLModel, table=True):
    __tablename__ = "concept_relations"

    id: int | None = Field(default=None, primary_key=True)
    source_concept_id: int = Field(foreign_key="concepts.id", index=True)
    target_concept_id: int = Field(foreign_key="concepts.id", index=True)
    relation_type: str = Field(max_length=80)
    is_directed: bool = True
    strength: float = 0.5
    extraction_confidence: float = 0.5
    explanation: str = Field(default="", max_length=500)
    evidence_chunk_id: int | None = Field(default=None, foreign_key="document_chunks.id", index=True)
    visibility: str = Field(default="visible", max_length=20)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AnalysisJob(SQLModel, table=True):
    __tablename__ = "analysis_jobs"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    status: str = Field(default="queued", index=True, max_length=30)
    stage: str = Field(default="received", max_length=50)
    progress: int = 0
    message: str = ""
    analysis_version: int = 1
    retry_count: int = 0
    error_code: str | None = Field(default=None, max_length=80)
    error_message: str | None = None
    cancel_requested_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)


class QuestionHistory(SQLModel, table=True):
    __tablename__ = "question_histories"

    id: int | None = Field(default=None, primary_key=True)
    question: str
    status: str = Field(default="queued", index=True, max_length=30)
    answer_markdown: str | None = None
    answer_language: str | None = Field(default=None, max_length=10)
    model_name: str | None = Field(default=None, max_length=120)
    retrieval_count: int = 0
    citation_count: int = 0
    error_code: str | None = Field(default=None, max_length=80)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    completed_at: datetime | None = None


class QuestionSource(SQLModel, table=True):
    __tablename__ = "question_sources"

    id: int | None = Field(default=None, primary_key=True)
    question_history_id: int = Field(foreign_key="question_histories.id", index=True)
    rank: int
    chunk_id: int | None = Field(default=None, foreign_key="document_chunks.id")
    document_id: int | None = Field(default=None, foreign_key="documents.id")
    document_title_snapshot: str
    document_filename_snapshot: str | None = None
    chunk_content_snapshot: str
    start_char_snapshot: int | None = None
    end_char_snapshot: int | None = None
    score: float = 0.0
    citation_key: str
    mapping_confidence: float = 0.0
    current_state: str = "current"
    created_at: datetime = Field(default_factory=utc_now)


class AppSetting(SQLModel, table=True):
    __tablename__ = "app_settings"

    key: str = Field(primary_key=True, max_length=100)
    value: str
    updated_at: datetime = Field(default_factory=utc_now)
