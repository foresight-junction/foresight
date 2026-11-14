from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.schemas import ResetRequest
from app.settings import AppState

router = APIRouter(prefix="/admin", tags=["admin"])


def _authorized_state(request: Request, token: str) -> AppState:
    state: AppState = request.app.state.uf
    if not state.settings.verifier_token or not secrets.compare_digest(
        token or "", state.settings.verifier_token
    ):
        raise HTTPException(status_code=401, detail="unauthorized")
    return state


@router.post("/finalize")
def finalize(request: Request, x_verifier_token: str = Header(default="")) -> dict[str, Any]:
    """Evaluator-side. Freezes the episode and returns reward and report. Not an MCP tool."""
    state = _authorized_state(request, x_verifier_token)
    return state.service.finalize()


@router.post("/reset")
def reset(request: Request, body: ResetRequest, x_verifier_token: str = Header(default="")) -> dict[str, Any]:
    """Operator-side. Starts a new episode, for demos and repeated local runs."""
    state = _authorized_state(request, x_verifier_token)
    try:
        service = state.reset(body.scenario, body.seed, body.profile)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from None
    return {
        "episode_id": service.episode_id,
        "scenario": service.world.name,
        "profile": service.profile.name,
        "total_requests": len(service.requests),
    }
