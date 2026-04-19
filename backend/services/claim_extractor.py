"""Stage 1 — extract atomic factual claims from a document."""
from __future__ import annotations

import re
from typing import List

from backend.config import MAX_CLAIMS_PER_DOC, MAX_DOC_CHARS, MOCK_MODE
from backend.data.mock_fixtures import get_fixture_for_text
from backend.models.schemas import Claim
from backend.services.llm_client import call_claude, extract_json

SYSTEM_PROMPT = """You are a precise factual claim extractor. Your job is to read a document and extract every atomic factual claim that could in principle be verified against real-world evidence.

A factual claim is: a specific assertion about a person, place, event, statistic, date, scientific finding, or named entity that is either true or false.

Do NOT extract:
- Opinions or subjective statements ("the policy was controversial")
- Future predictions ("this may lead to...")
- Vague general statements ("many experts believe...")
- Meta-commentary about the document itself

Important:
- Each claim_text must be standalone and fully understandable on its own.
- Resolve pronouns, bullets, shorthand, and list items using the document title and surrounding context when possible.
- If a bullet item depends on a heading for meaning, rewrite claim_text so it includes that missing context.

For each claim you extract, output a JSON object with exactly these fields:
{
  "id": integer starting from 1,
  "claim_text": "the factual claim rewritten as a standalone statement when needed",
  "claim_category": one of ["statistical", "citation", "event", "person", "scientific", "legal", "medical", "financial", "general"],
  "high_stakes": boolean (true if medical, legal, or financial),
  "source_sentence": "the sentence from the document this claim came from",
  "char_start": integer (character position where source_sentence starts in original doc),
  "char_end": integer (character position where source_sentence ends)
}

Return a JSON array of all claims. Return ONLY the JSON array, no other text."""


def _locate(doc: str, sentence: str) -> tuple[int, int]:
    idx = doc.find(sentence)
    if idx == -1:
        snippet = sentence[:30]
        idx = doc.find(snippet)
        if idx == -1:
            return (0, min(len(sentence), len(doc)))
    return (idx, idx + len(sentence))


def _prioritize_and_cap(claims: List[Claim], cap: int) -> List[Claim]:
    """Sort high_stakes first, then statistical/citation, then rest; cap count."""
    def key(c: Claim) -> tuple:
        hs = 0 if c.high_stakes else 1
        cat_rank = 0 if c.claim_category in {"statistical", "citation", "medical", "legal", "financial"} else 1
        return (hs, cat_rank, c.id)

    ordered = sorted(claims, key=key)[:cap]
    for i, c in enumerate(ordered, start=1):
        c.id = i
    return ordered


def _claims_from_fixture(fixture: dict, doc_text: str) -> List[Claim]:
    out: List[Claim] = []
    for i, item in enumerate(fixture["claims"], start=1):
        start, end = _locate(doc_text, item["source_sentence"])
        out.append(
            Claim(
                id=i,
                claim_text=item["claim_text"],
                claim_category=item.get("claim_category", "general"),
                high_stakes=item.get("high_stakes", False),
                source_sentence=item["source_sentence"],
                char_start=start,
                char_end=end,
            )
        )
    return out


def _heuristic_extract(doc_text: str, doc_title: str = "") -> List[Claim]:
    """Fallback extractor: splits text into sentences and picks ones that look factual."""
    claims: List[Claim] = []
    cid = 1
    seen: set[str] = set()

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', doc_text.strip())

    # Patterns that indicate a factual claim — broad coverage
    fact_patterns = re.compile(
        r"\b(\d{4}|\d+%|\d+\s*(million|billion|thousand)|"
        r"founded|born|died|won|lost|defeated|married|invented|discovered|"
        r"capital|population|located|president|ceo|awarded|published|"
        r"launched|established|created|signed|appointed|elected|"
        r"causes|increases|decreases|produces|contains|consists|"
        r"operates|evaluates|compiles|executes|processes|"
        r"known as|referred to|defined as|classified as|called|"
        r"is\s+(?:a|an|the|not|used|made|located|considered|composed)|"
        r"was\s+(?:a|an|the|first|originally|invented|founded|built)|"
        r"are\s+(?:a|an|the|used|made|found|known|classified)|"
        r"stands for|full form|acronym|abbreviation)\b",
        re.IGNORECASE,
    )

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 15 or len(sentence) > 300:
            continue

        # Skip non-factual sentences
        if not fact_patterns.search(sentence):
            continue

        # Skip opinions
        if re.search(r"\b(I think|probably|maybe|perhaps|might|could be|in my opinion)\b", sentence, re.IGNORECASE):
            continue

        dedupe_key = sentence.lower().strip()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        start, end = _locate(doc_text, sentence)

        # Determine category
        category = "general"
        low = sentence.lower()
        if re.search(r"\b(mg|dose|drug|patient|clinical|symptom|treatment)\b", low):
            category = "medical"
        elif re.search(r"\b(court|law|statute|legal|regulation)\b", low):
            category = "legal"
        elif re.search(r"\b(revenue|market|stock|earnings|price|cost)\b", low):
            category = "financial"
        elif re.search(r"\b\d+\b", low) and re.search(r"\b(%|percent|million|billion|thousand)\b", low):
            category = "statistical"
        elif re.search(r"\b(born|died|married|elected|appointed)\b", low):
            category = "person"
        elif re.search(r"\b(battle|war|treaty|revolution|founded|established)\b", low):
            category = "event"

        high_stakes = category in {"medical", "legal", "financial"}

        claims.append(Claim(
            id=cid,
            claim_text=sentence,
            claim_category=category,
            high_stakes=high_stakes,
            source_sentence=sentence,
            char_start=start,
            char_end=end,
        ))
        cid += 1

        if cid > MAX_CLAIMS_PER_DOC:
            break

    return claims


def extract_claims(doc_text: str, doc_title: str = "") -> List[Claim]:
    """Extract factual claims from a document."""
    doc_text = doc_text[:MAX_DOC_CHARS]

    if not doc_text.strip():
        return []

    # Mock mode: use fixtures
    if MOCK_MODE:
        fixture = get_fixture_for_text(doc_text)
        if fixture:
            return _claims_from_fixture(fixture, doc_text)

    # Try LLM extraction first
    context = f"Title: {doc_title.strip()}\n\n{doc_text}" if doc_title.strip() else doc_text
    raw = call_claude(SYSTEM_PROMPT, context, max_tokens=2000, temperature=0.1)

    if raw:
        try:
            data = extract_json(raw)
            if isinstance(data, list) and len(data) > 0:
                claims = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    claim_text = str(item.get("claim_text", "")).strip()
                    if not claim_text:
                        continue
                    source_sentence = str(item.get("source_sentence", claim_text)).strip()
                    start, end = _locate(doc_text, source_sentence)
                    cat = str(item.get("claim_category", "general"))
                    if cat not in {"statistical", "citation", "event", "person", "scientific", "legal", "medical", "financial", "general"}:
                        cat = "general"
                    claims.append(Claim(
                        id=item.get("id", len(claims) + 1),
                        claim_text=claim_text,
                        claim_category=cat,
                        high_stakes=bool(item.get("high_stakes", False)),
                        source_sentence=source_sentence,
                        char_start=start,
                        char_end=end,
                    ))
                if claims:
                    return _prioritize_and_cap(claims, MAX_CLAIMS_PER_DOC)
        except Exception as e:
            print(f"[claim_extractor] LLM parse failed: {e}")

    # Fallback: heuristic extraction
    print("[claim_extractor] Using heuristic fallback extraction")
    claims = _heuristic_extract(doc_text, doc_title)
    return _prioritize_and_cap(claims, MAX_CLAIMS_PER_DOC)
