"""Feedback collection and summary router."""

import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from libs.common.db.session import get_db_session
from libs.common.db.models import Feedback, Run

router = APIRouter(tags=["feedback"])


class FeedbackSubmission(BaseModel):
    satisfactory: bool
    reason: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=64)


@router.post("/v1/screenings/{run_id}/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(run_id: str, feedback_data: FeedbackSubmission):
    async with get_db_session() as session:
        # Check run exists
        run_res = await session.execute(select(Run).where(Run.id == run_id))
        run = run_res.scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="Screening run not found")

        feedback_entry = Feedback(
            id=str(uuid.uuid4()),
            run_id=run_id,
            satisfactory=feedback_data.satisfactory,
            reason=feedback_data.reason,
            category=feedback_data.category,
        )
        session.add(feedback_entry)

    return {"status": "recorded", "feedback_id": feedback_entry.id}


@router.get("/v1/feedback/summary")
async def get_feedback_summary():
    async with get_db_session() as session:
        total_q = await session.execute(select(func.count(Feedback.id)))
        total = total_q.scalar() or 0

        sat_q = await session.execute(select(func.count(Feedback.id)).where(Feedback.satisfactory == True))
        satisfactory = sat_q.scalar() or 0

        unsat = total - satisfactory
        satisfaction_rate = (satisfactory / total) if total > 0 else 0.0

        return {
            "total_feedbacks": total,
            "satisfactory_count": satisfactory,
            "unsatisfactory_count": unsat,
            "satisfaction_rate": round(satisfaction_rate, 4),
        }
