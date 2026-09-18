"""Pydantic models shared across the pipeline."""
from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


ClaimCategory = Literal[
    "statistical",
    "citation",
    "event",
    "person",
    "scientific",
    "legal",
    "medical",
    "financial",
    "general",
]

Verdict = Literal["VERIFIED", "UNVERIFIED", "HALLUCINATED"]

Domain = Literal["healthcare", "legal", "finance", "education", "news", "general"]

GenealogyType = Literal[
    "attribute_swap",
    "amalgamation",
    "temporal_drift",
    "domain_confusion",
    "pure_confabulation",
]


class Claim(BaseModel):
    id: int
    claim_text: str
    claim_category: ClaimCategory = "general"
    high_stakes: bool = False
    source_sentence: str
    char_start: int
    char_end: int


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    source_tier: int = Field(ge=1, le=4)
    relevance_score: float = 0.0


class Genealogy(BaseModel):
    genealogy_type: GenealogyType
    real_fact: str
    mutation_explanation: str
    confidence_in_genealogy: int = Field(ge=0, le=100)


class ClaimVerdict(BaseModel):
    claim: Claim
    verdict: Verdict
    confidence: int = Field(ge=0, le=100)
    reasoning: str
    best_source_url: Optional[str] = None
    best_source_quote: Optional[str] = None
    best_source_tier: Optional[int] = None
    best_source_label: Optional[str] = None
    contradicting_detail: Optional[str] = None
    sources: List[SearchResult] = Field(default_factory=list)
    genealogy: Optional[Genealogy] = None


class TrustScore(BaseModel):
    score: float
    band: Literal[
        "High Trustworthiness",
        "Moderate Trustworthiness",
        "Low Trustworthiness",
        "Unreliable",
    ]
    color: str
    verified_count: int
    unverified_count: int
    hallucinated_count: int
    high_stakes_hallucinations: int


class DomainInfo(BaseModel):
    domain: Domain = "general"
    confidence: int = 0
    reasoning: str = ""


class AuditResult(BaseModel):
    audit_id: str
    document_title: str
    document_text: str
    created_at: str
    status: Literal["processing", "complete", "error"]
    stage: str
    progress_percent: int
    claims_processed: int
    total_claims: int
    claims: List[ClaimVerdict] = Field(default_factory=list)
    trust_score: Optional[TrustScore] = None
    domain: Optional[DomainInfo] = None
    error_message: Optional[str] = None


class StartAuditRequest(BaseModel):
    document_text: str
    document_title: Optional[str] = None


class StartAuditResponse(BaseModel):
    audit_id: str
    status: str
    message: str
    total_claims: Optional[int] = None
    domain: Optional[str] = None


class StatusResponse(BaseModel):
    audit_id: str
    status: str
    stage: str
    progress_percent: int
    claims_processed: int
    total_claims: int
    partial_claims: List[ClaimVerdict] = Field(default_factory=list)
    domain: Optional[DomainInfo] = None
