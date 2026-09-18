"""Stage 3 — generate search queries and run them against the web.

FIXED: Tavily is now the PRIMARY search provider (best for fact-checking).
Fallback chain: Tavily -> Serper -> Brave

Uses Tavily's include_answer feature for AI-powered fact verification.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
from typing import List

import httpx

from backend.config import (
    BRAVE_API_KEY,
    CACHE_DIR,
    MOCK_SEARCH,
    SEARCH_RESULTS_PER_QUERY,
    SERPER_API_KEY,
    TAVILY_API_KEY,
)
from backend.data.mock_fixtures import SAMPLE_FIXTURES
from backend.models.schemas import Claim, SearchResult


# ------------------------------------------------------------------
# Source trustworthiness tier (per spec)
# ------------------------------------------------------------------
_TIER1_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "nytimes.com", "nature.com",
    "science.org", "pubmed.ncbi.nlm.nih.gov", "pubmed.ncbi", "who.int",
    "cdc.gov", "nasa.gov", "nejm.org", "nih.gov", "mayoclinic.org",
    "law.cornell.edu", "sec.gov", "federalreserve.gov", "imf.org",
}
_TIER2_DOMAINS = {
    "wikipedia.org", "britannica.com", "wsj.com", "ft.com", "economist.com",
    "theguardian.com", "washingtonpost.com", "npr.org",
}
_TIER4_DOMAINS = {
    "medium.com", "substack.com", "linkedin.com", "reddit.com",
    "quora.com", "blogspot.com",
}


def score_source(url: str) -> int:
    u = (url or "").lower()
    if u.endswith(".gov") or u.endswith(".edu") or ".gov/" in u or ".edu/" in u:
        return 1
    host = u
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0]
    for d in _TIER1_DOMAINS:
        if host == d or host.endswith("." + d) or d in u:
            return 1
    for d in _TIER2_DOMAINS:
        if host == d or host.endswith("." + d) or d in u:
            return 2
    for d in _TIER4_DOMAINS:
        if host == d or host.endswith("." + d) or d in u:
            return 4
    return 3


def tier_label(tier: int) -> str:
    return {1: "High Trust", 2: "Trusted", 3: "Standard", 4: "Low Trust"}.get(tier, "Standard")


# ------------------------------------------------------------------
# Query generation — simple, deterministic, no LLM needed
# ------------------------------------------------------------------
def _generate_queries(claim: Claim, domain: str = "general") -> List[str]:
    """Generate 2 search queries for a claim. Uses simple rules."""
    if MOCK_SEARCH:
        return [claim.claim_text, f"{claim.claim_text} evidence source"]

    text = re.sub(r"\s+", " ", claim.claim_text.strip())
    lower = text.lower()

    # Query 1: the claim itself (best for Tavily which understands natural language)
    # Query 2: a more targeted search
    queries = [text]

    # Extract key entities for a second targeted query
    # Remove common prefixes
    cleaned = re.sub(r"^(the|a|an)\s+", "", lower, flags=re.IGNORECASE)

    # For claims with numbers, add a verification query
    if re.search(r"\b\d+\b", text):
        subject = text.split(" is ")[0].split(" was ")[0].split(" has ")[0].split(" won ")[0]
        subject = subject.strip()[:80]
        queries.append(f"{subject} facts wikipedia")
    elif " married " in lower or " spouse " in lower or " wife " in lower or " husband " in lower:
        subject = re.split(r"\b(?:married|spouse|wife|husband)\b", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        queries.append(f"{subject} spouse partner")
    elif " born " in lower:
        subject = re.split(r"\bbborn\b", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        queries.append(f"{subject} birthday birthplace")
    elif " capital " in lower:
        queries.append(f"{text} official")
    elif " founded " in lower or " established " in lower:
        queries.append(f"{text} history")
    else:
        queries.append(f"{text} facts")

    # Extract main subject/entity (best for Wikipedia and encyclopedia lookups)
    subject_match = re.split(r"\b(?:is|was|are|were|has|had|born|founded|built|located|operates|causes|won)\b", text, maxsplit=1, flags=re.IGNORECASE)
    if subject_match and len(subject_match[0].strip()) >= 3:
        subj = re.sub(r"^(?:the|a|an)\s+", "", subject_match[0].strip(), flags=re.IGNORECASE).strip()
        if subj:
            queries.insert(0, subj)

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(q)
    return deduped[:3]


# ------------------------------------------------------------------
# Cache
# ------------------------------------------------------------------
def _cache_key(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()[:24]


def _cache_path(query: str) -> str:
    return os.path.join(CACHE_DIR, f"search_{_cache_key(query)}.json")


def _cache_get(query: str):
    p = _cache_path(query)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and not data:
                    return None
                return data
        except Exception:
            return None
    return None


def _cache_put(query: str, results: list) -> None:
    p = _cache_path(query)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(results, f)
    except Exception as e:
        print(f"[web_verifier] cache write failed: {e}")


# ------------------------------------------------------------------
# Provider 1 — Tavily (PRIMARY — best for fact-checking)
# ------------------------------------------------------------------
_tavily = None
_tavily_ai_answers: dict[str, str] = {}  # cache AI answers


def _get_tavily():
    global _tavily
    if not TAVILY_API_KEY:
        return None
    if _tavily is None:
        try:
            from tavily import TavilyClient
            _tavily = TavilyClient(api_key=TAVILY_API_KEY)
        except Exception as e:
            print(f"[web_verifier] Tavily init failed: {e}")
            return None
    return _tavily


def _search_tavily(query: str) -> List[dict]:
    client = _get_tavily()
    if client is None:
        return []
    try:
        resp = client.search(
            query=query,
            search_depth="advanced",  # Better quality results
            max_results=SEARCH_RESULTS_PER_QUERY,
            include_answer=True,  # Get AI-generated answer for fact-checking
        )
        if isinstance(resp, dict):
            # Store the AI answer for use in verdict engine
            ai_answer = resp.get("answer", "")
            if ai_answer:
                _tavily_ai_answers[query.strip().lower()] = ai_answer
            raw = resp.get("results", [])
        else:
            raw = []
    except Exception as e:
        print(f"[web_verifier] Tavily search failed: {e}")
        return []
    return [
        {
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "snippet": r.get("content") or r.get("snippet") or "",
            "score": float(r.get("score", 0.0) or 0.0),
        }
        for r in raw
    ]


def get_tavily_ai_answer(query: str) -> str:
    """Retrieve the cached Tavily AI answer for a query, if available."""
    return _tavily_ai_answers.get(query.strip().lower(), "")


# ------------------------------------------------------------------
# Provider 2 — Serper (Google wrapper)
# ------------------------------------------------------------------
def _search_serper(query: str) -> List[dict]:
    if not SERPER_API_KEY:
        return []
    try:
        r = httpx.post(
            "https://google.serper.dev/search",
            json={"q": query, "num": SEARCH_RESULTS_PER_QUERY},
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            timeout=6.0,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[web_verifier] Serper search failed: {e}")
        return []
    out: List[dict] = []
    for item in data.get("organic", [])[:SEARCH_RESULTS_PER_QUERY]:
        out.append({
            "url": item.get("link", ""),
            "title": item.get("title", ""),
            "snippet": item.get("snippet", "") or "",
            "score": 1.0 / (int(item.get("position", 1)) or 1),
        })
    return out


# ------------------------------------------------------------------
# Provider 3 — Brave Search
# ------------------------------------------------------------------
def _search_brave(query: str) -> List[dict]:
    if not BRAVE_API_KEY:
        return []
    try:
        r = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": SEARCH_RESULTS_PER_QUERY},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
            timeout=6.0,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[web_verifier] Brave search failed: {e}")
        return []
    out: List[dict] = []
    for idx, item in enumerate(data.get("web", {}).get("results", [])[:SEARCH_RESULTS_PER_QUERY]):
        out.append({
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "snippet": item.get("description", "") or "",
            "score": 1.0 / (idx + 1),
        })
    return out


# ------------------------------------------------------------------
# Provider 4 — Wikipedia + DuckDuckGo (FREE FALLBACK — NO API KEY NEEDED)
# ------------------------------------------------------------------
def _search_wikipedia(query: str) -> List[dict]:
    """Free fallback search using Wikipedia OpenSearch & REST summary APIs."""
    clean_query = re.sub(
        r"\b(wikipedia|facts|official|history|evidence|source|what is|who is)\b",
        "",
        query,
        flags=re.IGNORECASE,
    ).strip()
    if not clean_query:
        clean_query = query.strip()

    headers = {"User-Agent": "VerifAI/1.0 (https://verifai.local; verifai-checker)"}
    out: List[dict] = []

    try:
        r = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "opensearch",
                "search": clean_query[:80],
                "limit": 3,
                "namespace": 0,
                "format": "json",
            },
            headers=headers,
            timeout=5.0,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 4:
                titles = data[1]
                urls = data[3]
                for i, title in enumerate(titles[:3]):
                    if not title:
                        continue
                    url = urls[i] if i < len(urls) else f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"
                    snippet = ""
                    try:
                        sum_r = httpx.get(
                            f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}",
                            headers=headers,
                            timeout=4.0,
                        )
                        if sum_r.status_code == 200:
                            sum_data = sum_r.json()
                            snippet = sum_data.get("extract", "") or sum_data.get("description", "")
                    except Exception:
                        pass

                    if snippet:
                        out.append({
                            "url": url,
                            "title": f"{title} - Wikipedia",
                            "snippet": snippet[:450],
                            "score": 0.9 - (i * 0.15),
                        })
    except Exception as e:
        print(f"[web_verifier] Wikipedia search error: {e}")

    # Fallback to DuckDuckGo Instant Answer if Wikipedia yielded no summary
    if not out:
        try:
            ddg_r = httpx.get(
                "https://api.duckduckgo.com/",
                params={"q": clean_query[:80], "format": "json"},
                headers=headers,
                timeout=4.0,
            )
            if ddg_r.status_code == 200:
                ddg_data = ddg_r.json()
                abstract = ddg_data.get("AbstractText") or ddg_data.get("Abstract")
                source_url = ddg_data.get("AbstractURL")
                source_title = ddg_data.get("Heading") or clean_query
                if abstract and source_url:
                    out.append({
                        "url": source_url,
                        "title": source_title,
                        "snippet": abstract[:450],
                        "score": 0.85,
                    })
                for topic in ddg_data.get("RelatedTopics", [])[:2]:
                    if isinstance(topic, dict) and topic.get("Text") and topic.get("FirstURL"):
                        out.append({
                            "url": topic["FirstURL"],
                            "title": topic["Text"][:60],
                            "snippet": topic["Text"][:300],
                            "score": 0.7,
                        })
        except Exception as e:
            print(f"[web_verifier] DuckDuckGo fallback error: {e}")

    return out


# ------------------------------------------------------------------
# Unified search — TAVILY FIRST, then Serper, then Brave, then Free Wikipedia
# ------------------------------------------------------------------
def _search_with_fallback(query: str) -> List[dict]:
    cached = _cache_get(query)
    if cached is not None:
        return cached

    # Tavily first (best for fact-checking with AI answers)
    # Then Serper, then Brave, then Free Wikipedia
    providers = [_search_tavily, _search_serper, _search_brave, _search_wikipedia]

    for fn in providers:
        try:
            results = fn(query)
        except Exception as e:
            print(f"[web_verifier] provider {fn.__name__} raised: {e}")
            results = []
        if results:
            _cache_put(query, results)
            return results

    return []


# ------------------------------------------------------------------
# Mock-mode helpers
# ------------------------------------------------------------------
def _find_fixture_results(claim: Claim) -> List[SearchResult] | None:
    """In mock mode, find matching fixture results."""
    needle = claim.claim_text.strip().lower()[:40]
    for fixture in SAMPLE_FIXTURES.values():
        for item in fixture["claims"]:
            if needle and needle in item["claim_text"].lower():
                sources = item.get("sources", [])
                return [
                    SearchResult(
                        url=s["url"],
                        title=s["title"],
                        snippet=s["snippet"],
                        source_tier=s.get("source_tier", 3),
                        relevance_score=s.get("relevance_score", 0.5),
                    )
                    for s in sources
                ]
    return None


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------
def verify_claim(claim: Claim, domain: str = "general") -> List[SearchResult]:
    """Search for evidence about a claim. Returns ranked SearchResult list."""
    if MOCK_SEARCH:
        mock_results = _find_fixture_results(claim)
        if mock_results is not None:
            return mock_results

    queries = _generate_queries(claim, domain)
    all_results: dict[str, dict] = {}  # keyed by URL to deduplicate

    for query in queries:
        raw_results = _search_with_fallback(query)
        for r in raw_results:
            url = r.get("url", "")
            if not url:
                continue
            if url not in all_results or r.get("score", 0) > all_results[url].get("score", 0):
                all_results[url] = r

    # Convert to SearchResult objects with tier scoring
    search_results: List[SearchResult] = []
    for raw in all_results.values():
        url = raw.get("url", "")
        tier = score_source(url)
        search_results.append(
            SearchResult(
                url=url,
                title=raw.get("title", ""),
                snippet=raw.get("snippet", "")[:500],
                source_tier=tier,
                relevance_score=float(raw.get("score", 0.5)),
            )
        )

    # Sort by tier (lower = better), then by relevance score (higher = better)
    search_results.sort(key=lambda r: (r.source_tier, -r.relevance_score))
    return search_results[:8]
