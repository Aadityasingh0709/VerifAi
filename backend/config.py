"""Global config + mock-mode detection for VerifAI backend."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Prefer backend/.env, then accept a project-root .env for the documented quick start.
_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR.parent / ".env")
load_dotenv(_BACKEND_DIR / ".env", override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./verifai.db").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()


def _resolve_llm_provider() -> tuple[str, str, str]:
    configured = os.getenv("LLM_PROVIDER", "").strip().lower()
    if configured == "groq" and GROQ_API_KEY:
        return ("groq", GROQ_API_KEY, GROQ_MODEL)
    if configured == "gemini" and GEMINI_API_KEY:
        return ("gemini", GEMINI_API_KEY, GEMINI_MODEL)
    if configured == "anthropic" and ANTHROPIC_API_KEY:
        return ("anthropic", ANTHROPIC_API_KEY, ANTHROPIC_MODEL)
    if GROQ_API_KEY:
        return ("groq", GROQ_API_KEY, GROQ_MODEL)
    if GEMINI_API_KEY:
        return ("gemini", GEMINI_API_KEY, GEMINI_MODEL)
    if ANTHROPIC_API_KEY:
        return ("anthropic", ANTHROPIC_API_KEY, ANTHROPIC_MODEL)
    return ("none", "", "")


LLM_PROVIDER, LLM_API_KEY, LLM_MODEL = _resolve_llm_provider()


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}

# Extension talks from a browser context — allow all origins by default.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# Mock mode: use canned fixtures when explicitly requested or no LLM is configured.
# This keeps a fresh clone usable for the sample documents without paid API keys.
MOCK_MODE = _env_flag("MOCK_MODE") or not LLM_API_KEY
MOCK_SEARCH = _env_flag("MOCK_SEARCH")

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
