"""Health and readiness check endpoints."""

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Response, status
from sqlalchemy import text
from libs.common.config import settings
from libs.common.db.session import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "api"}


@router.get("/ready")
async def readiness_check(response: Response):
    checks = {"database": False, "redis": False, "chroma": False}

    # 1. Check PostgreSQL
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = True
    except Exception:
        checks["database"] = False

    # 2. Check Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=2.0)
        pong = await r.ping()
        checks["redis"] = bool(pong)
        await r.aclose()
    except Exception:
        checks["redis"] = False

    # 3. Check Chroma
    try:
        chroma_url = f"http://{settings.CHROMA_HOST}:{settings.CHROMA_PORT}/api/v1/heartbeat"
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(chroma_url)
            checks["chroma"] = resp.status_code == 200
    except Exception:
        checks["chroma"] = False

    all_ready = all(checks.values())
    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if all_ready else "not_ready",
        "service": "api",
        "dependencies": checks,
    }
