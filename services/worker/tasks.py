"""Celery worker task definitions."""

import os
import asyncio
from datetime import datetime, timezone
from celery import Celery
from sqlalchemy import select

from libs.common.config import settings
from libs.common.logging import configure_logging, get_logger
from libs.common.db.session import get_db_session
from libs.common.db.models import Run, RunStatus
from services.worker.graph_agent import ScreeningAgentGraph

configure_logging(service="worker", environment=settings.ENVIRONMENT, log_level=settings.LOG_LEVEL)
logger = get_logger("worker_tasks")

redis_url = os.environ.get("REDIS_URL", settings.REDIS_URL)

celery_app = Celery("worker", broker=redis_url, backend=redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=int(os.environ.get("RUN_WALL_CLOCK_SECONDS", 90)) + 30,
    task_soft_time_limit=int(os.environ.get("RUN_WALL_CLOCK_SECONDS", 90)),
)


@celery_app.task(bind=True, name="run_screening", max_retries=0)
def run_screening(self, run_id: str, request_data: dict, correlation_id: str):
    """Execute screening analysis workflow using full ScreeningAgentGraph."""
    logger.info("Worker received task run_screening", run_id=run_id, correlation_id=correlation_id)

    async def _execute():
        from libs.common.db.session import close_db
        try:
            # 1. Mark run as RUNNING in DB
            async with get_db_session() as session:
                q = select(Run).where(Run.id == run_id)
                r = await session.execute(q)
                run_obj = r.scalar_one_or_none()
                if run_obj:
                    run_obj.status = RunStatus.RUNNING
                    run_obj.updated_at = datetime.now(timezone.utc)
                    await session.commit()

            # 2. Run graph agent
            try:
                graph = ScreeningAgentGraph()
                result = await graph.run(run_id, request_data, correlation_id)
                route_val = result.get("route")
                cost_summary = result.get("cost_summary", {})
                total_cost = cost_summary.get("cost_usd", 0.0)

                async with get_db_session() as session:
                    q = select(Run).where(Run.id == run_id)
                    r = await session.execute(q)
                    run_obj = r.scalar_one_or_none()
                    if run_obj:
                        run_obj.status = RunStatus.COMPLETED if route_val != "ESCALATED_TO_HUMAN" else RunStatus.ESCALATED
                        run_obj.route = route_val
                        run_obj.result_json = result
                        run_obj.cost_usd = total_cost
                        run_obj.completed_at = datetime.now(timezone.utc)
                        run_obj.updated_at = datetime.now(timezone.utc)
                        await session.commit()
                return result
            except Exception as exc:
                logger.error("Screening graph execution failed", run_id=run_id, error=str(exc))
                async with get_db_session() as session:
                    q = select(Run).where(Run.id == run_id)
                    r = await session.execute(q)
                    run_obj = r.scalar_one_or_none()
                    if run_obj:
                        run_obj.status = RunStatus.FAILED
                        run_obj.result_json = {"error": str(exc)}
                        run_obj.completed_at = datetime.now(timezone.utc)
                        run_obj.updated_at = datetime.now(timezone.utc)
                        await session.commit()
                raise
        finally:
            try:
                await close_db()
            except Exception:
                pass

    return asyncio.run(_execute())
