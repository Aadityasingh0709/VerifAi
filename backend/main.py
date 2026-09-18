"""FastAPI entry point for the VerifAI backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CORS_ORIGINS, MOCK_MODE, MOCK_SEARCH
from backend.routers.audit import router as audit_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="VerifAI",
        description="Real-Time Hallucination Audit Trail for AI-Generated Text",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(audit_router)

    @app.get("/")
    def root():
        return {
            "name": "VerifAI",
            "status": "ok",
            "mock_mode": MOCK_MODE,
            "mock_search": MOCK_SEARCH,
        }

    @app.get("/healthz")
    def health():
        return {"ok": True}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
