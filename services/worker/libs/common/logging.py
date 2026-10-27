"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Optional
import structlog
from structlog.types import EventDict, WrappedLogger
from contextvars import ContextVar

# Context variables for request/run tracing across async tasks
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
run_id_ctx: ContextVar[Optional[str]] = ContextVar("run_id", default=None)
step_id_ctx: ContextVar[Optional[str]] = ContextVar("step_id", default=None)
agent_ctx: ContextVar[Optional[str]] = ContextVar("agent", default=None)


def add_context_vars(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """Inject context variables into every log record."""
    corr_id = correlation_id_ctx.get()
    if corr_id is not None:
        event_dict["correlation_id"] = corr_id
    elif "correlation_id" not in event_dict:
        event_dict["correlation_id"] = None

    r_id = run_id_ctx.get()
    if r_id is not None:
        event_dict["run_id"] = r_id
    elif "run_id" not in event_dict:
        event_dict["run_id"] = None

    s_id = step_id_ctx.get()
    if s_id is not None:
        event_dict["step_id"] = s_id
    elif "step_id" not in event_dict:
        event_dict["step_id"] = None

    ag = agent_ctx.get()
    if ag is not None:
        event_dict["agent"] = ag
    elif "agent" not in event_dict:
        event_dict["agent"] = None

    return event_dict


def configure_logging(service: str = "app", environment: str = "development", log_level: str = "INFO") -> None:
    """Configure structlog and standard library logging."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_context_vars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if environment.lower() == "production":
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(service: str = "app") -> structlog.stdlib.BoundLogger:
    """Return a logger bound with service name."""
    logger = structlog.get_logger(service)
    return logger.bind(service=service)
