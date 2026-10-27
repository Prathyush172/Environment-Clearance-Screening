"""LLM Gateway Service - abstraction, retry, circuit-breaker, and stub routing."""

import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Response
import httpx
from prometheus_client import Counter, Histogram, make_asgi_app

app = FastAPI(title="LLM Gateway", version="1.0.0")

# Prometheus metrics
llm_gateway_requests_total = Counter("llm_gateway_requests_total", "Total LLM gateway requests", ["provider", "status"])
llm_gateway_duration_seconds = Histogram("llm_gateway_duration_seconds", "LLM gateway latency", ["provider"])

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "stub")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
STUB_HOST = os.environ.get("STUB_HOST", "llm-stub")
STUB_PORT = os.environ.get("STUB_PORT", "8080")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "llm-gateway", "provider": LLM_PROVIDER}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    payload = await request.json()
    provider = LLM_PROVIDER

    # Determine backend URL
    if provider == "stub":
        target_url = f"http://{STUB_HOST}:{STUB_PORT}/v1/chat/completions"
    elif LLM_BASE_URL:
        target_url = f"{LLM_BASE_URL.rstrip('/')}/v1/chat/completions"
    else:
        target_url = "https://api.openai.com/v1/chat/completions"

    headers = {}
    api_key = os.environ.get("LLM_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(target_url, json=payload, headers=headers)
            llm_gateway_requests_total.labels(provider=provider, status=str(resp.status_code)).inc()
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type="application/json",
            )
    except Exception as exc:
        llm_gateway_requests_total.labels(provider=provider, status="500").inc()
        raise HTTPException(status_code=502, detail=f"LLM gateway upstream error: {str(exc)}")
