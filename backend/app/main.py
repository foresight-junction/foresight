from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.mcp_server import build_mcp
from app.routers import admin, observe
from app.settings import AppState, Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    state = AppState(settings)
    mcp_app = build_mcp(state).http_app(path="/mcp")

    app = FastAPI(title="Unfindable", lifespan=mcp_app.lifespan)
    app.state.uf = state
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET"],
        allow_headers=[],
    )

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(observe.router)
    app.include_router(admin.router)
    app.mount("/", mcp_app)
    return app


app = create_app()
