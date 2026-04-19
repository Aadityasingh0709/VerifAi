"""Stage 4 — verdict engine using LLM + Tavily AI answers for accurate fact-checking.

FIXED: Removed brittle heuristic contradiction detection.
Now relies on LLM judgment backed by Tavily AI answers + web evidence.
"""
from __future__ import annotations

import re
from typing import List

from backend.config import MOCK_MODE
from backend.data.mock_fixtures import SAMPLE_FIXTURES, TOPIC_FIXTURES
from backend.models.schemas import Claim, ClaimVerdict, SearchResult
from backend.services.domain_detector import get_domain_rules
from backend.services.llm_client import call_claude, extract_json
from backend.services.web_verifier import get_tavily_ai_answer, tier_label

SYSTEM_PROMPT = """You are a fact-checking judge. You will be given a factual claim, web search results, and optionally an AI-generated answer from a search engine.

Your job is to determine whether the claim is VERIFIED, UNVERIFIED, or HALLUCINATED.

Definitions:
- VERIFIED: At least one credible source explicitly confirms the claim is accurate
- UNVERIFIED: No source either confirms or contradicts the claim (could not find evidence either way)
- HALLUCINATED: At least one credible source explicitly contradicts the claim, OR the claim contains specific details (names, dates, statistics) that sources show are incorrect

IMPORTANT RULES:
1. Compare the claim CAREFULLY against the search results. Pay close attention to specific numbers, dates, names.
2. If sources say something DIFFERENT from the claim (e.g., claim says "5" but sources say "8"), that is HALLUCINATED.
3. If no sources address the claim at all, mark it UNVERIFIED, not VERIFIED.
4. Domain context matters: for healthcare/legal/financial claims, demand clearer confirmation.

Respond with a JSON object with exactly these fields:
{
  "verdict": "VERIFIED" | "UNVERIFIED" | "HALLUCINATED",
  "confidence": integer 0 to 100,
  "reasoning": "1-2 sentence explanation citing specific evidence",
  "best_source_url": "most relevant source URL",
  "best_source_quote": "brief relevant snippet under 20 words",
  "contradicting_detail": "what is specifically wrong if HALLUCINATED, else null"
}

Return ONLY the JSON object."""

USER_TEMPLATE = """Domain: {domain}
High stakes: {high_stakes}
Claim: {claim_text}

{ai_answer_section}
Search Results:
{formatted_results}"""


def _format_results(results: List[SearchResult]) -> str:
    if not results:
        return "(no search results found)"
    lines = []
    for i, r in enumerate(results[:6], start=1):
        label = {
            1: "Tier 1 (gov/edu/peer-reviewed/major wire)",
            2: "Tier 2 (major news/wiki)",
            3: "Tier 3 (general)",
            4: "Tier 4 (blog/social)",
        }.get(r.source_tier, "Tier ?")
        lines.append(
            f"[{i}] {r.title}\n    URL: {r.url}\n    {label} | relevance={r.relevance_score:.2f}\n    Snippet: {r.snippet[:350]}"
        )
    return "\n".join(lines)


def _apply_confidence_caps(
    verdict: str,
    best_tier: int,
    confidence: int,
    high_stakes: bool,
    domain: str,
) -> int:
    """Post-process confidence. Less aggressive than before."""
    rules = get_domain_rules(domain)
    min_tier = rules["min_tier_for_verified"]

    if verdict == "VERIFIED":
        # Boost confidence for good sources, only cap for very poor ones
        if best_tier <= 2:
            confidence = max(confidence, 70)  # Trusted sources = at least 70%
        elif best_tier >= 4:
            confidence = min(confidence, 65)
        if high_stakes and best_tier > 2:
            confidence = min(confidence, 60)
    elif verdict == "HALLUCINATED":
        if best_tier <= 2:
            confidence = max(confidence, 85)
    elif verdict == "UNVERIFIED":
        confidence = max(20, min(50, confidence))
    return max(0, min(100, confidence))


def _best_source(verdict_url: str | None, results: List[SearchResult]) -> SearchResult | None:
    if verdict_url:
        for r in results:
            if r.url == verdict_url:
                return r
    return results[0] if results else None


# ------------------------------------------------------------------
# Heuristic verdict (fallback when LLM is unavailable)
# ------------------------------------------------------------------
def _heuristic_verdict(
    claim: Claim,
    results: List[SearchResult],
    domain: str,
) -> ClaimVerdict:
    """Simple keyword-overlap based verdict. Used when LLM fails."""
    if not results:
        return ClaimVerdict(
            claim=claim,
            verdict="UNVERIFIED",
            confidence=25,
            reasoning="No search results found to verify this claim.",
            sources=results,
        )

    claim_lower = claim.claim_text.lower()
    claim_words = set(re.findall(r"[a-z]{3,}", claim_lower))

    best_overlap = 0
    best_result = results[0]

    for r in results:
        haystack = f"{r.title} {r.snippet}".lower()
        hay_words = set(re.findall(r"[a-z]{3,}", haystack))
        overlap = len(claim_words & hay_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_result = r

    # If good keyword overlap, lean toward VERIFIED; otherwise UNVERIFIED
    total_claim_words = len(claim_words) or 1
    overlap_ratio = best_overlap / total_claim_words

    if overlap_ratio > 0.6:
        verdict = "VERIFIED"
        confidence = min(85, int(overlap_ratio * 95))
        reasoning = f"Strong keyword overlap with search results ({overlap_ratio:.0%} match)."
    elif overlap_ratio > 0.35:
        verdict = "VERIFIED"
        confidence = min(65, int(overlap_ratio * 80))
        reasoning = f"Moderate keyword overlap with search results ({overlap_ratio:.0%} match)."
    else:
        verdict = "UNVERIFIED"
        confidence = 35
        reasoning = "Insufficient evidence in search results to confirm or deny this claim."

    return ClaimVerdict(
        claim=claim,
        verdict=verdict,
        confidence=confidence,
        reasoning=reasoning,
        sources=results,
        best_source_url=best_result.url,
        best_source_quote=best_result.snippet[:80],
        best_source_tier=best_result.source_tier,
        best_source_label=tier_label(best_result.source_tier),
    )


# ------------------------------------------------------------------
# Mock-mode verdict
# ------------------------------------------------------------------
def _mock_verdict(claim: Claim, results: List[SearchResult]) -> ClaimVerdict | None:
    needle = claim.claim_text.strip().lower()[:40]

    # Search ALL fixtures: legacy samples + topic fixtures
    all_claim_lists = []
    for fixture in SAMPLE_FIXTURES.values():
        all_claim_lists.append(fixture["claims"])
    for topic in TOPIC_FIXTURES:
        all_claim_lists.append(topic["claims"])

    for claim_list in all_claim_lists:
        for item in claim_list:
            item_text = item["claim_text"].lower()
            # Match if needle is in item text OR item text is in needle
            if needle and (needle in item_text or item_text[:35] in needle):
                best_url = item.get("best_source_url")
                best = _best_source(best_url, results)
                # Build source list from fixture if available
                fixture_sources = item.get("sources", [])
                source_objects = []
                for s in fixture_sources:
                    source_objects.append(SearchResult(
                        url=s["url"],
                        title=s.get("title", ""),
                        snippet=s.get("snippet", ""),
                        source_tier=s.get("source_tier", 3),
                        relevance_score=s.get("relevance_score", 0.8),
                    ))
                # Build genealogy if present
                from backend.models.schemas import Genealogy
                genealogy = None
                if item.get("genealogy"):
                    g = item["genealogy"]
                    genealogy = Genealogy(
                        genealogy_type=g["genealogy_type"],
                        real_fact=g["real_fact"],
                        mutation_explanation=g["mutation_explanation"],
                        confidence_in_genealogy=g["confidence_in_genealogy"],
                    )
                return ClaimVerdict(
                    claim=claim,
                    verdict=item["verdict"],
                    confidence=item["confidence"],
                    reasoning=item["reasoning"],
                    best_source_url=best_url,
                    best_source_quote=item.get("best_source_quote"),
                    best_source_tier=best.source_tier if best else (fixture_sources[0]["source_tier"] if fixture_sources else 3),
                    best_source_label=tier_label(best.source_tier if best else (fixture_sources[0]["source_tier"] if fixture_sources else 3)),
                    contradicting_detail=item.get("contradicting_detail"),
                    sources=source_objects if source_objects else results,
                    genealogy=genealogy,
                )
    return None


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------
def evaluate_claim(
    claim: Claim,
    results: List[SearchResult],
    domain: str = "general",
) -> ClaimVerdict:
    """Evaluate a single claim against search results."""
    # Mock mode: return fixture verdict
    if MOCK_MODE:
        mock = _mock_verdict(claim, results)
        if mock:
            return mock

    # Try to get Tavily AI answer for additional context
    ai_answer = get_tavily_ai_answer(claim.claim_text)
    ai_answer_section = ""
    if ai_answer:
        ai_answer_section = f"AI Search Answer (use as additional context):\n{ai_answer[:500]}\n"

    # Build prompt and call LLM
    formatted = _format_results(results)
    user_msg = USER_TEMPLATE.format(
        domain=domain,
        high_stakes=claim.high_stakes,
        claim_text=claim.claim_text,
        ai_answer_section=ai_answer_section,
        formatted_results=formatted,
    )

    raw = call_claude(SYSTEM_PROMPT, user_msg, max_tokens=400, temperature=0.1)

    if not raw:
        # LLM unavailable — fall back to heuristic
        print(f"[verdict_engine] LLM unavailable, using heuristic for: {claim.claim_text[:60]}")
        return _heuristic_verdict(claim, results, domain)

    try:
        data = extract_json(raw)
    except Exception as e:
        print(f"[verdict_engine] JSON parse failed: {e}")
        return _heuristic_verdict(claim, results, domain)

    verdict = str(data.get("verdict", "UNVERIFIED")).upper()
    if verdict not in {"VERIFIED", "UNVERIFIED", "HALLUCINATED"}:
        verdict = "UNVERIFIED"

    confidence = max(0, min(100, int(data.get("confidence", 50))))
    reasoning = str(data.get("reasoning", ""))[:300]
    best_url = data.get("best_source_url")
    best = _best_source(best_url, results)
    best_tier = best.source_tier if best else 3

    # Apply confidence caps (less aggressive than before)
    confidence = _apply_confidence_caps(
        verdict, best_tier, confidence, claim.high_stakes, domain
    )

    return ClaimVerdict(
        claim=claim,
        verdict=verdict,
        confidence=confidence,
        reasoning=reasoning,
        best_source_url=best_url,
        best_source_quote=str(data.get("best_source_quote", ""))[:100] or None,
        best_source_tier=best_tier,
        best_source_label=tier_label(best_tier),
        contradicting_detail=str(data.get("contradicting_detail", ""))[:200] or None,
        sources=results,
    )
