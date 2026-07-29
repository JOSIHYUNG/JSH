"""create second brain schema

Revision ID: 20260729_0003
Revises: 20260729_0002
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_0003"
down_revision: str | None = "20260729_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _table(name: str, *columns: sa.Column, **kwargs) -> None:
    op.create_table(name, *columns, **kwargs)


def upgrade() -> None:
    _table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("analysis_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_job_id", sa.Integer()),
        sa.Column("vector_store_file_id", sa.String(120)),
        sa.Column("vector_store_status", sa.String(30), nullable=False, server_default="not_uploaded"),
        sa.Column("vector_store_error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime()),
    )
    _table(
        "document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    _table(
        "document_keywords",
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("normalized_keyword", sa.String(255), primary_key=True),
        sa.Column("keyword", sa.String(255), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    _table(
        "concepts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("concept_type", sa.String(40), nullable=False),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("english_name", sa.String(255)),
        sa.Column("abbreviation", sa.String(100)),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("merge_confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="visible"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    _table(
        "concept_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("concept_id", sa.Integer(), sa.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("normalized_alias", sa.String(255), nullable=False),
        sa.Column("alias_type", sa.String(30), nullable=False),
        sa.Column("source_chunk_id", sa.Integer(), sa.ForeignKey("document_chunks.id", ondelete="SET NULL")),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    _table(
        "chunk_concepts",
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("document_chunks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("concept_id", sa.Integer(), sa.ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("mention", sa.String(255), primary_key=True),
        sa.Column("mention_start", sa.Integer()),
        sa.Column("mention_end", sa.Integer()),
        sa.Column("extraction_confidence", sa.Float(), nullable=False),
        sa.Column("description_snapshot", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    _table(
        "concept_relations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_concept_id", sa.Integer(), sa.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_concept_id", sa.Integer(), sa.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(80), nullable=False),
        sa.Column("is_directed", sa.Boolean(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("extraction_confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.String(500), nullable=False),
        sa.Column("evidence_chunk_id", sa.Integer(), sa.ForeignKey("document_chunks.id", ondelete="CASCADE")),
        sa.Column("visibility", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    _table(
        "analysis_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("analysis_version", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.Column("cancel_requested_at", sa.DateTime()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    _table(
        "question_histories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("answer_markdown", sa.Text()),
        sa.Column("answer_language", sa.String(10)),
        sa.Column("model_name", sa.String(120)),
        sa.Column("retrieval_count", sa.Integer(), nullable=False),
        sa.Column("citation_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
    )
    _table(
        "question_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_history_id", sa.Integer(), sa.ForeignKey("question_histories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("document_chunks.id", ondelete="SET NULL")),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("document_title_snapshot", sa.Text(), nullable=False),
        sa.Column("document_filename_snapshot", sa.String(255)),
        sa.Column("chunk_content_snapshot", sa.Text(), nullable=False),
        sa.Column("start_char_snapshot", sa.Integer()),
        sa.Column("end_char_snapshot", sa.Integer()),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("citation_key", sa.String(10), nullable=False),
        sa.Column("mapping_confidence", sa.Float(), nullable=False),
        sa.Column("current_state", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("question_history_id", "rank"),
        sa.UniqueConstraint("question_history_id", "citation_key"),
    )
    _table("app_settings", sa.Column("key", sa.String(100), primary_key=True), sa.Column("value", sa.Text(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))

    indexes = [
        ("ix_documents_status_created", "documents", ["status", "created_at"]),
        ("ix_documents_content_hash_active", "documents", ["content_hash"]),
        ("ix_chunks_document_offset", "document_chunks", ["document_id", "start_char"]),
        ("ix_concepts_type_name", "concepts", ["concept_type", "normalized_name"]),
        ("ix_aliases_normalized", "concept_aliases", ["normalized_alias"]),
        ("ix_relations_pair", "concept_relations", ["source_concept_id", "target_concept_id"]),
        ("ix_jobs_document_created", "analysis_jobs", ["document_id", "created_at"]),
    ]
    for name, table, columns in indexes:
        op.create_index(name, table, columns)
    op.execute("CREATE UNIQUE INDEX ix_documents_active_hash ON documents(content_hash) WHERE status != 'deleted'")
    op.execute("CREATE VIRTUAL TABLE chunk_fts USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, title, content, keywords, tokenize='unicode61')")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunk_fts")
    for table in ["app_settings", "question_sources", "question_histories", "analysis_jobs", "concept_relations", "chunk_concepts", "concept_aliases", "concepts", "document_keywords", "document_chunks", "documents"]:
        op.drop_table(table)
