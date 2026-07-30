"""store answer mode and generated AI document links

Revision ID: 20260730_0008
Revises: 20260730_0007
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0008"
down_revision: str | None = "20260730_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("question_histories") as batch:
        batch.add_column(sa.Column("answer_mode", sa.String(20), nullable=False, server_default="grounded"))
        batch.add_column(sa.Column("generated_document_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_question_histories_generated_document_id",
            "documents",
            ["generated_document_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_question_histories_generated_document_id", ["generated_document_id"])


def downgrade() -> None:
    with op.batch_alter_table("question_histories") as batch:
        batch.drop_index("ix_question_histories_generated_document_id")
        batch.drop_constraint("fk_question_histories_generated_document_id", type_="foreignkey")
        batch.drop_column("generated_document_id")
        batch.drop_column("answer_mode")
