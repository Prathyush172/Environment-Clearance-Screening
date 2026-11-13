"""Google Gemini API integration using the official Google Gen AI Python SDK (google-genai).

Provides:
- Structured schema-validated generation with strict Pydantic models
- Automatic model deprecation resolution (e.g. 404 on deprecated models falls back to active Flash versions)
- Rate-limit and transient 503 backoff with jitter
- Accurate token accounting and cost tracking from response usage_metadata
- Secure key handling without logging credentials
"""

import os
os.environ["NO_GCE_CHECK"] = "true"
import json
import time
import random
from typing import Type, TypeVar, Optional, Dict, Any, Tuple
from pydantic import BaseModel
import httpx

from libs.common.config import settings
from libs.common.logging import get_logger

logger = get_logger("gemini_client")

T = TypeVar("T", bound=BaseModel)

# Gemini Flash pricing per 1 million tokens (USD)
FLASH_INPUT_PRICE_PER_M = 0.075
FLASH_OUTPUT_PRICE_PER_M = 0.30

# Known fallback model candidates in order of preference if requested model is 404/deprecated/quota-exhausted
FALLBACK_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
]


class GeminiClient:
    """Wrapper around official Google Gen AI SDK client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        timeout_s: float = 45.0,
        max_retries: int = 3,
    ):
        self.api_key = (
            api_key
            or getattr(settings, "LLM_API_KEY", None)
            or os.getenv("LLM_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        self.model_id = (
            model_id
            or getattr(settings, "LLM_MODEL_ID", None)
            or os.getenv("LLM_MODEL_ID")
            or "gemini-3-flash-preview"
        )
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self._sdk_client = None

    def _get_client(self):
        """Lazy initialization of google-genai Client with custom HTTP transport."""
        if self._sdk_client is None:
            if not self.api_key:
                raise ValueError("Gemini API key is not configured. Set LLM_API_KEY or GEMINI_API_KEY.")
            from google import genai
            from google.genai import types

            self._sdk_client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000)),
            )
        return self._sdk_client

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.0,
        max_output_tokens: int = 2048,
        override_model: Optional[str] = None,
    ) -> Tuple[T, Dict[str, Any]]:
        """Invokes Gemini with structured Pydantic schema validation.
        
        Returns:
            Tuple of (validated_pydantic_instance, usage_and_meta_dict)
        """
        from google.genai import types, errors

        client = self._get_client()
        target_model = override_model or self.model_id

        # Model candidate queue: requested model first, then fallback models
        models_to_try = [target_model]
        for fb in FALLBACK_MODELS:
            if fb != target_model and fb not in models_to_try:
                models_to_try.append(fb)

        cleaned_schema = response_schema
        if isinstance(response_schema, type) and issubclass(response_schema, BaseModel):
            try:
                from google.genai import _transformers
                schema_obj = _transformers.t_schema(None, response_schema)
                def _strip_defaults(s):
                    if hasattr(s, "default"):
                        s.default = None
                    if hasattr(s, "properties") and s.properties:
                        for p in s.properties.values():
                            _strip_defaults(p)
                    if hasattr(s, "items") and s.items:
                        _strip_defaults(s.items)
                _strip_defaults(schema_obj)
                cleaned_schema = schema_obj
            except Exception:
                cleaned_schema = response_schema

        last_error = None
        for current_model in models_to_try:
            attempts = 0
            while attempts <= self.max_retries:
                attempts += 1
                try:
                    config = types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=cleaned_schema,
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                        system_instruction=system_instruction,
                    )
                    t0 = time.time()
                    resp = client.models.generate_content(
                        model=current_model,
                        contents=prompt,
                        config=config,
                    )
                    latency_s = time.time() - t0

                    raw_text = resp.text
                    if not raw_text and resp.candidates:
                        # Extract from parts if resp.text is empty
                        parts = resp.candidates[0].content.parts
                        text_parts = [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
                        raw_text = "".join(text_parts)

                    if not raw_text:
                        raise ValueError(f"Gemini returned empty candidate content from model '{current_model}'")

                    # Parse into Pydantic model
                    parsed = response_schema.model_validate_json(raw_text)

                    # Update default model to the working model
                    self.model_id = current_model

                    # Extract usage metadata
                    usage = resp.usage_metadata
                    prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
                    completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
                    thoughts_tokens = getattr(usage, "thoughts_token_count", 0) or 0
                    total_tokens = getattr(usage, "total_token_count", prompt_tokens + completion_tokens) or (prompt_tokens + completion_tokens)

                    # Cost estimation based on Flash pricing
                    cost_usd = round(
                        (prompt_tokens / 1_000_000.0) * FLASH_INPUT_PRICE_PER_M
                        + ((completion_tokens + thoughts_tokens) / 1_000_000.0) * FLASH_OUTPUT_PRICE_PER_M,
                        6,
                    )

                    meta = {
                        "model_invoked": current_model,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "thoughts_tokens": thoughts_tokens,
                        "total_tokens": total_tokens,
                        "cost_usd": cost_usd,
                        "latency_s": round(latency_s, 3),
                    }
                    return parsed, meta

                except errors.ClientError as ce:
                    # If 404 (model deprecated/not found), break retry loop and try next model
                    if ce.code == 404:
                        logger.warning(
                            "gemini_model_not_found_trying_fallback",
                            attempted_model=current_model,
                            code=ce.code,
                        )
                        last_error = ce
                        break
                    # If 429 rate limit / quota, back off and retry up to max_retries, then try next model candidate
                    elif ce.code == 429:
                        last_error = ce
                        if attempts > self.max_retries:
                            logger.warning("gemini_rate_limit_exceeded_for_model_trying_next", model=current_model)
                            break
                        wait = (2 ** attempts) * 1.0 + random.uniform(0.1, 0.4)
                        logger.warning("gemini_rate_limited", attempt=attempts, wait_s=wait)
                        time.sleep(wait)
                    else:
                        logger.error("gemini_client_error", code=ce.code, error=str(ce))
                        raise

                except errors.ServerError as se:
                    # 503 high demand or 500 server error: retry or switch to fallback model
                    last_error = se
                    if attempts >= 2:
                        logger.warning("gemini_server_unavailable_trying_fallback_model", model=current_model)
                        break
                    wait = 2.0 + random.uniform(0.2, 0.5)
                    logger.warning("gemini_server_unavailable_retrying", attempt=attempts, wait_s=wait)
                    time.sleep(wait)

                except Exception as exc:
                    last_error = exc
                    # Network timeout or transient connection issue
                    if attempts <= self.max_retries:
                        wait = (2 ** attempts) * 1.0 + random.uniform(0.1, 0.3)
                        time.sleep(wait)
                    else:
                        break

        # If all candidates and retries exhausted
        logger.error("gemini_all_models_and_retries_exhausted", last_error=str(last_error))
        raise RuntimeError(f"Gemini API generation failed after retries: {last_error}")
