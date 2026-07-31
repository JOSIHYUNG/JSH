"""add indexes missing from agent schema

Revision ID: 20260731_0010
Revises: 20260731_0009
"""

from typing import Sequence

from alembic import op


revision: str = "20260731_0010"
down_revision: str | None = "20260731_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_agent_runs_question_history_id", "agent_runs", ["question_history_id"])
    op.create_index("ix_agent_runs_stage", "agent_runs", ["stage"])
    op.create_index("ix_agent_events_sequence", "agent_events", ["sequence"])
    op.create_index("ix_agent_events_event_type", "agent_events", ["event_type"])
    op.create_index("ix_question_web_sources_created_at", "question_web_sources", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_question_web_sources_created_at", table_name="question_web_sources")
    op.drop_index("ix_agent_events_event_type", table_name="agent_events")
    op.drop_index("ix_agent_events_sequence", table_name="agent_events")
    op.drop_index("ix_agent_runs_stage", table_name="agent_runs")
    op.drop_index("ix_agent_runs_question_history_id", table_name="agent_runs")
