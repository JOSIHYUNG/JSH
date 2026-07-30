"""track whether a document title is user-defined

Revision ID: 20260730_0005
Revises: 20260730_0004
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0005"
down_revision: str | None = "20260730_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(
            sa.Column("title_source", sa.String(20), nullable=False, server_default="generated")
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("title_source")
