from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.settings import AppState

router = APIRouter(prefix="/observe", tags=["observe"])


def _authorized_state(request: Request, token: str) -> AppState:
    state: AppState = request.app.state.uf
    expected = state.settings.spectator_token
    if not state.settings.observe or not expected or not secrets.compare_digest(token or "", expected):
        raise HTTPException(status_code=401)
    return state


@router.get("/history")
def history(request: Request, token: str = "", after_seq: int = 0) -> list[dict[str, Any]]:
    state = _authorized_state(request, token)
    return state.bus.since(after_seq)


@router.get("/stream")
async def stream(request: Request, token: str = "") -> StreamingResponse:
    state = _authorized_state(request, token)
    queue = state.bus.subscribe()

    async def events() -> AsyncIterator[str]:
        try:
            yield ": connected\n\n"
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"event: observation\ndata: {json.dumps(event)}\n\n"
        finally:
            state.bus.unsubscribe(queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
