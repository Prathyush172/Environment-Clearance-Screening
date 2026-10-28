"""Unit tests for Caching and Rate Limiting (Milestone 6)."""

import time
from libs.common.caching import (
    MemoryCache,
    TokenBucketRateLimiter,
    hash_request,
)


def test_memory_cache_ttl():
    """Verify memory cache sets, gets, and respects TTL expiration."""
    cache = MemoryCache()
    cache.set("test_key", {"data": "sample"}, ttl_seconds=1)

    # Immediate retrieval
    hit = cache.get("test_key")
    assert hit is not None
    assert hit["data"] == "sample"

    # After expiration
    time.sleep(1.1)
    miss = cache.get("test_key")
    assert miss is None


def test_token_bucket_rate_limiter():
    """Verify rate limiter allows bursts and throttles when tokens exhausted."""
    # 60 rpm = 1 token/sec, max burst = 2 tokens
    limiter = TokenBucketRateLimiter(rate_per_minute=60, max_burst=2)

    # 1st call -> allowed
    allowed, retry_after = limiter.is_allowed("client_alpha")
    assert allowed is True
    assert retry_after is None

    # 2nd call -> allowed (burst used)
    allowed, retry_after = limiter.is_allowed("client_alpha")
    assert allowed is True

    # 3rd call immediately -> rate limited
    allowed, retry_after = limiter.is_allowed("client_alpha")
    assert allowed is False
    assert retry_after >= 1

    # Different client -> not affected
    allowed_beta, _ = limiter.is_allowed("client_beta")
    assert allowed_beta is True


def test_hash_request_deterministic():
    """Verify identical requests yield identical hash regardless of proximity ordering."""
    req1 = {
        "client_id": "test_corp",
        "description": "Granite quarry covering 10 ha.",
        "sector_hint": "Mining of minerals",
        "proximity": [
            {"feature_type": "national_park", "distance_km": 2.0},
            {"feature_type": "inter_state_boundary", "distance_km": 1.5}
        ]
    }
    req2 = {
        "client_id": "test_corp",
        "description": "Granite quarry covering 10 ha.",
        "sector_hint": "Mining of minerals",
        "proximity": [
            {"feature_type": "inter_state_boundary", "distance_km": 1.5},
            {"feature_type": "national_park", "distance_km": 2.0}
        ]
    }

    h1 = hash_request(req1)
    h2 = hash_request(req2)
    assert h1 == h2
