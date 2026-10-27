"""Quarantine inspection router for rejected screening requests."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, desc
from libs.common.db.session import get_db_session
from libs.common.db.models import Quarantine

router = APIRouter(prefix="/v1/quarantine", tags=["quarantine"])


@router.get("/{quarantine_id}")
async def get_quarantined_record(quarantine_id: str):
    async with get_db_session() as session:
        query = select(Quarantine).where(Quarantine.id == quarantine_id)
        res = await session.execute(query)
        record = res.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail="Quarantine record not found")

        return {
            "id": record.id,
            "correlation_id": record.correlation_id,
            "raw_payload": record.raw_payload_json,
            "field_errors": record.field_errors_json,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "client_ip": record.client_ip,
        }


@router.get("")
async def list_quarantined_records(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    async with get_db_session() as session:
        query = (
            select(Quarantine)
            .order_by(desc(Quarantine.created_at))
            .offset(offset)
            .limit(limit)
        )
        res = await session.execute(query)
        records = res.scalars().all()

        return {
            "total": len(records),
            "offset": offset,
            "limit": limit,
            "items": [
                {
                    "id": r.id,
                    "correlation_id": r.correlation_id,
                    "raw_payload": r.raw_payload_json,
                    "field_errors": r.field_errors_json,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "client_ip": r.client_ip,
                }
                for r in records
            ],
        }
