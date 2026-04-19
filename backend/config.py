"""Global config + mock-mode detection for VerifAI backend."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend/ regardless of where uvicorn is launched from.
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./verifai.db").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()


def _resolve_llm_provider() -> tuple[str, str, str]:
    configured = os.getenv("LLM_PROVIDER", "").strip().lower()
    if configured == "groq" and GROQ_API_KEY:
        return ("groq", GROQ_API_KEY, GROQ_MODEL)
    if configured == "anthropic" and ANTHROPIC_API_KEY:
        return ("anthropic", ANTHROPIC_API_KEY, ANTHROPIC_MODEL)
    if GROQ_API_KEY:
        return ("groq", GROQ_API_KEY, GROQ_MODEL)
    if ANTHROPIC_API_KEY:
        return ("anthropic", ANTHROPIC_API_KEY, ANTHROPIC_MODEL)
    return ("none", "", "")


LLM_PROVIDER, LLM_API_KEY, LLM_MODEL = _resolve_llm_provider()

# Extension talks from a browser context — allow all origins by default.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# Mock mode: when set, use canned fixtures instead of real API calls.
MOCK_MODE = bool(os.getenv("MOCK_MODE", "").strip())
MOCK_SEARCH = bool(os.getenv("MOCK_SEARCH", "").strip())

# Pipeline limits
MAX_CLAIMS_PER_DOC = int(os.getenv("MAX_CLAIMS_PER_DOC", "12"))
MAX_DOC_CHARS = int(os.getenv("MAX_DOC_CHARS", "15000"))

# Search settings
SEARCH_RESULTS_PER_QUERY = int(os.getenv("SEARCH_RESULTS_PER_QUERY", "5"))
SEARCH_CONCURRENCY = int(os.getenv("SEARCH_CONCURRENCY", "4"))

# Cache directory for search results
CACHE_DIR = os.getenv("CACHE_DIR", str(Path(__file__).resolve().parent / "cache"))
os.makedirs(CACHE_DIR, exist_ok=True)

# Timeouts and retries
CLAIM_TIMEOUT_SECONDS = int(os.getenv("CLAIM_TIMEOUT_SECONDS", "30"))
LLM_CONCURRENCY = int(os.getenv("LLM_CONCURRENCY", "3"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
LLM_RETRY_BASE_SECONDS = float(os.getenv("LLM_RETRY_BASE_SECONDS", "1.0"))
