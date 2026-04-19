"""Async orchestration of the VerifAI audit pipeline."""
from __future__ import annotations

import asyncio
import traceback
from datetime import datetime, timezone
from typing import List

from backend.config import CLAIM_TIMEOUT_SECONDS, MAX_DOC_CHARS, MOCK_MODE, SEARCH_CONCURRENCY
from backend.data.mock_fixtures import get_fixture_for_text, TOPIC_FIXTURES, SAMPLE_FIXTURES
from backend.db.database import get_live, persist_final, update_live
from backend.models.schemas import Claim, ClaimVerdict, DomainInfo, Genealogy, SearchResult, TrustScore
from backend.services.claim_extractor import extract_claims
from backend.services.domain_detector import detect_domain
from backend.services.genealogy import diagnose_genealogy
from backend.services.report_generator import calculate_trust_score
from backend.services.verdict_engine import evaluate_claim
from backend.services.web_verifier import verify_claim


# Human-readable stage labels surfaced in the extension sidebar.
STAGE_LABELS = {
    "queued": "Queued...",
    "extracting": "Extracting factual claims...",
    "detecting_domain": "Detecting document domain...",
    "searching": "Searching web sources...",
    "verifying": "Evaluating evidence...",
    "genealogy": "Running hallucination forensics...",
    "reporting": "Generating report...",
    "complete": "Complete",
    "error": "Error",
}


async def _to_thread(fn, /, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


def _merge_live(audit_id: str, payload: dict) -> None:
    patch = {k: v for k, v in payload.items() if k != "audit_id"}
    update_live(audit_id, **patch)


def _try_mock_fast_path(doc_text: str) -> list[ClaimVerdict] | None:
    """If MOCK_MODE and text matches a fixture, build complete verdicts directly."""
    if not MOCK_MODE:
        return None
    fixture = get_fixture_for_text(doc_text)
    if not fixture:
        return None
    verdicts = []
    for i, item in enumerate(fixture["claims"], start=1):
        claim = Claim(
            id=i,
            claim_text=item["claim_text"],
            claim_category=item.get("claim_category", "general"),
            high_stakes=item.get("high_stakes", False),
            source_sentence=item.get("source_sentence", item["claim_text"]),
            char_start=0, char_end=0,
        )
        sources = []
        for s in item.get("sources", []):
            sources.append(SearchResult(
                url=s["url"], title=s.get("title", ""),
                snippet=s.get("snippet", ""),
                source_tier=s.get("source_tier", 3),
                relevance_score=s.get("relevance_score", 0.8),
            ))
        genealogy = None
        if item.get("genealogy"):
            g = item["genealogy"]
            genealogy = Genealogy(
                genealogy_type=g["genealogy_type"],
                real_fact=g["real_fact"],
                mutation_explanation=g["mutation_explanation"],
                confidence_in_genealogy=g["confidence_in_genealogy"],
            )
        verdicts.append(ClaimVerdict(
            claim=claim,
            verdict=item["verdict"],
            confidence=item["confidence"],
            reasoning=item["reasoning"],
            best_source_url=item.get("best_source_url"),
            best_source_quote=item.get("best_source_quote"),
            best_source_tier=sources[0].source_tier if sources else 3,
            best_source_label={"1": "High Trust", "2": "Trusted", "3": "Standard", "4": "Low Trust"}.get(str(sources[0].source_tier if sources else 3), "Standard"),
            contradicting_detail=item.get("contradicting_detail"),
            sources=sources,
            genealogy=genealogy,
        ))
    return verdicts


async def _process_claim(claim: Claim, domain: str, sem: asyncio.Semaphore) -> ClaimVerdict:
    async with sem:
        try:
            results = await asyncio.wait_for(
                _to_thread(verify_claim, claim, domain),
                timeout=CLAIM_TIMEOUT_SECONDS,
            )
            verdict = await asyncio.wait_for(
                _to_thread(evaluate_claim, claim, results, domain),
                timeout=CLAIM_TIMEOUT_SECONDS,
            )
            if verdict.verdict == "HALLUCINATED":
                g = await asyncio.wait_for(
                    _to_thread(diagnose_genealogy, verdict),
                    timeout=CLAIM_TIMEOUT_SECONDS,
                )
                verdict.genealogy = g
            return verdict
        except asyncio.TimeoutError:
            return ClaimVerdict(
                claim=claim,
                verdict="UNVERIFIED",
                confidence=20,
                reasoning="Claim processing timed out before enough evidence could be collected.",
                sources=[],
            )


def _live_snapshot(audit_id: str) -> dict:
    return get_live(audit_id) or {}


async def run_audit(audit_id: str) -> None:
    """Main pipeline runner; updates live state as it progresses."""
    try:
        live = _live_snapshot(audit_id)
        doc_text = (live.get("document_text") or "")[:MAX_DOC_CHARS]
        doc_title = live.get("document_title") or ""

        # Stage 1: extract claims
        update_live(
            audit_id,
            stage="extracting",
            stage_label=STAGE_LABELS["extracting"],
            progress_percent=5,
        )
        preview_claims = live.get("preview_claims") or []
        if preview_claims:
            claims = [Claim.model_validate(item) for item in preview_claims]
        else:
            claims = await _to_thread(extract_claims, doc_text, doc_title)
        total = len(claims)
        update_live(
            audit_id,
            total_claims=total,
            progress_percent=12,
            stage="detecting_domain",
            stage_label=STAGE_LABELS["detecting_domain"],
        )

        # Stage 2: domain detection
        preview_domain = live.get("preview_domain")
        if preview_domain:
            domain_info = DomainInfo.model_validate(preview_domain)
        else:
            domain_info = await _to_thread(detect_domain, doc_text, doc_title)
        update_live(
            audit_id,
            domain=domain_info.model_dump(),
            progress_percent=18,
            stage="searching",
            stage_label=STAGE_LABELS["searching"],
        )

        if total == 0:
            final = _build_result(
                audit_id, live,
                claims_processed=0, claim_verdicts=[],
                status="complete", stage="complete", progress_percent=100,
                domain_info=domain_info,
            )
            persist_final(audit_id, final)
            _merge_live(audit_id, final)
            return

        # MOCK FAST PATH: if fixture matched, use pre-built verdicts directly
        mock_verdicts = _try_mock_fast_path(doc_text)
        if mock_verdicts:
            update_live(audit_id, stage="verifying", stage_label=STAGE_LABELS["verifying"], progress_percent=60)
            update_live(audit_id, stage="reporting", stage_label=STAGE_LABELS["reporting"], progress_percent=95,
                        claims_processed=len(mock_verdicts), claims=[v.model_dump() for v in mock_verdicts])
            ts = calculate_trust_score(mock_verdicts, domain_info.domain)
            final = _build_result(
                audit_id, live,
                claims_processed=len(mock_verdicts), claim_verdicts=mock_verdicts,
                status="complete", stage="complete", progress_percent=100,
                trust_score=ts, domain_info=domain_info,
            )
            persist_final(audit_id, final)
            _merge_live(audit_id, final)
            return

        # Stages 3-5: search + verdict + genealogy (concurrent)
        sem = asyncio.Semaphore(SEARCH_CONCURRENCY)
        verdicts: List[ClaimVerdict] = []
        tasks = [
            asyncio.create_task(_process_claim(c, domain_info.domain, sem))
            for c in claims
        ]

        processed = 0
        for coro in asyncio.as_completed(tasks):
            cv = await coro
            verdicts.append(cv)
            processed += 1
            if processed < total * 0.4:
                stage = "searching"
            elif processed < total * 0.8:
                stage = "verifying"
            else:
                stage = "genealogy"
            progress = 18 + int((processed / total) * 72)
            sorted_so_far = sorted(verdicts, key=lambda v: v.claim.id)
            update_live(
                audit_id,
                stage=stage,
                stage_label=STAGE_LABELS[stage],
                progress_percent=progress,
                claims_processed=processed,
                claims=[v.model_dump() for v in sorted_so_far],
            )

        verdicts.sort(key=lambda v: v.claim.id)

        # Stage 6: trust score + finalize
        update_live(
            audit_id,
            stage="reporting",
            stage_label=STAGE_LABELS["reporting"],
            progress_percent=95,
        )
        ts: TrustScore = calculate_trust_score(verdicts, domain_info.domain)

        final = _build_result(
            audit_id,
            live,
            claims_processed=total,
            claim_verdicts=verdicts,
            status="complete",
            stage="complete",
            progress_percent=100,
            trust_score=ts,
            domain_info=domain_info,
        )
        persist_final(audit_id, final)
        _merge_live(audit_id, final)

    except Exception as e:
        traceback.print_exc()
        update_live(audit_id, status="error", stage="error", error_message=str(e))
        live = _live_snapshot(audit_id)
        final = _build_result(
            audit_id, live,
            claims_processed=live.get("claims_processed", 0),
            claim_verdicts=[], status="error", stage="error",
            progress_percent=live.get("progress_percent", 0),
            error_message=str(e),
        )
        persist_final(audit_id, final)


def _build_result(
    audit_id: str,
    live: dict,
    *,
    claims_processed: int,
    claim_verdicts: List[ClaimVerdict],
    status: str,
    stage: str,
    progress_percent: int,
    trust_score: TrustScore | None = None,
    domain_info: DomainInfo | None = None,
    error_message: str | None = None,
) -> dict:
    """Build the final result dict that gets persisted and sent to the extension."""
    return {
        "audit_id": audit_id,
        "document_title": live.get("document_title", ""),
        "document_text": live.get("document_text", ""),
        "status": status,
        "stage": stage,
        "stage_label": STAGE_LABELS.get(stage, stage),
        "progress_percent": progress_percent,
        "claims_processed": claims_processed,
        "total_claims": live.get("total_claims", len(claim_verdicts)),
        "claims": [cv.model_dump() for cv in claim_verdicts],
        "trust_score": trust_score.model_dump() if trust_score else None,
        "domain": domain_info.model_dump() if domain_info else live.get("domain"),
        "error_message": error_message,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }