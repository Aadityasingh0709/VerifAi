"""FastAPI router — all VerifAI audit endpoints."""
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response

from backend.data.mock_fixtures import get_correct_information
from backend.data.samples import SAMPLES, get_sample
from backend.db.database import create_initial, get_live, load_final, update_live
from backend.models.schemas import (
    AuditResult,
    DomainInfo,
    StartAuditRequest,
    StartAuditResponse,
    StatusResponse,
)
from backend.services.claim_extractor import extract_claims
from backend.services.domain_detector import detect_domain
from backend.services.pipeline import run_audit
from backend.services.report_generator import render_pdf_bytes

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _launch_audit(audit_id: str) -> None:
    """Run the async audit pipeline in a fresh event loop (background task)."""
    asyncio.run(run_audit(audit_id))


@router.post("/start", response_model=StartAuditResponse)
def start_audit(req: StartAuditRequest, background: BackgroundTasks) -> StartAuditResponse:
    text = (req.document_text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="document_text is required")
    audit_id = uuid.uuid4().hex[:12]
    title = (req.document_title or text[:48] + ("..." if len(text) > 48 else "")).strip() or "Untitled document"
    create_initial(audit_id, title, text)

    # Quick synchronous preview so the extension can render the domain pill
    # and claim count immediately, before the async pipeline ramps up.
    try:
        preview_domain = detect_domain(text, title)
    except Exception:
        preview_domain = DomainInfo(domain="general", confidence=0, reasoning="")
    try:
        preview_claims = extract_claims(text, title)
        total = len(preview_claims)
    except Exception:
        preview_claims = []
        total = 0

    update_live(
        audit_id,
        preview_domain=preview_domain.model_dump(),
        preview_claims=[c.model_dump() for c in preview_claims],
        total_claims=total,
    )

    background.add_task(_launch_audit, audit_id)
    return StartAuditResponse(
        audit_id=audit_id,
        status="processing",
        message="Audit started",
        total_claims=total,
        domain=preview_domain.domain,
    )


def _load_result(audit_id: str) -> dict:
    live = get_live(audit_id)
    if live:
        return live
    persisted = load_final(audit_id)
    if persisted:
        return persisted
    raise HTTPException(status_code=404, detail=f"audit {audit_id} not found")


@router.get("/{audit_id}/status", response_model=StatusResponse)
def get_status(audit_id: str) -> StatusResponse:
    data = _load_result(audit_id)
    dom = data.get("domain")
    if dom and not isinstance(dom, DomainInfo):
        try:
            dom = DomainInfo.model_validate(dom)
        except Exception:
            dom = None
    return StatusResponse(
        audit_id=audit_id,
        status=data.get("status", "processing"),
        stage=data.get("stage_label") or data.get("stage", "queued"),
        progress_percent=data.get("progress_percent", 0),
        claims_processed=data.get("claims_processed", 0),
        total_claims=data.get("total_claims", 0),
        partial_claims=data.get("claims", []) or [],
        domain=dom,
    )


@router.get("/{audit_id}/results")
def get_results(audit_id: str) -> dict:
    data = _load_result(audit_id)
    # Attach correct information if available
    doc_text = data.get("document_text", "")
    correct_info = get_correct_information(doc_text)
    if correct_info:
        data["correct_information"] = correct_info
    return data


@router.get("/{audit_id}/report.pdf")
def get_report_pdf(audit_id: str) -> Response:
    data = _load_result(audit_id)
    if data.get("status") != "complete":
        raise HTTPException(status_code=409, detail="audit not yet complete")
    result = AuditResult.model_validate({
        **data,
        "trust_score": data.get("trust_score") if data.get("trust_score") else None,
    })
    pdf_bytes = render_pdf_bytes(result)
    filename = f"verifai-audit-{audit_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ------------------------------------------------------------------
# Sample documents for the demo UI
# ------------------------------------------------------------------
@router.get("/samples/list")
def list_samples() -> dict:
    return {"samples": SAMPLES}


@router.get("/samples/{sample_id}")
def get_sample_detail(sample_id: str) -> dict:
    s = get_sample(sample_id)
    if not s:
        raise HTTPException(status_code=404, detail="sample not found")
    return s
