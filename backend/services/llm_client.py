"""Thin wrapper around the configured LLM provider with JSON extraction helpers."""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Optional

import httpx

from backend.config import (
    LLM_API_KEY,
    LLM_CONCURRENCY,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_RETRY_BASE_SECONDS,
    MOCK_MODE,
)

_anthropic_client = None
_llm_gate = threading.BoundedSemaphore(LLM_CONCURRENCY)


def _get_anthropic_client():
    """Lazy-init the Anthropic client. Returns None in mock mode."""
    global _anthropic_client
    if MOCK_MODE or LLM_PROVIDER != "anthropic" or not LLM_API_KEY:
        return None
    if _anthropic_client is None:
        try:
            from anthropic import Anthropic
            _anthropic_client = Anthropic(api_key=LLM_API_KEY)
        except Exception as e:
            print(f"[llm_client] Failed to init Anthropic client: {e}")
            return None
    return _anthropic_client


def _call_anthropic(
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> Optional[str]:
    client = _get_anthropic_client()
    if client is None:
        return None
    try:
        resp = client.messages.create(
            model=LLM_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip() or None
    except Exception as e:
        print(f"[llm_client] Anthropic call failed: {e}")
        return None


def _call_groq(
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> Optional[str]:
    if not LLM_API_KEY:
        return None
    with _llm_gate:
        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                resp = httpx.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                    timeout=15.0,
                )
                if resp.status_code == 429:
                    wait = LLM_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                    print(f"[llm_client] Groq rate-limited, waiting {wait}s (attempt {attempt})")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip() or None
                return None
            except Exception as e:
                print(f"[llm_client] Groq call failed (attempt {attempt}): {e}")
                if attempt < LLM_MAX_RETRIES:
                    time.sleep(LLM_RETRY_BASE_SECONDS * attempt)
                    continue
                return None
    return None


def _call_gemini(
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> Optional[str]:
    if not LLM_API_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL}:generateContent?key={LLM_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    with _llm_gate:
        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                resp = httpx.post(url, json=payload, timeout=20.0)
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip() or None
                return None
            except Exception as e:
                print(f"[llm_client] Gemini call failed (attempt {attempt}): {e}")
                if attempt < LLM_MAX_RETRIES:
                    time.sleep(LLM_RETRY_BASE_SECONDS * attempt)
                    continue
                return None
    return None


def call_claude(
    system: str,
    user: str,
    max_tokens: int = 1024,
    temperature: float = 0.1,
) -> Optional[str]:
    """Call the configured LLM provider. Returns raw text or None."""
    if MOCK_MODE:
        return None
    if LLM_PROVIDER == "anthropic":
        return _call_anthropic(system, user, max_tokens, temperature)
    if LLM_PROVIDER == "groq":
        return _call_groq(system, user, max_tokens, temperature)
    if LLM_PROVIDER == "gemini":
        return _call_gemini(system, user, max_tokens, temperature)
    return None


def extract_json(raw: str) -> dict:
    """Best-effort extraction of a JSON object or array from LLM output."""
    if not raw:
        return {}
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try to find JSON in markdown code blocks
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try to find a JSON object or array
    for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
        match = re.search(pattern, raw)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}
