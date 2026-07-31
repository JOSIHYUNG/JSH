import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.dependencies import agent_run_service
from app.core.envelope import ApiResponse, success
from app.core.errors import not_found
from app.db import engine, get_session
from app.models import AgentRun
from app.schemas.agent import AgentRunCreate
from app.services.agent_runs import AgentRunService


router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
def create_agent_run(payload: AgentRunCreate, background: BackgroundTasks, session: Session = Depends(get_session), service: AgentRunService = Depends(agent_run_service)) -> ApiResponse:
    run, _history = service.enqueue(session, payload.question, payload.conversation_id)
    background.add_task(service.orchestrator.run, run.id)
    return success(service.summary(session, run))


@router.post("/conversations/{conversation_id}/agent-runs", status_code=status.HTTP_202_ACCEPTED)
def create_conversation_agent_run(conversation_id: int, payload: AgentRunCreate, background: BackgroundTasks, session: Session = Depends(get_session), service: AgentRunService = Depends(agent_run_service)) -> ApiResponse:
    run, _history = service.enqueue(session, payload.question, conversation_id)
    background.add_task(service.orchestrator.run, run.id)
    return success(service.summary(session, run))


@router.get("/runs/{run_id}")
def get_agent_run(run_id: int, session: Session = Depends(get_session), service: AgentRunService = Depends(agent_run_service)) -> ApiResponse:
    return success(service.result_payload(session, service.get(session, run_id)))


@router.post("/runs/{run_id}/cancel")
def cancel_agent_run(run_id: int, session: Session = Depends(get_session), service: AgentRunService = Depends(agent_run_service)) -> ApiResponse:
    return success(service.summary(session, service.cancel(session, run_id)))


@router.get("/runs/{run_id}/events")
async def agent_events(run_id: int, last_event_id: str | None = Header(default=None, alias="Last-Event-ID"), after: int = Query(0, ge=0), service: AgentRunService = Depends(agent_run_service)) -> StreamingResponse:
    initial_sequence = max(after, int(last_event_id or 0))
    with Session(engine) as session:
        service.get(session, run_id)

    async def stream() -> AsyncIterator[str]:
        sequence = initial_sequence
        idle = 0
        while idle < 600:
            with Session(engine) as session:
                run = service.get(session, run_id)
                events = service.events(session, run_id, sequence)
                for event in events:
                    sequence = event.sequence
                    yield f"id: {sequence}\nevent: activity\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                if run.status in {"completed", "failed", "canceled", "max_turns"}:
                    return
            idle += 1
            if idle % 30 == 0:
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
