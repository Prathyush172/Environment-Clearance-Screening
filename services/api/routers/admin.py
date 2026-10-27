"""Admin router for fault injection and system diagnostics."""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from libs.common.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


class FaultInjectionRequest(BaseModel):
    fault_type: str  # e.g. "provider_down", "latency_spike", "corrupt_index"
    params: Optional[Dict[str, Any]] = None


@router.post("/faults")
async def inject_fault(
    payload: FaultInjectionRequest,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    if not settings.ADMIN_FAULTS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin fault injection is disabled in this environment (ADMIN_FAULTS_ENABLED=false)",
        )

    if not x_admin_token or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")

    return {
        "status": "applied",
        "fault_type": payload.fault_type,
        "params": payload.params,
    }
