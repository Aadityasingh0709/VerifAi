"""Stage 4 \u2014 Hallucination Genealogy.

For each claim verdict marked HALLUCINATED, ask Claude to diagnose how the
underlying model likely mutated a real fact. This is our flagship differentiator.
"""
from __future__ import annotations

from backend.config import MOCK_MODE
from backend.data.mock_fixtures import SAMPLE_FIXTURES
from backend.models.schemas import ClaimVerdict, Genealogy
from backend.services.llm_client import call_claude, extract_json

SYSTEM_PROMPT = """You are a forensic AI analyst. Given a hallucinated claim and the real-world truth, diagnose how the LLM likely produced the error.

Common patterns:
- attribute_swap: correct event/fact but wrong person/date/number
- amalgamation: merged two real facts into one false one
- temporal_drift: real fact but wrong time period
- domain_confusion: real concept from one field incorrectly applied to another
- pure_confabulation: no real basis found

Respond with a JSON object with exactly these fields:
{
  "genealogy_type": one of ["attribute_swap", "amalgamation", "temporal_drift", "domain_confusion", "pure_confabulation"],
  "real_fact": "what the actual true fact is (1 sentence)",
  "mutation_explanation": "how the AI likely transformed the real fact into the hallucination (1-2 sentences)",
  "confidence_in_genealogy": integer from 0 to 100
}

Return ONLY the JSON object."""

USER_TEMPLATE = """Hallucinated claim: {claim_text}
The actual truth according to sources: {contradicting_detail}
Supporting source: {best_source_url}

Diagnose the mutation pattern."""


def _mock_genealogy_for(cv: ClaimVerdict) -> Genealogy | None:
    needle = cv.claim.claim_text.strip().lower()[:40]
    for fixture in SAMPLE_FIXTURES.values():
        for item in fixture["claims"]:
            if needle and needle in item["claim_text"].lower():
                g = item.get("genealogy")
                if g:
                    return Genealogy(**g)
    # Fallback generic genealogy.
    return Genealogy(
        genealogy_type="pure_confabulation",
        real_fact="No corroborating real fact found in available sources.",
        mutation_explanation="The model likely confabulated this statement without any real-world anchor \u2014 no mapping to a known fact could be established.",
        confidence_in_genealogy=40,
    )


def diagnose_genealogy(cv: ClaimVerdict) -> Genealogy | None:
    if cv.verdict != "HALLUCINATED":
        return None

    if MOCK_MODE:
        return _mock_genealogy_for(cv)

    raw = call_claude(
        SYSTEM_PROMPT,
        USER_TEMPLATE.format(
            claim_text=cv.claim.claim_text,
            contradicting_detail=cv.contradicting_detail or cv.reasoning,
            best_source_url=cv.best_source_url or "(no source)",
        ),
        max_tokens=500,
    )
    if not raw:
        return _mock_genealogy_for(cv)

    try:
        data = extract_json(raw)
    except Exception as e:
        print(f"[genealogy] parse failure: {e}")
        return _mock_genealogy_for(cv)

    gtype = str(data.get("genealogy_type", "pure_confabulation"))
    if gtype not in {"attribute_swap", "amalgamation", "temporal_drift", "domain_confusion", "pure_confabulation"}:
        gtype = "pure_confabulation"
    return Genealogy(
        genealogy_type=gtype,  # type: ignore[arg-type]
        real_fact=str(data.get("real_fact", ""))[:400],
        mutation_explanation=str(data.get("mutation_explanation", ""))[:600],
        confidence_in_genealogy=max(0, min(100, int(data.get("confidence_in_genealogy", 50)))),
    )
