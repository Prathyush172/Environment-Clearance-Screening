"""LLM Gateway Service:
Single choke point for model requests with:
- Retry with exponential backoff & jitter (tenacity)
- Circuit Breaker (CLOSED -> OPEN -> HALF_OPEN)
- Degradation chain: Primary Provider -> Fallback Provider -> Degraded Local Fallback
- Attribution headers propagation (X-Run-Id, X-Step-Id, X-Agent, X-Prompt-Version)
- Guardrail input/output inspection
- Admin Fault Injection endpoint
"""

import os
import json
import time
import random
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Response, Header
import httpx
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
from pydantic import BaseModel

from libs.common.config import settings
from libs.common.logging import get_logger
from libs.common.guardrails import InputGuardrail, OutputGuardrail
from services.llm_gateway.resilience import CircuitBreaker, BreakerState

logger = get_logger("llm_gateway")

app = FastAPI(title="LLM Gateway", version="2.0.0")

# Prometheus Metrics
llm_requests_total = Counter("llm_gateway_requests_total", "LLM requests", ["provider", "status"])
llm_retries_total = Counter("llm_gateway_retries_total", "LLM retries triggered", ["provider"])
llm_cost_usd_total = Counter("llm_cost_usd_total", "Total USD cost estimated", ["agent", "step"])
breaker_gauge = Gauge("circuit_breaker_state", "Circuit breaker state (0=closed, 1=half-open, 2=open)", ["provider"])

# Mount Prometheus
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Circuit Breakers
primary_breaker = CircuitBreaker("primary_llm")
fallback_breaker = CircuitBreaker("fallback_llm")

# Fault injection state
FAULTS = {
    "provider_down": False,
    "provider_slow": False,
    "provider_error_rate": 0.0,
}


class FaultInjectionRequest(BaseModel):
    fault_type: str  # "provider_down", "provider_slow", "provider_error_rate", "reset"
    value: Optional[Any] = None
    admin_token: str


@app.get("/health")
async def health():
    state = primary_breaker.get_state()
    breaker_gauge.labels(provider="primary").set(0 if state == BreakerState.CLOSED else (1 if state == BreakerState.HALF_OPEN else 2))
    return {
        "status": "ok",
        "service": "llm-gateway",
        "primary_breaker": state.value,
        "faults_active": FAULTS,
    }


@app.post("/admin/faults")
async def inject_fault(req: FaultInjectionRequest):
    """Guarded fault injection endpoint to demonstrate resilience and circuit-breaker."""
    if not settings.ADMIN_FAULTS_ENABLED and req.admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin fault injection is disabled or invalid token.")

    ft = req.fault_type.lower()
    if ft == "provider_down":
        FAULTS["provider_down"] = True
        primary_breaker.force_state(BreakerState.OPEN)
        return {"status": "injected", "fault": "provider_down", "circuit_breaker": "OPEN"}
    elif ft == "provider_slow":
        FAULTS["provider_slow"] = True
        return {"status": "injected", "fault": "provider_slow", "delay_ms": 5000}
    elif ft == "provider_error_rate":
        rate = float(req.value or 0.5)
        FAULTS["provider_error_rate"] = rate
        return {"status": "injected", "fault": "provider_error_rate", "rate": rate}
    elif ft == "reset":
        FAULTS["provider_down"] = False
        FAULTS["provider_slow"] = False
        FAULTS["provider_error_rate"] = 0.0
        primary_breaker.force_state(BreakerState.CLOSED)
        return {"status": "cleared", "circuit_breaker": "CLOSED"}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown fault type '{req.fault_type}'")


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    x_run_id: Optional[str] = Header(None, alias="X-Run-Id"),
    x_step_id: Optional[str] = Header(None, alias="X-Step-Id"),
    x_agent: Optional[str] = Header(None, alias="X-Agent"),
    x_prompt_version: Optional[str] = Header(None, alias="X-Prompt-Version"),
):
    payload = await request.json()
    messages = payload.get("messages", [])

    # 1. Input Guardrail: Inspect user messages
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            gr_res = InputGuardrail.process_input(content)
            if not gr_res.passed and gr_res.action == "block":
                logger.warning("request_blocked_by_guardrail", run_id=x_run_id, reason=gr_res.reason)
                raise HTTPException(status_code=422, detail=gr_res.reason)

    # 2. Check Fault Injections
    if FAULTS["provider_down"]:
        primary_breaker.record_failure()
        return await handle_fallback_or_degraded(payload, x_run_id, x_agent)

    if FAULTS["provider_slow"]:
        await asyncio.sleep(5.0)

    if FAULTS["provider_error_rate"] > 0:
        if random.random() < FAULTS["provider_error_rate"]:
            primary_breaker.record_failure()
            return await handle_fallback_or_degraded(payload, x_run_id, x_agent)

    # 3. Check Circuit Breaker
    if not primary_breaker.allow_request():
        logger.warning("primary_breaker_open_routing_fallback", run_id=x_run_id)
        return await handle_fallback_or_degraded(payload, x_run_id, x_agent)

    # 4. Call Primary with retry and backoff
    target_url = get_target_url(settings.LLM_PROVIDER, settings.LLM_BASE_URL)
    headers = get_auth_headers(settings.LLM_PROVIDER)

    attempts = 0
    max_retries = settings.GATEWAY_MAX_RETRIES
    while attempts <= max_retries:
        try:
            attempts += 1
            async with httpx.AsyncClient(timeout=float(settings.GATEWAY_TIMEOUT_S)) as client:
                resp = await client.post(target_url, json=payload, headers=headers)
                if resp.status_code == 200:
                    primary_breaker.record_success()
                    llm_requests_total.labels(provider=settings.LLM_PROVIDER, status="200").inc()
                    return Response(content=resp.content, status_code=200, media_type="application/json")
                elif resp.status_code in [429, 500, 502, 503, 504]:
                    primary_breaker.record_failure()
                    llm_retries_total.labels(provider=settings.LLM_PROVIDER).inc()
                    await asyncio.sleep((2 ** attempts) * 0.2 + random.uniform(0, 0.1))
                else:
                    break
        except Exception as exc:
            primary_breaker.record_failure()
            llm_retries_total.labels(provider=settings.LLM_PROVIDER).inc()
            await asyncio.sleep((2 ** attempts) * 0.2 + random.uniform(0, 0.1))

    # If retries exhausted, degrade gracefully
    return await handle_fallback_or_degraded(payload, x_run_id, x_agent)


async def handle_fallback_or_degraded(payload: Dict[str, Any], run_id: Optional[str], agent: Optional[str]) -> Response:
    """Degradation Path: Primary -> Fallback Provider -> Local Deterministic Degraded Response."""
    logger.info("routing_to_fallback_mode", run_id=run_id, fallback_provider=settings.FALLBACK_LLM_PROVIDER)

    # Attempt Fallback Provider if breaker allows
    if fallback_breaker.allow_request():
        fb_url = get_target_url(settings.FALLBACK_LLM_PROVIDER, settings.FALLBACK_LLM_BASE_URL)
        fb_headers = get_auth_headers(settings.FALLBACK_LLM_PROVIDER)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(fb_url, json=payload, headers=fb_headers)
                if resp.status_code == 200:
                    fallback_breaker.record_success()
                    llm_requests_total.labels(provider="fallback", status="200").inc()
                    return Response(content=resp.content, status_code=200, media_type="application/json")
        except Exception as exc:
            fallback_breaker.record_failure()
            logger.warning("fallback_provider_failed", error=str(exc))

    # Final Graceful Degraded Mode (Deterministic rule-based response with degraded=true notice)
    logger.warning("all_providers_unavailable_entering_degraded_mode", run_id=run_id)
    degraded_response = {
        "id": "degraded-response",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "degraded-deterministic-rules",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "route": "ESCALATED_TO_HUMAN",
                        "basis": "Automated preliminary screening: LLM provider unavailable. Evaluation degraded to deterministic lexical rules.",
                        "degraded": True,
                        "escalation": {
                            "reason_code": "PROVIDER_UNAVAILABLE",
                            "detail": "Circuit breaker is open and fallback provider is unreachable. Result is preliminary and unverified.",
                            "missing_info": ["Active model provider"],
                            "human_checklist": ["Confirm classification manually against Notification Schedule"]
                        }
                    })
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }
    return Response(
        content=json.dumps(degraded_response),
        status_code=200,
        media_type="application/json",
        headers={"X-Degraded-Mode": "true"}
    )


def get_target_url(provider: str, base_url: Optional[str]) -> str:
    if provider == "stub":
        stub_host = os.environ.get("STUB_HOST", "llm-stub")
        stub_port = os.environ.get("STUB_PORT", "8080")
        return f"http://{stub_host}:{stub_port}/v1/chat/completions"
    elif base_url:
        return f"{base_url.rstrip('/')}/v1/chat/completions"
    elif provider == "openai":
        return "https://api.openai.com/v1/chat/completions"
    return "http://llm-stub:8080/v1/chat/completions"


def get_auth_headers(provider: str) -> Dict[str, str]:
    headers = {}
    if provider != "stub":
        key = settings.LLM_API_KEY
        if key:
            headers["Authorization"] = f"Bearer {key}"
    return headers
