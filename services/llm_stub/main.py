"""Deterministic LLM Stub Service mimicking OpenAI chat completions API."""

import os
import time
import uuid
import random
import asyncio
import json
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="LLM Stub Service", version="1.0.0")

STUB_DELAY_MS_MIN = int(os.environ.get("STUB_DELAY_MS_MIN", "1500"))
STUB_DELAY_MS_MAX = int(os.environ.get("STUB_DELAY_MS_MAX", "4000"))
STUB_ERROR_RATE = float(os.environ.get("STUB_ERROR_RATE", "0.0"))


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "stub-model"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.0
    max_tokens: Optional[int] = 1000


@app.get("/health")
async def health():
    return {"status": "ok", "service": "llm-stub"}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    # Simulated failure
    if STUB_ERROR_RATE > 0.0 and random.random() < STUB_ERROR_RATE:
        raise HTTPException(status_code=500, detail="Simulated LLM stub provider internal error")

    # Simulated latency
    delay_ms = random.uniform(STUB_DELAY_MS_MIN, STUB_DELAY_MS_MAX)
    await asyncio.sleep(delay_ms / 1000.0)

    # Extract all prompt text
    all_text = " ".join([m.content for m in req.messages]).lower()
    prompt_len = sum(len(m.content) for m in req.messages)

    # Deterministic canned responses
    if "verify" in all_text:
        content_obj = {
            "passed": True,
            "checks": [
                {"check_name": "schedule_lookup", "passed": True, "detail": "Applicable schedule item identified"},
                {"check_name": "general_condition", "passed": True, "detail": "General Condition checked properly"},
                {"check_name": "groundedness", "passed": True, "detail": "All basis claims grounded in retrieved passages"}
            ],
            "entailment_results": [
                {
                    "claim": "Project falls under Mining of Minerals",
                    "verdict": "SUPPORTED",
                    "supporting_chunk_id": "chunk_schedule_1a",
                    "explanation": "Direct match from Schedule Item 1(a)"
                }
            ],
            "failed_checks": []
        }
    elif "intake" in all_text or "classify" in all_text or "sector" in all_text:
        content_obj = {
            "sector": "Mining of Minerals",
            "sector_confidence": 0.85,
            "out_of_corpus": False,
            "entities": [
                {"field": "project_type", "value": "bauxite_mining", "confidence": 0.9, "source": "text"},
                {"field": "mining_lease_area", "value": 45.0, "confidence": 0.95, "source": "structured"}
            ],
            "proximity_extracted": [],
            "escalate": False,
            "escalation_reason": None
        }
    elif "determine" in all_text or "category" in all_text or "researcher" in all_text:
        # Check if proximity or national park mentioned in prompt
        is_near_protected = "national park" in all_text or "wildlife sanctuary" in all_text or "2 km" in all_text or "2km" in all_text
        if is_near_protected:
            route = "CATEGORY_A_CENTRAL"
            basis = (
                "The project is a mining proposal (< 50 ha lease area) which initially qualifies as Category 'B' "
                "under Item 1(a) of the Schedule. However, the project is located 2 km from a National Park. "
                "Under the General Condition (GC) of the EIA Notification 2006, any Category 'B' project located within "
                "5 km of a Protected Area notified under the Wild Life (Protection) Act, 1972 is appraised at the Central Level as Category 'A'."
            )
            conditions = [{"condition": "General Condition (GC)", "trigger": "Proximity <= 5 km to National Park", "effect": "Upgraded from Category B to Category A (Central Level)"}]
        else:
            route = "CATEGORY_B_STATE"
            basis = (
                "The project is an open-cast mining project covering an area of 45 hectares. "
                "Under Item 1(a) of the Schedule to EIA Notification 2006, mining lease area < 50 ha falls under Category 'B'. "
                "No General Condition modifiers apply based on provided proximity data."
            )
            conditions = []

        content_obj = {
            "route": route,
            "basis": basis,
            "schedule_entry": {
                "item_no": "1(a)",
                "project_or_activity": "(i) Mining of minerals",
                "category_a": ">= 50 ha of mining lease area",
                "category_b": "< 50 ha of mining lease area"
            },
            "conditions_applied": conditions,
            "citations": [
                {
                    "citation_id": "cit_1a",
                    "doc_id": "eia_2006_master",
                    "doc_title": "EIA Notification 2006",
                    "clause_ref": "Schedule Item 1(a)",
                    "chunk_id": "chunk_schedule_1a",
                    "quote": "Mining of minerals: Category B < 50 ha of mining lease area.",
                    "score": 0.92
                }
            ],
            "claims": [
                {"text": "Project lease area is under 50 ha.", "citation_ids": ["cit_1a"], "supported": True}
            ],
            "confidence": 0.95
        }
    else:
        content_obj = {
            "message": "Screening analysis completed successfully.",
            "status": "PROCESSED"
        }

    content_str = json.dumps(content_obj)
    prompt_tokens = max(1, prompt_len // 4)
    completion_tokens = 150

    return {
        "id": f"chatcmpl-stub-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content_str
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
    }
