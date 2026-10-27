"""Celery worker task definitions."""

import os
import asyncio
from celery import Celery

from libs.common.config import settings
from libs.common.logging import configure_logging, get_logger
from libs.common.db.session import get_db_session
from services.worker.agent_m1 import run_simple_agent

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
    """Execute screening analysis workflow."""
    logger.info("Worker received task run_screening", run_id=run_id, correlation_id=correlation_id)

    async def _execute():
        async with get_db_session() as session:
            return await run_simple_agent(
                run_id=run_id,
                request_data=request_data,
                correlation_id=correlation_id,
                session=session,
            )

    return asyncio.run(_execute())
