"""Multi-layer Caching and Rate Limiting for Environmental Clearance Service.

1. Embedding Cache: query text -> vector embedding (Redis / in-memory).
2. Retrieval Cache: (normalised_query, filters, index_version) -> passages.
3. Whole-Run Cache: hash(request_payload + prompt_versions + index_version) -> FinalResult.
4. Token Bucket Rate Limiter: client_id and IP based request budgeting.
"""

import time
import hashlib
import json
from typing import Dict, Any, Optional, Tuple

from libs.common.config import settings
from libs.common.logging import get_logger

logger = get_logger("caching_ratelimit")


class MemoryCache:
    """In-memory cache with TTL."""

    def __init__(self):
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            exp, val = self._store[key]
            if time.time() < exp:
                return val
            else:
                del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self._store[key] = (time.time() + ttl_seconds, value)

    def clear(self) -> None:
        self._store.clear()


# Cache instances
embedding_cache = MemoryCache()
retrieval_cache = MemoryCache()
run_cache = MemoryCache()


class TokenBucketRateLimiter:
    """Token bucket rate limiter per client_id and IP."""

    def __init__(
        self,
        rate_per_minute: int = settings.RATE_LIMIT_RPM_PER_CLIENT,
        max_burst: int = 10,
    ):
        self.rate_per_second = rate_per_minute / 60.0
        self.max_tokens = float(max_burst)
        self._buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_update)

    def is_allowed(self, client_key: str) -> Tuple[bool, Optional[int]]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.time()
        if client_key not in self._buckets:
            self._buckets[client_key] = (self.max_tokens - 1.0, now)
            return True, None

        tokens, last_update = self._buckets[client_key]
        elapsed = now - last_update
        tokens = min(self.max_tokens, tokens + elapsed * self.rate_per_second)

        if tokens >= 1.0:
            self._buckets[client_key] = (tokens - 1.0, now)
            return True, None
        else:
            retry_after = int((1.0 - tokens) / self.rate_per_second) + 1
            self._buckets[client_key] = (tokens, now)
            logger.warning("rate_limit_exceeded", client=client_key, retry_after=retry_after)
            return False, retry_after


rate_limiter = TokenBucketRateLimiter()


def hash_request(request_data: Dict[str, Any], prompt_version: str = "v2", index_version: str = "v1") -> str:
    """Computes deterministic hash key for whole-run caching."""
    clean = {
        "client_id": request_data.get("client_id"),
        "description": request_data.get("description", "").strip().lower(),
        "sector_hint": request_data.get("sector_hint"),
        "area_ha": request_data.get("area_ha"),
        "capacity": request_data.get("capacity"),
        "location": request_data.get("location"),
        "proximity": sorted(
            request_data.get("proximity") or [],
            key=lambda x: (x.get("feature_type", ""), x.get("distance_km", 0.0))
        ),
        "prompt_version": prompt_version,
        "index_version": index_version,
    }
    encoded = json.dumps(clean, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
