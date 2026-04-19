"""Stage 2 — automatic document domain classifier.

Auto-detects whether the document is healthcare, legal, finance, education,
news, or general. Drives downstream strictness in the verdict engine.
"""
from __future__ import annotations

import re

from backend.config import MOCK_MODE
from backend.models.schemas import DomainInfo
from backend.services.llm_client import call_claude, extract_json

SYSTEM_PROMPT = """You are a domain classifier. Read the following text and determine which single domain it primarily belongs to.

Domains:
- healthcare: medical advice, drug information, clinical studies, symptoms, treatments, dosages
- legal: laws, regulations, court cases, legal rights, contracts, statutes
- finance: investments, market data, economic statistics, financial advice, company finances
- education: academic facts, historical events, scientific concepts, research, biographies
- news: current events, political developments, recent incidents
- general: anything that does not clearly fit above

Respond with ONLY a JSON object:
{
  "domain": one of the six domains above,
  "confidence": integer 0 to 100,
  "reasoning": "one sentence explanation"
}"""


# Domain-level verification rules used by the verdict engine and trust score.
DOMAIN_RULES = {
    "healthcare": {
        "trusted_sources": [
            "pubmed.ncbi", "who.int", "cdc.gov", "nih.gov",
            "mayoclinic.org", "nejm.org", "nature.com",
        ],
        "min_tier_for_verified": 2,
        "penalty_multiplier": 2.0,
    },
    "legal": {
        "trusted_sources": [
            "law.cornell.edu", "supreme.justia.com",
            "legislation.gov.uk", "justice.gov",
        ],
        "min_tier_for_verified": 2,
        "penalty_multiplier": 2.0,
    },
    "finance": {
        "trusted_sources": [
            "sec.gov", "federalreserve.gov", "imf.org",
            "worldbank.org", "bls.gov",
        ],
        "min_tier_for_verified": 2,
        "penalty_multiplier": 1.5,
    },
    "education": {
        "trusted_sources": [],
        "min_tier_for_verified": 3,
        "penalty_multiplier": 1.0,
    },
    "news": {
        "trusted_sources": ["reuters.com", "apnews.com", "bbc.com", "nytimes.com"],
        "min_tier_for_verified": 2,
        "penalty_multiplier": 1.0,
    },
    "general": {
        "trusted_sources": [],
        "min_tier_for_verified": 3,
        "penalty_multiplier": 1.0,
    },
}


def get_domain_rules(domain: str) -> dict:
    """Get the verification rules for a domain."""
    return DOMAIN_RULES.get(domain, DOMAIN_RULES["general"])


def _heuristic_detect(text: str) -> DomainInfo:
    """Cheap fallback classifier used in mock mode or when LLM is unavailable."""
    t = text.lower()
    scores = {
        "healthcare": 0,
        "legal": 0,
        "finance": 0,
        "education": 0,
        "news": 0,
    }
    scores["healthcare"] += len(re.findall(
        r"\b(aspirin|drug|dose|patient|clinical|mg\b|symptom|disease|treatment|mayo|nejm|pubmed|cdc|who\b)",
        t,
    ))
    scores["legal"] += len(re.findall(
        r"\b(court|supreme|statute|plaintiff|defendant|contract|law|legal|v\.|regulation)",
        t,
    ))
    scores["finance"] += len(re.findall(
        r"\b(market|stock|nasdaq|s&p|revenue|earnings|fed|federal reserve|quarter|fiscal|sec filing|investor)",
        t,
    ))
    scores["education"] += len(re.findall(
        r"\b(revolution|history|napoleon|pope|emperor|century|bce|bc|ad|published|journal|university|jwst|telescope|mirror|orbit)",
        t,
    ))
    scores["news"] += len(re.findall(
        r"\b(today|yesterday|reuters|ap news|announced|reported|breaking)",
        t,
    ))
    domain, best = max(scores.items(), key=lambda kv: kv[1])
    if best == 0:
        return DomainInfo(domain="general", confidence=30,
                          reasoning="No strong domain keywords detected; defaulting to general.")
    total = sum(scores.values()) or 1
    conf = int(round((best / total) * 100))
    return DomainInfo(
        domain=domain,
        confidence=min(95, max(45, conf)),
        reasoning=f"Heuristic keyword match: {best} {domain}-related term(s).",
    )


def detect_domain(text: str, doc_title: str = "") -> DomainInfo:
    """Return the auto-detected domain for a document."""
    if not text.strip():
        return DomainInfo(domain="general", confidence=0, reasoning="Empty document.")

    # For short texts or bullet-point style, use heuristics (faster, no API cost)
    if text.count("\n") >= 3 or any(marker in text for marker in ["->", "=>"]):
        return _heuristic_detect(f"{doc_title}\n{text}")

    if MOCK_MODE:
        return _heuristic_detect(text)

    context = f"Title: {doc_title.strip()}\nText:\n{text[:6000]}" if doc_title.strip() else f"Text:\n{text[:6000]}"
    raw = call_claude(SYSTEM_PROMPT, context, max_tokens=200)
    if not raw:
        return _heuristic_detect(text)
    try:
        data = extract_json(raw)
        domain = str(data.get("domain", "general")).lower()
        if domain not in DOMAIN_RULES:
            domain = "general"
        conf = max(0, min(100, int(data.get("confidence", 60))))
        reasoning = str(data.get("reasoning", ""))[:240]
        return DomainInfo(domain=domain, confidence=conf, reasoning=reasoning)
    except Exception as e:
        print(f"[domain_detector] parse error: {e}")
        return _heuristic_detect(text)
