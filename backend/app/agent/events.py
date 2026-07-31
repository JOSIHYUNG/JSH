import json
from typing import Any

from sqlmodel import Session, select

from app.agent.contracts import safe_json
from app.models import AgentEvent, AgentRun
from app.services.jobs import now


def append_event(
    session: Session,
    run: AgentRun,
    event_type: str,
    *,
    turn: int = 0,
    tool_name: str | None = None,
    label: str | None = None,
    input_safe: Any = None,
    output_safe: Any = None,
    error_code: str | None = None,
    duration_ms: int | None = None,
) -> AgentEvent:
    last = session.exec(
        select(AgentEvent.sequence).where(AgentEvent.run_id == run.id).order_by(AgentEvent.sequence.desc())
    ).first()
    event = AgentEvent(
        run_id=run.id or 0,
        sequence=(last or 0) + 1,
        turn=turn,
        event_type=event_type,
        tool_name=tool_name,
        activity_label=label,
        input_safe_json=safe_json(input_safe) if input_safe is not None else None,
        output_safe_json=safe_json(output_safe) if output_safe is not None else None,
        error_code=error_code,
        duration_ms=duration_ms,
        created_at=now(),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def safe_event_payload(event: AgentEvent) -> dict[str, Any]:
    input_data = json.loads(event.input_safe_json) if event.input_safe_json else {}
    output_data = json.loads(event.output_safe_json) if event.output_safe_json else {}
    return {
        "sequence": event.sequence,
        "run_id": event.run_id,
        "turn": event.turn,
        "type": event.event_type,
        "tool": event.tool_name,
        "label": event.activity_label,
        "status": _status(event.event_type),
        "query_preview": input_data.get("query_preview"),
        "node_labels": input_data.get("node_labels", []),
        "result_count": output_data.get("result_count"),
        "error_code": event.error_code,
        "created_at": event.created_at,
    }


def _status(event_type: str) -> str | None:
    if event_type.endswith("started") or event_type == "model_started":
        return "started"
    if event_type.endswith("completed") or event_type == "run_completed":
        return "completed"
    if event_type.endswith("failed") or event_type in {"run_failed", "run_max_turns", "run_canceled"}:
        return "failed" if event_type == "run_failed" else "terminal"
    return None
