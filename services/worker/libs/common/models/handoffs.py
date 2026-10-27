"""Typed Pydantic v2 handoff models between pipeline stages and agents."""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    field: str
    value: Any
    confidence: float = Field(ge=0, le=1)
    source: Literal["structured", "text", "inferred"]


class ProximityExtracted(BaseModel):
    feature_type: str
    distance_km: Optional[float] = None
    name: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    source: Literal["structured", "text"]
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None


class IntakeResult(BaseModel):
    run_id: str
    correlation_id: str
    sanitised_description: str
    sector: Optional[str] = None
    sector_confidence: float = Field(default=0.0, ge=0, le=1)
    out_of_corpus: bool = False
    entities: List[ExtractedEntity] = Field(default_factory=list)
    proximity_extracted: List[ProximityExtracted] = Field(default_factory=list)
    escalate: bool = False
    escalation_reason: Optional[str] = None


class Citation(BaseModel):
    citation_id: str
    doc_id: str
    doc_title: str
    clause_ref: Optional[str] = None
    chunk_id: str
    quote: str = Field(max_length=500)  # verbatim snippet
    score: float = Field(default=0.0)


class Claim(BaseModel):
    text: str
    citation_ids: List[str] = Field(default_factory=list)
    supported: bool = True


class ResearchDraft(BaseModel):
    run_id: str
    correlation_id: str
    proposed_route: str  # enum value
    basis: str
    schedule_entry: Optional[Dict[str, Any]] = None
    conditions_applied: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    extracted_entities: List[ExtractedEntity] = Field(default_factory=list)
    retrieved_passages: List[Dict[str, Any]] = Field(default_factory=list)
    steps_used: int = 0
    tool_calls_used: int = 0
    prompt_version: str = "v1"


class VerificationCheck(BaseModel):
    check_name: str
    passed: bool
    detail: Optional[str] = None


class VerificationReport(BaseModel):
    run_id: str
    passed: bool
    checks: List[VerificationCheck] = Field(default_factory=list)
    attempts: int = 1
    failed_checks: List[str] = Field(default_factory=list)
    entailment_results: List[Dict[str, Any]] = Field(default_factory=list)


class EscalationDetail(BaseModel):
    reason_code: str
    detail: str
    missing_info: List[str] = Field(default_factory=list)
    what_was_found: Optional[str] = None
    human_checklist: List[str] = Field(default_factory=list)


class FinalResult(BaseModel):
    run_id: str
    correlation_id: str
    route: str  # NO_CLEARANCE_REQUIRED | CATEGORY_B_STATE | CATEGORY_A_CENTRAL | ESCALATED_TO_HUMAN
    basis: str
    schedule_entry: Optional[Dict[str, Any]] = None
    conditions_applied: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    extracted_entities: List[ExtractedEntity] = Field(default_factory=list)
    confidence: float = 1.0
    verification: VerificationReport
    escalation: Optional[EscalationDetail] = None
    degraded: bool = False
    prompt_versions: Dict[str, str] = Field(default_factory=dict)
    index_version: str = "default"
    cost_summary: Dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = (
        "SCREENING OPINION ONLY: This is not a legal determination of environmental clearance requirements. "
        "An accredited environmental consultant must make the final determination. This system performs "
        "pre-screening only and does not constitute environmental impact assessment."
    )
