"""persist question retrieval metadata

Revision ID: 20260730_0004
Revises: 20260729_0003
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0004"
down_revision: str | None = "20260729_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("question_histories") as batch:
        batch.add_column(sa.Column("retrieval_provider", sa.String(30), nullable=False, server_default="none"))
        batch.add_column(sa.Column("retrieval_candidate_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("retrieval_mapping_failures", sa.Integer(), nullable=False, server_default="0"))
    op.create_index(
        "uq_concept_alias_identity",
        "concept_aliases",
        ["concept_id", "normalized_alias", "alias_type"],
        unique=True,
    )
    op.create_index(
        "uq_concept_relation_evidence",
        "concept_relations",
        ["source_concept_id", "target_concept_id", "relation_type", "evidence_chunk_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_concept_relation_evidence", table_name="concept_relations")
    op.drop_index("uq_concept_alias_identity", table_name="concept_aliases")
    with op.batch_alter_table("question_histories") as batch:
        batch.drop_column("retrieval_mapping_failures")
        batch.drop_column("retrieval_candidate_count")
        batch.drop_column("retrieval_provider")
