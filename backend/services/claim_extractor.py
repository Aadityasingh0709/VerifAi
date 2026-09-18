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
    """Fallback extractor: splits text into lines/sentences and picks factual assertions."""
    claims: List[Claim] = []
    cid = 1
    seen: set[str] = set()

    # Split into lines first to preserve bullet points and lists
    lines = [line.strip() for line in re.split(r'[\r\n]+', doc_text.strip()) if line.strip()]
    raw_sentences = []
    for line in lines:
        # Strip common markdown/bullet markers: -, *, •, 1., etc.
        cleaned_line = re.sub(r"^(?:[-*•–—]|\d+[.)])\s*", "", line).strip()
        if not cleaned_line:
            continue
        # Split line by sentence terminators if multiple sentences exist
        parts = re.split(r'(?<=[.!?])\s+', cleaned_line)
        for p in parts:
            p_clean = p.strip()
            if len(p_clean) >= 12:
                raw_sentences.append(p_clean)

    # If no sentences found via splitting, use whatever non-empty text exists
    if not raw_sentences and len(doc_text.strip()) >= 5:
        raw_sentences.append(doc_text.strip())

    # Patterns indicating strong factual claims
    fact_patterns = re.compile(
        r"\b(\d{1,4}%?|\d+\s*(?:million|billion|thousand|trillion|m|km|kg|lbs|mg|hz|ghz)?|"
        r"founded|born|died|won|lost|defeated|married|invented|discovered|"
        r"capital|population|located|president|ceo|founder|director|author|awarded|published|"
        r"launched|established|created|signed|appointed|elected|built|constructed|developed|"
        r"causes|increases|decreases|produces|contains|consists|comprises|"
        r"operates|evaluates|compiles|executes|processes|serves|provides|"
        r"known as|referred to|defined as|classified as|called|"
        r"is\s+(?:a|an|the|not|used|made|located|considered|composed|named|part)|"
        r"was\s+(?:a|an|the|first|originally|invented|founded|built|named|born|held)|"
        r"are\s+(?:a|an|the|used|made|found|known|classified)|"
        r"were\s+(?:a|an|the|first|originally|used|made)|"
        r"has\s+(?:been|a|an|over|more|less)|"
        r"stands for|full form|acronym|abbreviation)\b",
        re.IGNORECASE,
    )

    priority_candidates = []
    fallback_candidates = []

    for sentence in raw_sentences:
        # Skip obvious subjective remarks or filler
        if re.search(r"^(i think|probably|maybe|perhaps|might|could be|in my opinion|as an ai)\b", sentence, re.IGNORECASE):
            continue

        dedupe_key = sentence.lower().strip()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        if fact_patterns.search(sentence):
            priority_candidates.append(sentence)
        elif len(sentence.split()) >= 3 and len(sentence) <= 350:
            fallback_candidates.append(sentence)

    # Combine prioritized factual sentences with general fallback statements
    selected_sentences = (priority_candidates + fallback_candidates)[:MAX_CLAIMS_PER_DOC]

    for sentence in selected_sentences:
        start, end = _locate(doc_text, sentence)

        # Determine category
        category = "general"
        low = sentence.lower()
        if re.search(r"\b(mg\b|dose|drug|patient|clinical|symptom|treatment|disease|medicine)\b", low):
            category = "medical"
        elif re.search(r"\b(court|law|statute|legal|regulation|judge|rights|constitution)\b", low):
            category = "legal"
        elif re.search(r"\b(revenue|market|stock|earnings|price|cost|dollar|inflation|gdp)\b", low):
            category = "financial"
        elif re.search(r"\b\d+\b", low) and re.search(r"\b(%|percent|million|billion|thousand)\b", low):
            category = "statistical"
        elif re.search(r"\b(born|died|married|elected|appointed|graduated)\b", low):
            category = "person"
        elif re.search(r"\b(battle|war|treaty|revolution|founded|established|war|launch)\b", low):
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
