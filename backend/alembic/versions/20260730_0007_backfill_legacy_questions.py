"""backfill questions created by a legacy server into conversations

Revision ID: 20260730_0007
Revises: 20260730_0006
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0007"
down_revision: str | None = "20260730_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, question, created_at
            FROM question_histories
            WHERE conversation_id IS NULL
            ORDER BY id
            """
        )
    ).mappings().all()

    for row in rows:
        question = (row["question"] or "새 대화").strip()
        title = question[:80]
        result = bind.execute(
            sa.text(
                """
                INSERT INTO chat_conversations
                    (title, title_source, status, turn_count, last_turn_at, created_at, updated_at)
                VALUES (:title, 'auto', 'active', 1, :created_at, :created_at, :created_at)
                """
            ),
            {"title": title, "created_at": row["created_at"]},
        )
        conversation_id = result.lastrowid
        bind.execute(
            sa.text(
                """
                UPDATE question_histories
                SET conversation_id = :conversation_id, turn_index = 1
                WHERE id = :history_id
                """
            ),
            {"conversation_id": conversation_id, "history_id": row["id"]},
        )


def downgrade() -> None:
    # The rows are valid conversation history after backfill; retain them on downgrade.
    pass
