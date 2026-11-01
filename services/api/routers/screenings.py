"""Screenings router: submission, status polling, trace, and SSE events."""

import uuid
import json
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request, Response, HTTPException, Header, Depends, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy import select, or_, func
from celery import Celery

from libs.common.config import settings
from libs.common.db.session import get_db_session
from libs.common.db.models import Run, RunStep, Quarantine, RunStatus, User
from libs.common.models.screening_request import ScreeningRequest
from services.api.auth import get_current_user
from services.api.metrics import runs_queued_total, validation_rejected_total
from services.api.validation import (
    sanitise_description,
    validate_description_not_empty_after_sanitisation,
    validate_capacity_unit_sector_compatibility,
    validate_lat_lon_state_consistency,
    validate_proximity_no_duplicates,
    validate_proximity_critically_polluted_needs_name_or_district,
    validate_area_ha_plausible_for_unit,
)

router = APIRouter(prefix="/v1/screenings", tags=["screenings"])

# Celery client for enqueuing screening tasks
celery_app = Celery("screening_api", broker=settings.REDIS_URL)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_screening(
    request: Request,
    current_user: User = Depends(get_current_user),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    correlation_id = x_correlation_id or str(uuid.uuid4())
    client_ip = request.client.host if request.client else None

    # Parse raw JSON body
    try:
        raw_payload = await request.json()
    except Exception as exc:
        validation_rejected_total.labels(reason="malformed_json").inc()
        # Quarantine malformed payload
        async with get_db_session() as session:
            q_entry = Quarantine(
                correlation_id=correlation_id,
                raw_payload_json={"raw": str(exc)},
                field_errors_json=[{"loc": ["body"], "msg": "Invalid JSON format"}],
                client_ip=client_ip,
            )
            session.add(q_entry)
        raise HTTPException(status_code=422, detail="Invalid JSON format")

    # Step 2: Validate request using Pydantic and custom cross-field validators
    errors = []
    try:
        screening_req = ScreeningRequest(**raw_payload)
    except ValidationError as val_err:
        errors.extend(val_err.errors())
        screening_req = None

    if screening_req:
        # Cross-field checks
        try:
            validate_description_not_empty_after_sanitisation(screening_req.description)
            validate_capacity_unit_sector_compatibility(screening_req.capacity, screening_req.sector_hint)
            validate_lat_lon_state_consistency(
                screening_req.location.latitude,
                screening_req.location.longitude,
                screening_req.location.state,
            )
            validate_proximity_no_duplicates(screening_req.proximity)
            validate_proximity_critically_polluted_needs_name_or_district(
                screening_req.proximity, screening_req.location.district
            )
            validate_area_ha_plausible_for_unit(screening_req.area_ha, screening_req.capacity)
        except ValueError as custom_err:
            errors.append({"loc": ["cross_field"], "msg": str(custom_err), "type": "value_error"})

    # If any validation errors occurred, quarantine and return 422
    if errors:
        validation_rejected_total.labels(reason="validation_error").inc()
        # Sanitize raw payload before recording
        safe_payload = {k: v for k, v in raw_payload.items()}
        if "description" in safe_payload:
            safe_payload["description"] = sanitise_description(str(safe_payload["description"]))[:500]

        async with get_db_session() as session:
            q_entry = Quarantine(
                correlation_id=correlation_id,
                raw_payload_json=safe_payload,
                field_errors_json=errors,
                client_ip=client_ip,
            )
            session.add(q_entry)

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Request validation failed",
                "correlation_id": correlation_id,
                "errors": errors,
            },
        )

    # Step 3: Success path - bind client_id and user_id to authenticated user
    run_id = str(uuid.uuid4())
    req_data = screening_req.model_dump()
    req_data["description"] = sanitise_description(screening_req.description)
    # Enforce data isolation: client_id is scoped to authenticated user
    effective_client_id = current_user.client_id
    req_data["client_id"] = effective_client_id

    async with get_db_session() as session:
        new_run = Run(
            id=run_id,
            run_id=run_id,
            correlation_id=correlation_id,
            client_id=effective_client_id,
            user_id=current_user.id,
            project_name=screening_req.project_name,
            description=req_data["description"],
            status=RunStatus.QUEUED,
            task_id=run_id,
        )
        session.add(new_run)

    # Enqueue task in Celery if broker is reachable, else execute in async background
    enqueued = False
    try:
        celery_app.send_task(
            "run_screening",
            args=[run_id, req_data, correlation_id],
            task_id=run_id,
            queue="screening",
        )
        enqueued = True
    except Exception:
        enqueued = False

    if not enqueued:
        from datetime import datetime, timezone
        from services.worker.graph_agent import ScreeningAgentGraph

        async def _execute_local_agent():
            try:
                graph = ScreeningAgentGraph()
                result = await graph.run(run_id, req_data, correlation_id)
                async with get_db_session() as session:
                    q = select(Run).where(Run.id == run_id)
                    r = await session.execute(q)
                    run_obj = r.scalar_one_or_none()
                    if run_obj:
                        route_val = result.get("route")
                        run_obj.status = RunStatus.COMPLETED if route_val != "ESCALATED_TO_HUMAN" else RunStatus.ESCALATED
                        run_obj.route = route_val
                        run_obj.result_json = result
                        run_obj.completed_at = datetime.now(timezone.utc)
                        session.add(run_obj)
            except Exception as bg_exc:
                async with get_db_session() as session:
                    q = select(Run).where(Run.id == run_id)
                    r = await session.execute(q)
                    run_obj = r.scalar_one_or_none()
                    if run_obj:
                        run_obj.status = RunStatus.FAILED
                        run_obj.result_json = {"error": str(bg_exc)}
                        run_obj.completed_at = datetime.now(timezone.utc)
                        session.add(run_obj)

        asyncio.create_task(_execute_local_agent())

    runs_queued_total.inc()

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "run_id": run_id,
            "status_url": f"/v1/screenings/{run_id}",
            "correlation_id": correlation_id,
            "status": "QUEUED",
        },
    )


@router.get("")
async def list_screenings(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Retrieve historical screening runs scoped to the authenticated user."""
    async with get_db_session() as session:
        base_query = select(Run)
        if current_user.role != "admin":
            base_query = base_query.where(
                or_(
                    Run.user_id == current_user.id,
                    Run.client_id == current_user.client_id,
                )
            )

        # Count total records
        count_query = select(func.count()).select_from(base_query.subquery())
        count_res = await session.execute(count_query)
        total_count = count_res.scalar() or 0

        # Query paginated runs
        query = base_query.order_by(Run.created_at.desc()).offset(offset).limit(limit)
        res = await session.execute(query)
        runs = res.scalars().all()

        items = []
        for r in runs:
            v_status = None
            v_passed = None
            if r.result_json and isinstance(r.result_json, dict):
                v_obj = r.result_json.get("verification")
                if isinstance(v_obj, dict):
                    v_passed = v_obj.get("passed")
                    v_status = v_obj.get("status")
                    if not v_status:
                        if v_passed is True:
                            v_status = "PASSED"
                        elif any("429" in str(c.get("detail", "")) or "exceeded" in str(c.get("detail", "")).lower() or "failed:" in str(c.get("detail", "")).lower() or "error" in str(c.get("detail", "")).lower() or "unavailable" in str(c.get("check_name", "")).lower() for c in v_obj.get("checks", []) if not c.get("passed")):
                            v_status = "ERROR"
                        elif v_obj.get("checks"):
                            v_status = "FAILED"
                        else:
                            v_status = "SKIPPED"
            items.append({
                "run_id": r.id,
                "project_name": r.project_name,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "route": r.route.value if hasattr(r.route, "value") and r.route else str(r.route) if r.route else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "client_id": r.client_id,
                "cost_usd": r.cost_usd,
                "verification_status": v_status,
                "verification_passed": v_passed,
            })

        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "items": items,
        }


@router.get("/{run_id}")
async def get_screening_status(run_id: str, current_user: User = Depends(get_current_user)):
    async with get_db_session() as session:
        query = select(Run).where(Run.id == run_id)
        result = await session.execute(query)
        run = result.scalar_one_or_none()

        if not run:
            raise HTTPException(status_code=404, detail="Screening run not found")

        # Authorization: only admin or the user / tenant who owns this record
        if current_user.role != "admin":
            is_owner = (
                (run.user_id and run.user_id == current_user.id) or
                (run.client_id == current_user.client_id)
            )
            if not is_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: access to this screening record is not authorized",
                )

        # Fetch latest step
        step_query = (
            select(RunStep)
            .where(RunStep.run_id == run_id)
            .order_by(RunStep.started_at.desc())
        )
        step_res = await session.execute(step_query)
        latest_step = step_res.scalars().first()

        result_payload = run.result_json
        if result_payload and isinstance(result_payload, dict):
            v_obj = result_payload.get("verification")
            if isinstance(v_obj, dict):
                v_copy = dict(v_obj)
                if "status" not in v_copy:
                    if v_copy.get("passed") is True:
                        v_copy["status"] = "PASSED"
                    elif any(
                        "429" in str(c.get("detail", ""))
                        or "exceeded" in str(c.get("detail", "")).lower()
                        or "failed:" in str(c.get("detail", "")).lower()
                        or "error" in str(c.get("detail", "")).lower()
                        or "unavailable" in str(c.get("check_name", "")).lower()
                        for c in v_copy.get("checks", [])
                        if not c.get("passed")
                    ):
                        v_copy["status"] = "ERROR"
                    elif v_copy.get("checks"):
                        v_copy["status"] = "FAILED"
                    else:
                        v_copy["status"] = "SKIPPED"
                result_payload = dict(result_payload)
                result_payload["verification"] = v_copy

        response = {
            "run_id": run.id,
            "correlation_id": run.correlation_id,
            "client_id": run.client_id,
            "project_name": run.project_name,
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "route": run.route.value if hasattr(run.route, "value") and run.route else str(run.route) if run.route else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "current_step": latest_step.step_name if latest_step else None,
            "result": result_payload,
            "degraded": run.degraded,
        }
        return response


@router.get("/{run_id}/trace")
async def get_screening_trace(run_id: str, current_user: User = Depends(get_current_user)):
    async with get_db_session() as session:
        query = select(Run).where(Run.id == run_id)
        run_res = await session.execute(query)
        run = run_res.scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="Screening run not found")

        if current_user.role != "admin":
            is_owner = (
                (run.user_id and run.user_id == current_user.id) or
                (run.client_id == current_user.client_id)
            )
            if not is_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: access to this screening trace is not authorized",
                )

        steps_query = (
            select(RunStep)
            .where(RunStep.run_id == run_id)
            .order_by(RunStep.started_at.asc())
        )
        steps_res = await session.execute(steps_query)
        steps = steps_res.scalars().all()

        return {
            "run_id": run.id,
            "correlation_id": run.correlation_id,
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "route": run.route.value if hasattr(run.route, "value") and run.route else str(run.route) if run.route else None,
            "cost_usd": run.cost_usd,
            "tokens_prompt": run.tokens_prompt,
            "tokens_completion": run.tokens_completion,
            "steps": [
                {
                    "step_id": s.id,
                    "step_name": s.step_name,
                    "agent": s.agent,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "latency_ms": s.latency_ms,
                    "tokens_prompt": s.tokens_prompt,
                    "tokens_completion": s.tokens_completion,
                    "cost_usd": s.cost_usd,
                    "tool_calls": s.tool_calls_json,
                    "retrieved_passages": s.retrieved_passage_ids,
                    "status": s.status,
                    "error": s.error,
                }
                for s in steps
            ],
        }


@router.get("/{run_id}/events")
async def stream_screening_events(run_id: str, current_user: User = Depends(get_current_user)):
    """Server-Sent Events (SSE) endpoint providing run status stream."""
    async with get_db_session() as session:
        check_q = select(Run).where(Run.id == run_id)
        check_res = await session.execute(check_q)
        run_check = check_res.scalar_one_or_none()
        if not run_check:
            raise HTTPException(status_code=404, detail="Screening run not found")
        if current_user.role != "admin":
            is_owner = (
                (run_check.user_id and run_check.user_id == current_user.id) or
                (run_check.client_id == current_user.client_id)
            )
            if not is_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: access to this screening stream is not authorized",
                )
    async def event_generator():
        while True:
            async with get_db_session() as session:
                query = select(Run).where(Run.id == run_id)
                res = await session.execute(query)
                run = res.scalar_one_or_none()
                if not run:
                    yield f"event: error\ndata: {json.dumps({'error': 'Run not found'})}\n\n"
                    break

                status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
                payload = {
                    "run_id": run.id,
                    "status": status_val,
                    "route": run.route.value if hasattr(run.route, "value") and run.route else None,
                    "result": run.result_json,
                }
                yield f"data: {json.dumps(payload)}\n\n"

                if status_val in ["COMPLETED", "ESCALATED", "DEGRADED", "FAILED", "TIMED_OUT"]:
                    break
            await asyncio.sleep(2.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
