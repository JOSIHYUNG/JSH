"""create knowledge documents and chunks

Revision ID: 20260729_0002
Revises: 20260729_0001
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_0002"
down_revision: Union[str, Sequence[str], None] = "20260729_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("keywords_json", sa.String(), nullable=False),
        sa.Column("embedding_json", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "knowledgechunk",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_json", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledgechunk_document_id"), "knowledgechunk", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledgechunk_document_id"), table_name="knowledgechunk")
    op.drop_table("knowledgechunk")
    op.drop_table("document")
