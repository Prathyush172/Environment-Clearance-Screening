"""Milestone 2 Agent State and Hand-off Definitions for LangGraph Pipeline."""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Annotated
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """Execution state passed through the LangGraph screening nodes."""
    run_id: str
    correlation_id: str
    request_data: Dict[str, Any]
    
    # Step tracking & loop bounds
    step_count: int = 0
    tool_call_count: int = 0
    replans_count: int = 0
    verification_attempts: int = 0
    start_time: float = 0.0
    
    # Node outputs
    intake_result: Optional[Dict[str, Any]] = None
    retrieved_passages: List[Dict[str, Any]] = Field(default_factory=list)
    modifiers_found: List[Dict[str, Any]] = Field(default_factory=list)
    derived_queries: List[str] = Field(default_factory=list)
    
    # Draft & Citations
    draft_determination: Optional[Dict[str, Any]] = None
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    claims: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Verification & Escalation
    verification_report: Optional[Dict[str, Any]] = None
    escalation_reason: Optional[str] = None
    escalation_detail: Optional[Dict[str, Any]] = None
    is_terminal: bool = False
    route: Optional[str] = None

    # LLM Usage & Cost Tracking
    llm_tokens: Dict[str, Any] = Field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "thoughts_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "models_invoked": [],
        }
    )
    
    # Final Result
    final_result: Optional[Dict[str, Any]] = None
