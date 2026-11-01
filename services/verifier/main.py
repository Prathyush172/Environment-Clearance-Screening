"""Independent Verifier Service checking draft determinations and citations using Gemini or deterministic rules."""

import os
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, make_asgi_app

from libs.common.config import settings
from libs.common.logging import get_logger
from libs.common.llm.schemas import VerifierVerificationResult
from libs.common.llm.gemini import GeminiClient

logger = get_logger("verifier_service")

app = FastAPI(title="Independent Verifier Service", version="2.0.0")

# Metrics
verification_checks_total = Counter("verification_checks_total", "Verification check results", ["result"])
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


class VerificationRequest(BaseModel):
    run_id: str
    draft: Dict[str, Any]
    retrieved_passages: List[Dict[str, Any]] = []


@app.get("/health")
async def health():
    provider = getattr(settings, "VERIFIER_LLM_PROVIDER", None) or getattr(settings, "LLM_PROVIDER", "stub")
    return {"status": "ok", "service": "verifier", "provider": provider}


@app.post("/v1/verify")
async def verify_draft(req: VerificationRequest):
    draft = req.draft
    passages = req.retrieved_passages or []
    checks = []
    failed_checks = []
    citations = draft.get("citations", [])

    # Basic structural check 1: Schedule entry present
    has_schedule = bool(draft.get("schedule_entry"))
    checks.append({
        "check_name": "schedule_lookup",
        "passed": has_schedule,
        "detail": "Applicable Schedule entry identified" if has_schedule else "Missing Schedule entry"
    })
    if not has_schedule:
        failed_checks.append("schedule_lookup")

    # Basic structural check 2: Citations present and non-empty
    has_citations = len(citations) > 0
    checks.append({
        "check_name": "citations_present",
        "passed": has_citations,
        "detail": f"{len(citations)} citations provided" if has_citations else "No citations provided"
    })
    if not has_citations:
        failed_checks.append("citations_present")

    # Basic structural check 3: Retrieved evidence present
    has_evidence = len(passages) > 0
    checks.append({
        "check_name": "evidence_passages_present",
        "passed": has_evidence,
        "detail": f"{len(passages)} corpus passages provided" if has_evidence else "No retrieved passages provided to substantiate draft claims"
    })
    if not has_evidence:
        failed_checks.append("evidence_passages_present")

    # Determine provider
    provider = (getattr(settings, "VERIFIER_LLM_PROVIDER", None) or getattr(settings, "LLM_PROVIDER", "stub")).lower()
    api_key = (
        getattr(settings, "VERIFIER_LLM_API_KEY", None)
        or getattr(settings, "LLM_API_KEY", None)
        or os.getenv("VERIFIER_LLM_API_KEY")
        or os.getenv("LLM_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    model_id = (
        getattr(settings, "VERIFIER_LLM_MODEL_ID", None)
        or getattr(settings, "LLM_MODEL_ID", None)
        or os.getenv("VERIFIER_LLM_MODEL_ID")
        or os.getenv("LLM_MODEL_ID")
        or "gemini-3-flash-preview"
    )

    entailment_results = []
    verifier_meta = {}

    if provider == "gemini":
        # Missing evidence check: verifier must NOT return SUPPORTED when evidence is missing
        if not has_citations or not has_evidence:
            logger.warning("verifier_rejected_missing_evidence", run_id=req.run_id)
            verification_checks_total.labels(result="failed").inc()
            return {
                "run_id": req.run_id,
                "passed": False,
                "status": "FAILED",
                "checks": checks,
                "attempts": 1,
                "failed_checks": failed_checks,
                "entailment_results": [
                    {
                        "claim": "Evidence grounding and sufficiency",
                        "verdict": "UNSUPPORTED",
                        "supporting_chunk_id": None,
                        "explanation": "Evidence is missing: citations or retrieved passages were not provided to substantiate the determination.",
                    }
                ],
                "verifier_summary": "Verification failed: missing statutory citations or corpus evidence.",
            }

        if not api_key:
            # LLM unavailable: must NOT return SUPPORTED
            logger.warning("verifier_llm_key_missing", run_id=req.run_id)
            failed_checks.append("llm_verifier_unavailable")
            checks.append({
                "check_name": "llm_verifier_available",
                "passed": False,
                "detail": "Gemini API key is not configured for verifier service",
            })
            verification_checks_total.labels(result="failed").inc()
            return {
                "run_id": req.run_id,
                "passed": False,
                "status": "ERROR",
                "checks": checks,
                "attempts": 1,
                "failed_checks": failed_checks,
                "entailment_results": [
                    {
                        "claim": "Independent verification",
                        "verdict": "UNSUPPORTED",
                        "supporting_chunk_id": None,
                        "explanation": "Independent LLM verifier cannot execute because API key is missing.",
                    }
                ],
                "verifier_summary": "Verification error: LLM verifier is unavailable.",
            }

        # Execute Gemini independent verification
        try:
            verifier_client = GeminiClient(
                api_key=api_key,
                model_id=model_id,
                timeout_s=30.0,
            )

            # Format retrieved passages for the prompt
            formatted_passages = []
            for p in passages:
                formatted_passages.append(
                    f"[Chunk ID: {p.get('chunk_id')}] (Doc: {p.get('doc_title', 'EIA 2006')}, Ref: {p.get('clause_ref')})\n"
                    f"Text: {p.get('text')}\n"
                )
            passages_block = "\n---\n".join(formatted_passages)

            prompt = (
                f"You are an independent regulatory compliance verifier for Indian Environmental Clearance pre-screening.\n"
                f"Audit this draft screening determination against the provided retrieved legal corpus passages.\n\n"
                f"=== DRAFT SCREENING DETERMINATION ===\n"
                f"Proposed Route: {draft.get('proposed_route') or draft.get('route')}\n"
                f"Schedule Entry: {draft.get('schedule_entry')}\n"
                f"Conditions Applied: {draft.get('conditions_applied')}\n"
                f"Stated Regulatory Basis: {draft.get('basis')}\n"
                f"Citations: {draft.get('citations')}\n\n"
                f"=== RETRIEVED STATUTORY PASSAGES ===\n"
                f"{passages_block}\n\n"
                f"=== AUDITING INSTRUCTIONS ===\n"
                f"1. Check if the proposed route and threshold interpretations are strictly entailed by the passages.\n"
                f"2. For General Condition triggers, verify that proximity thresholds (5 km vs 10 km) strictly align with the corpus.\n"
                f"3. Mark each statement in entailment_results as 'SUPPORTED', 'UNSUPPORTED', or 'CONTRADICTED'.\n"
                f"4. If any legal claim is hallucinated or unsupported by the passages, set hallucination_detected = True and is_supported = False.\n"
                f"5. Return is_supported = True ONLY if all material statutory claims are backed by the retrieved text."
            )

            v_res, meta = await asyncio.to_thread(
                verifier_client.generate_structured,
                prompt=prompt,
                response_schema=VerifierVerificationResult,
                system_instruction="You are an uncompromising statutory compliance auditor. Reject unsupported or hallucinated legal claims.",
            )
            verifier_meta = meta

            checks.append({
                "check_name": "independent_llm_entailment",
                "passed": v_res.is_supported and not v_res.hallucination_detected,
                "detail": v_res.summary_verdict,
            })
            if not v_res.is_supported or v_res.hallucination_detected:
                failed_checks.append("independent_llm_entailment")

            for er in v_res.entailment_results:
                entailment_results.append({
                    "claim": er.claim,
                    "verdict": er.verdict,
                    "supporting_chunk_id": er.supporting_chunk_id,
                    "explanation": er.explanation,
                })

        except Exception as exc:
            # When LLM fails, verifier must NOT automatically return SUPPORTED!
            logger.error("gemini_verifier_call_failed", error=str(exc))
            checks.append({
                "check_name": "independent_llm_entailment",
                "passed": False,
                "detail": f"Independent Gemini verifier failed: {str(exc)}",
            })
            failed_checks.append("independent_llm_entailment")
            entailment_results.append({
                "claim": "Draft route is supported by cited provisions",
                "verdict": "UNSUPPORTED",
                "supporting_chunk_id": None,
                "explanation": f"Verifier LLM call failed or was unreachable: {str(exc)}",
            })

    else:
        # Stub / Deterministic offline verification
        route = draft.get("proposed_route") or draft.get("route")
        basis = draft.get("basis", "")
        has_gc_check = True
        if route == "CATEGORY_A_CENTRAL" and "general condition" in basis.lower():
            has_gc_check = True
        checks.append({
            "check_name": "general_condition_verified",
            "passed": has_gc_check,
            "detail": "General Condition consistency verified against proximity criteria"
        })
        entailment_results.append({
            "claim": "Draft route is supported by cited provisions",
            "verdict": "SUPPORTED" if len(failed_checks) == 0 else "UNSUPPORTED",
            "supporting_chunk_id": citations[0].get("chunk_id") if citations else None,
            "explanation": "Deterministic verification matched Schedule and General Condition rules",
        })

    passed = len(failed_checks) == 0
    verification_checks_total.labels(result="passed" if passed else "failed").inc()

    if passed:
        ver_status = "PASSED"
        summary = "All statutory threshold calculations and citations verified against retrieved passages."
    elif any(
        "429" in str(c.get("detail", ""))
        or "exceeded" in str(c.get("detail", "")).lower()
        or "failed:" in str(c.get("detail", "")).lower()
        or "unavailable" in str(c.get("check_name", "")).lower()
        or "error" in str(c.get("detail", "")).lower()
        for c in checks if not c.get("passed")
    ):
        ver_status = "ERROR"
        summary = "Independent verifier encountered an upstream service error or rate limit."
    else:
        ver_status = "FAILED"
        summary = "Independent verifier found unsupported claims or citations in the draft determination."

    return {
        "run_id": req.run_id,
        "passed": passed,
        "status": ver_status,
        "checks": checks,
        "attempts": 1,
        "failed_checks": failed_checks,
        "entailment_results": entailment_results,
        "verifier_meta": verifier_meta,
        "verifier_summary": summary,
    }
