"""add agent runs, events, and web source snapshots

Revision ID: 20260731_0009
Revises: 20260730_0008
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_0009"
down_revision: str | None = "20260730_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_history_id", sa.Integer(), sa.ForeignKey("question_histories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("current_turn", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_turns", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("tool_call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(120), nullable=False, server_default="unknown"),
        sa.Column("stop_reason", sa.String(30)),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column("last_error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("question_history_id", name="uq_agent_run_question"),
    )
    op.create_index("ix_agent_runs_conversation_id", "agent_runs", ["conversation_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])

    op.create_table(
        "agent_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("tool_name", sa.String(40)),
        sa.Column("activity_label", sa.String(500)),
        sa.Column("input_safe_json", sa.Text()),
        sa.Column("output_safe_json", sa.Text()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_event_run_sequence"),
    )
    op.create_index("ix_agent_events_run_id", "agent_events", ["run_id"])
    op.create_index("ix_agent_events_created_at", "agent_events", ["created_at"])

    op.create_table(
        "question_web_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_history_id", sa.Integer(), sa.ForeignKey("question_histories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("citation_key", sa.String(10), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("publisher", sa.String(255)),
        sa.Column("source_rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("question_history_id", "citation_key", name="uq_question_web_source_key"),
    )
    op.create_index("ix_question_web_sources_question_history_id", "question_web_sources", ["question_history_id"])


def downgrade() -> None:
    op.drop_index("ix_question_web_sources_question_history_id", table_name="question_web_sources")
    op.drop_table("question_web_sources")
    op.drop_index("ix_agent_events_created_at", table_name="agent_events")
    op.drop_index("ix_agent_events_run_id", table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index("ix_agent_runs_created_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_conversation_id", table_name="agent_runs")
    op.drop_table("agent_runs")
