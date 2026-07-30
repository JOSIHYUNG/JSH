"""add conversations and multi-turn question metadata

Revision ID: 20260730_0006
Revises: 20260730_0005
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0006"
down_revision: str | None = "20260730_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("title_source", sa.String(20), nullable=False, server_default="auto"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_turn_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_chat_conversations_status_last_turn_at",
        "chat_conversations",
        ["status", "last_turn_at"],
    )

    with op.batch_alter_table("question_histories") as batch:
        batch.add_column(sa.Column("conversation_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("turn_index", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("retrieval_query", sa.Text(), nullable=True))
        batch.add_column(sa.Column("context_turn_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("context_truncated", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_foreign_key(
            "fk_question_histories_conversation_id",
            "chat_conversations",
            ["conversation_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Preserve existing single-question history by creating one conversation per row.
    op.execute(
        sa.text(
            """
            INSERT INTO chat_conversations
                (id, title, title_source, status, turn_count, last_turn_at, created_at, updated_at)
            SELECT id,
                   CASE WHEN length(trim(question)) > 80
                        THEN substr(trim(question), 1, 80) || '…'
                        ELSE trim(question) END,
                   'auto',
                   'active',
                   1,
                   created_at,
                   created_at,
                   created_at
            FROM question_histories
            """
        )
    )
    op.execute(sa.text("UPDATE question_histories SET conversation_id = id, turn_index = 1"))

    op.create_index(
        "ix_question_histories_conversation_turn",
        "question_histories",
        ["conversation_id", "turn_index"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_question_histories_conversation_turn", table_name="question_histories")
    with op.batch_alter_table("question_histories") as batch:
        batch.drop_constraint("fk_question_histories_conversation_id", type_="foreignkey")
        batch.drop_column("context_truncated")
        batch.drop_column("context_turn_count")
        batch.drop_column("retrieval_query")
        batch.drop_column("turn_index")
        batch.drop_column("conversation_id")
    op.drop_index("ix_chat_conversations_status_last_turn_at", table_name="chat_conversations")
    op.drop_table("chat_conversations")
