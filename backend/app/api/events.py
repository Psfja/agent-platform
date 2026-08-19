from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.database import get_db
from app.services.event_bus import project_events

router = APIRouter(tags=["events"])


@router.get("/projects/{project_id}/events", response_class=StreamingResponse)
async def project_event_stream(project_id: str, request: Request, db: Session = Depends(get_db)) -> StreamingResponse:
    get_project_or_404(db, project_id)

    async def stream():
        connected = {"event": "connected", "projectId": project_id, "data": {"message": "SSE connected"}}
        yield f"event: connected\ndata: {json.dumps(connected, ensure_ascii=False)}\n\n"
        async with project_events.subscribe(project_id) as queue:
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield project_events.encode(event)
                except TimeoutError:
                    yield ": heartbeat\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
