"""Stage 6 — trust score calculator + WeasyPrint PDF audit report."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import List

from backend.models.schemas import AuditResult, ClaimVerdict, TrustScore
from backend.services.domain_detector import get_domain_rules

_WEIGHTS = {"VERIFIED": 1.0, "UNVERIFIED": 0.4, "HALLUCINATED": 0.0}
_COLOR = {
    "High Trustworthiness": "#22c55e",
    "Moderate Trustworthiness": "#f59e0b",
    "Low Trustworthiness": "#f97316",
    "Unreliable": "#ef4444",
}


def _band(score: float) -> str:
    if score >= 85:
        return "High Trustworthiness"
    if score >= 60:
        return "Moderate Trustworthiness"
    if score >= 35:
        return "Low Trustworthiness"
    return "Unreliable"


def calculate_trust_score(claims: List[ClaimVerdict], domain: str = "general") -> TrustScore:
    verified = sum(1 for c in claims if c.verdict == "VERIFIED")
    unverified = sum(1 for c in claims if c.verdict == "UNVERIFIED")
    hallucinated = sum(1 for c in claims if c.verdict == "HALLUCINATED")
    hs_hall = sum(1 for c in claims if c.verdict == "HALLUCINATED" and c.claim.high_stakes)

    if not claims:
        return TrustScore(
            score=0.0, band="Unreliable", color=_COLOR["Unreliable"],
            verified_count=0, unverified_count=0, hallucinated_count=0,
            high_stakes_hallucinations=0,
        )

    weighted_sum = sum(_WEIGHTS[c.verdict] * (c.confidence / 100.0) for c in claims)
    raw_score = (weighted_sum / len(claims)) * 100.0
    penalty_multiplier = get_domain_rules(domain)["penalty_multiplier"]
    final_score = max(0.0, raw_score - (hs_hall * 10.0 * penalty_multiplier))
    final_score = round(final_score, 1)
    band = _band(final_score)
    return TrustScore(
        score=final_score,
        band=band,  # type: ignore[arg-type]
        color=_COLOR[band],
        verified_count=verified,
        unverified_count=unverified,
        hallucinated_count=hallucinated,
        high_stakes_hallucinations=hs_hall,
    )


# ------------------------------------------------------------------
# PDF rendering
# ------------------------------------------------------------------
def _verdict_badge(verdict: str) -> str:
    color = {"VERIFIED": "#22c55e", "UNVERIFIED": "#f59e0b", "HALLUCINATED": "#ef4444"}.get(verdict, "#64748b")
    return f'<span class="badge" style="background:{color}">{verdict}</span>'


def _render_claim_html(cv: ClaimVerdict) -> str:
    src = ""
    if cv.best_source_url:
        quote = html.escape(cv.best_source_quote or "")
        label = html.escape(cv.best_source_label or "Standard")
        src = (
            f'<div class="source"><b>Best source:</b> '
            f'<a href="{html.escape(cv.best_source_url)}">{html.escape(cv.best_source_url)}</a> '
            f'<span class="tier">[{label}]</span><br><i>\u201c{quote}\u201d</i></div>'
        )
    geneal_block = ""
    if cv.genealogy:
        geneal_block = (
            f'<div class="genealogy">'
            f'<b>Forensic genealogy ({cv.genealogy.genealogy_type.replace("_", " ")}):</b><br>'
            f'<b>Real fact:</b> {html.escape(cv.genealogy.real_fact)}<br>'
            f'<b>Mutation:</b> {html.escape(cv.genealogy.mutation_explanation)}<br>'
            f'<b>Analyst confidence:</b> {cv.genealogy.confidence_in_genealogy}%'
            f'</div>'
        )
    hs = '<span class="hs">\u26a0 HIGH STAKES</span>' if cv.claim.high_stakes else ""
    contradicting = (
        f'<div class="contradicting"><b>Contradicted by evidence:</b> {html.escape(cv.contradicting_detail)}</div>'
        if cv.contradicting_detail else ""
    )
    return (
        f'<div class="claim">'
        f'<div class="claim-head"><span class="claim-id">#{cv.claim.id}</span> {_verdict_badge(cv.verdict)} '
        f'<span class="conf">Confidence: {cv.confidence}%</span> {hs}</div>'
        f'<div class="claim-text">{html.escape(cv.claim.claim_text)}</div>'
        f'<div class="reasoning"><b>Reasoning:</b> {html.escape(cv.reasoning)}</div>'
        f'{contradicting}{src}{geneal_block}'
        f'</div>'
    )


def _pdf_css() -> str:
    return """
    @page { size: A4; margin: 22mm 18mm; @bottom-center { content: "This report was generated automatically by VerifAI. Verdicts are probabilistic, not legal determinations.  \u2014  page " counter(page) " of " counter(pages); color: #64748b; font-size: 8.5pt; } }
    body { font-family: 'Helvetica', sans-serif; color: #0f172a; font-size: 10.5pt; line-height: 1.45; }
    h1 { font-size: 22pt; margin: 0 0 4pt 0; }
    h2 { font-size: 14pt; border-bottom: 2px solid #0f172a; padding-bottom: 4pt; margin-top: 18pt; }
    .cover { text-align: center; padding: 30pt 0; border: 2px solid #0f172a; margin-bottom: 20pt; }
    .cover h1 { font-size: 26pt; }
    .cover .subtitle { color: #64748b; font-size: 11pt; margin-bottom: 20pt; }
    .score-big { font-size: 72pt; font-weight: bold; }
    .band { font-size: 16pt; padding: 6pt 12pt; border-radius: 6pt; color: #fff; display: inline-block; margin-top: 8pt; }
    .domain-pill { display:inline-block; margin-top:10pt; padding:4pt 10pt; background:#2563eb; color:#fff; border-radius:12pt; font-size:10pt; }
    .stats { display: flex; justify-content: space-around; margin: 18pt 0; }
    .stat { text-align: center; padding: 10pt 14pt; border-radius: 8pt; }
    .stat .num { font-size: 22pt; font-weight: bold; display: block; }
    .stat .label { font-size: 9pt; color: #64748b; }
    .claim { border: 1px solid #e2e8f0; border-left: 5px solid #cbd5e1; border-radius: 6pt; padding: 10pt 12pt; margin: 10pt 0; page-break-inside: avoid; }
    .claim-head { margin-bottom: 6pt; }
    .claim-id { font-weight: bold; color: #64748b; margin-right: 6pt; }
    .claim-text { font-size: 11pt; margin: 6pt 0; font-weight: 600; }
    .reasoning, .source, .genealogy, .contradicting { margin-top: 6pt; font-size: 9.5pt; }
    .genealogy { background: #fef2f2; padding: 8pt; border-radius: 4pt; border-left: 3px solid #ef4444; }
    .contradicting { background: #fff7ed; padding: 6pt; border-radius: 4pt; }
    .badge { color: #fff; padding: 2pt 8pt; border-radius: 4pt; font-size: 9pt; font-weight: bold; }
    .tier { color:#2563eb; font-size:9pt; font-weight:bold; }
    .hs { color: #b91c1c; font-size: 9pt; margin-left: 6pt; }
    .conf { color: #475569; font-size: 9pt; margin-left: 8pt; }
    .methodology { background: #f1f5f9; padding: 12pt; border-radius: 6pt; font-size: 9.5pt; }
    .disclaimer { font-size: 8.5pt; color: #64748b; font-style: italic; margin-top: 20pt; }
    a { color: #2563eb; text-decoration: none; }
    """


def render_pdf_bytes(result: AuditResult) -> bytes:
    """Render the audit report to PDF bytes using WeasyPrint."""
    from weasyprint import HTML, CSS

    ts = result.trust_score or calculate_trust_score(result.claims)
    domain_name = (result.domain.domain.title() if result.domain else "General")
    created = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    verified = ts.verified_count
    unverified = ts.unverified_count
    hallucinated = ts.hallucinated_count

    claim_htmls = "\n".join(_render_claim_html(c) for c in result.claims)

    halluc = [c for c in result.claims if c.verdict == "HALLUCINATED" and c.genealogy]
    geneal_section = ""
    if halluc:
        geneal_items = "\n".join(
            f'<div class="claim"><div class="claim-head"><span class="claim-id">#{c.claim.id}</span> '
            f'<b>{c.genealogy.genealogy_type.replace("_", " ").title()}</b></div>'
            f'<div class="claim-text">{html.escape(c.claim.claim_text)}</div>'
            f'<div class="genealogy"><b>Real fact:</b> {html.escape(c.genealogy.real_fact)}<br>'
            f'<b>How the model went wrong:</b> {html.escape(c.genealogy.mutation_explanation)}</div></div>'
            for c in halluc
        )
        geneal_section = f'<h2>Hallucination Forensics</h2>{geneal_items}'

    doc = f"""
    <!doctype html>
    <html><head><meta charset="utf-8"><title>VerifAI Hallucination Audit Certificate</title></head>
    <body>
      <div class="cover">
        <h1>VerifAI Hallucination Audit Certificate</h1>
        <div class="subtitle">Real-Time Hallucination Audit Trail for AI-Generated Text</div>
        <div><b>Document:</b> {html.escape(result.document_title or 'Untitled')}</div>
        <div><b>Audit timestamp:</b> {created}</div>
        <div><b>Audit ID:</b> {html.escape(result.audit_id)}</div>
        <div class="score-big" style="color: {ts.color}">{ts.score}</div>
        <div class="band" style="background: {ts.color}">{ts.band}</div>
        <div class="domain-pill">Detected domain: {html.escape(domain_name)}</div>
      </div>

      <h2>Executive Summary</h2>
      <div class="stats">
        <div class="stat" style="background:#dcfce7"><span class="num" style="color:#166534">{verified}</span><span class="label">Verified</span></div>
        <div class="stat" style="background:#fef3c7"><span class="num" style="color:#92400e">{unverified}</span><span class="label">Unverified</span></div>
        <div class="stat" style="background:#fee2e2"><span class="num" style="color:#991b1b">{hallucinated}</span><span class="label">Hallucinated</span></div>
        <div class="stat" style="background:#fef2f2"><span class="num" style="color:#7f1d1d">{ts.high_stakes_hallucinations}</span><span class="label">High-stakes hallucinations</span></div>
      </div>

      <h2>Claim-by-Claim Breakdown</h2>
      {claim_htmls}

      {geneal_section}

      <h2>Methodology</h2>
      <div class="methodology">
        VerifAI extracts atomic factual claims, auto-detects document domain,
        then searches the open web for corroborating or contradicting evidence
        via a Tavily \u2192 Serper \u2192 Brave fallback chain. Each claim receives a
        three-tier verdict (VERIFIED / UNVERIFIED / HALLUCINATED) with a
        confidence score adjusted by the trustworthiness tier of the supporting
        source and the document domain. Healthcare, legal, and financial
        documents apply a stricter source-tier requirement.<br><br>
        \u2022 <b>Tier 1 (High Trust):</b> .gov / .edu / peer-reviewed journals / major wire services.<br>
        \u2022 <b>Tier 2 (Trusted):</b> Britannica, Wikipedia, leading newspapers.<br>
        \u2022 <b>Tier 3 (Standard):</b> General web sources.<br>
        \u2022 <b>Tier 4 (Low Trust):</b> Blogs, social, user-generated platforms.<br><br>
        For HALLUCINATED claims, a forensic genealogy pass diagnoses how the
        underlying model likely mutated a real fact (attribute swap,
        amalgamation, temporal drift, domain confusion, pure confabulation).
      </div>

      <div class="disclaimer">
        This report was generated automatically by VerifAI. Verdicts are
        probabilistic, not legal determinations. High-stakes claims (medical,
        legal, financial) should always be independently reviewed by a qualified
        professional before being acted upon.
      </div>
    </body></html>
    """
    return HTML(string=doc).write_pdf(stylesheets=[CSS(string=_pdf_css())])
