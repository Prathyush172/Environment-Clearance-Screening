"""Strict Pydantic schemas for Gemini structured outputs across the screening lifecycle."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ProximityEntity(BaseModel):
    """Structured representation of a spatial proximity mention."""
    feature_type: str = Field(
        description="Type of sensitive feature, e.g. national_park, wildlife_sanctuary, esz, biosphere_reserve, forest, river, interstate_boundary, etc."
    )
    distance_km: Optional[float] = Field(
        default=None,
        description="Distance in kilometers, if specified numerically in the text"
    )
    raw_distance_text: Optional[str] = Field(
        default=None,
        description="Verbatim textual mention of distance or proximity (e.g. '7 km', 'near national park')"
    )
    is_ambiguous: Optional[bool] = Field(
        default=None,
        description="True if proximity is qualitative/vague (e.g. 'near', 'close to', 'adjacent') without an exact number"
    )


class IntakeExtractionSchema(BaseModel):
    """Schema for project description understanding and structured entity extraction."""
    project_summary: str = Field(
        description="Brief objective summary of the proposed project and primary industrial/development activities"
    )
    classified_sector: str = Field(
        description="Sector name mapped or identified from the project description (e.g. 'Mining of minerals', 'Thermal Power Plants', 'River Valley Projects', 'Highways', 'Synthetic organic chemicals industry', etc.)"
    )
    schedule_item_hint: Optional[str] = Field(
        default=None,
        description="Tentative schedule item code if discernible (e.g. '1(a)', '1(c)', '1(d)', '5(f)', '7(c)', '8(a)', etc.)"
    )
    capacity_value: Optional[float] = Field(
        default=None,
        description="Extracted numerical capacity or throughput quantity (e.g. 500, 45, 120)"
    )
    capacity_unit: Optional[str] = Field(
        default=None,
        description="Extracted capacity unit (e.g. 'MW', 'ha', 'TPA', 'klpd', 'km')"
    )
    area_ha: Optional[float] = Field(
        default=None,
        description="Extracted total project area in hectares, if mentioned"
    )
    proximities: List[ProximityEntity] = Field(
        description="Extracted proximity relationships to sensitive or protected features"
    )
    is_out_of_corpus: bool = Field(
        description="True if project activity clearly falls outside the Schedule of the EIA Notification 2006 (e.g. purely commercial software IT parks, space satellites, agriculture, etc.)"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Extraction confidence score"
    )


class GroundedRegulatoryExplanation(BaseModel):
    """Schema for evidence-grounded regulatory reasoning drafted by Gemini."""
    regulatory_basis: str = Field(
        description="Detailed legal reasoning and statutory analysis grounded strictly in the cited EIA Notification Schedule and General Condition clauses"
    )
    threshold_analysis: str = Field(
        description="Explicit statutory threshold comparison explaining why the project meets or does not meet Category A or Category B criteria"
    )
    general_condition_analysis: str = Field(
        description="Analysis of General Condition (GC) applicability based on distance to protected features and statutory distance limits (5 km vs 10 km)"
    )
    grounded_in_citations: bool = Field(
        description="True if all assertions are backed strictly by the provided corpus citations"
    )


class EntailmentClaimCheck(BaseModel):
    """Schema for independent claim-level verification against retrieved evidence."""
    claim: str = Field(
        description="The specific regulatory or factual statement being verified"
    )
    verdict: str = Field(
        description="Must be strictly one of: 'SUPPORTED', 'UNSUPPORTED', 'CONTRADICTED'"
    )
    supporting_chunk_id: Optional[str] = Field(
        default=None,
        description="The chunk_id of the retrieved passage providing evidence for the claim, or null if unsupported"
    )
    explanation: str = Field(
        description="Verification reasoning citing specific phrases or numbers from the retrieved passages"
    )


class VerifierVerificationResult(BaseModel):
    """Schema for independent evidence-based verification of screening determinations."""
    is_supported: bool = Field(
        description="True ONLY if the proposed route, statutory threshold comparisons, and General Condition findings are fully supported by the retrieved passages"
    )
    entailment_results: List[EntailmentClaimCheck] = Field(
        description="Individual claim verification checks"
    )
    evidence_sufficiency: str = Field(
        description="Rating of evidence sufficiency: 'HIGH', 'MEDIUM', 'LOW', or 'INSUFFICIENT'"
    )
    hallucination_detected: bool = Field(
        description="True if the draft determination cites facts, rules, or thresholds absent from the retrieved passages"
    )
    summary_verdict: str = Field(
        description="Independent verifier commentary summarizing why the draft is supported or rejected"
    )
