"""Structured logging configuration using structlog with fallback to standard logging."""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Optional, Any
from contextvars import ContextVar

try:
    import structlog
    from structlog.types import EventDict, WrappedLogger
    HAVE_STRUCTLOG = True
except ImportError:
    HAVE_STRUCTLOG = False

# Context variables for request/run tracing across async tasks
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
run_id_ctx: ContextVar[Optional[str]] = ContextVar("run_id", default=None)
step_id_ctx: ContextVar[Optional[str]] = ContextVar("step_id", default=None)
agent_ctx: ContextVar[Optional[str]] = ContextVar("agent", default=None)


if HAVE_STRUCTLOG:
    def add_context_vars(logger: Any, method_name: str, event_dict: Any) -> Any:
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


    def get_logger(service: str = "app") -> Any:
        """Return a logger bound with service name."""
        logger = structlog.get_logger(service)
        return logger.bind(service=service)

else:
    class SimpleFallbackLogger:
        """Fallback logger matching structlog method calling conventions."""
        def __init__(self, name: str):
            self._logger = logging.getLogger(name)

        def _format(self, event: str, **kwargs: Any) -> str:
            data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "correlation_id": correlation_id_ctx.get(),
                "run_id": run_id_ctx.get(),
                "step_id": step_id_ctx.get(),
                "agent": agent_ctx.get(),
                **kwargs
            }
            return json.dumps(data)

        def info(self, event: str, **kwargs: Any) -> None:
            self._logger.info(self._format(event, **kwargs))

        def warning(self, event: str, **kwargs: Any) -> None:
            self._logger.warning(self._format(event, **kwargs))

        def error(self, event: str, **kwargs: Any) -> None:
            self._logger.error(self._format(event, **kwargs))

        def debug(self, event: str, **kwargs: Any) -> None:
            self._logger.debug(self._format(event, **kwargs))

        def bind(self, **kwargs: Any) -> "SimpleFallbackLogger":
            return self

    def configure_logging(service: str = "app", environment: str = "development", log_level: str = "INFO") -> None:
        level = getattr(logging, log_level.upper(), logging.INFO)
        logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    def get_logger(service: str = "app") -> Any:
        return SimpleFallbackLogger(service)
