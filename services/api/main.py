"""FastAPI application entrypoint for Environmental Clearance Pre-Screening Service."""

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from libs.common.config import settings
from libs.common.logging import configure_logging, get_logger
from libs.common.tracing import setup_tracing
from libs.common.db.session import get_engine, close_db

from services.api.routers import screenings, quarantine, health, feedback, admin
from services.api.metrics import http_requests_total, http_request_duration_seconds

# Configure logging and tracer
configure_logging(service="api", environment=settings.ENVIRONMENT, log_level=settings.LOG_LEVEL)
logger = get_logger("api")
setup_tracing("api", settings.OTEL_EXPORTER_OTLP_ENDPOINT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting API service", environment=settings.ENVIRONMENT)
    # Warm up database engine
    try:
        engine = get_engine()
        logger.info("Database engine initialized")
    except Exception as exc:
        logger.error("Failed to initialize database engine", error=str(exc))
    yield
    logger.info("Shutting down API service")
    await close_db()


app = FastAPI(
    title="Environmental Clearance Pre-Screening API",
    description="Pre-screening service classifying proposals under India's EIA Notification 2006",
    version="1.0.0",
    lifespan=lifespan,
)

# OpenTelemetry FastAPI instrumentation if available
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)
except Exception:
    pass

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_and_logging_middleware(request: Request, call_next):
    start_time = time.time()
    path = request.url.path
    method = request.method

    response = await call_next(request)
    duration = time.time() - start_time

    # Record Prometheus metrics
    http_requests_total.labels(method=method, path=path, status=str(response.status_code)).inc()
    http_request_duration_seconds.labels(method=method, path=path).observe(duration)

    return response


# Prometheus /metrics endpoint
metrics_asgi = make_asgi_app()
app.mount("/metrics", metrics_asgi)

# Include API routers
app.include_router(health.router)
app.include_router(screenings.router)
app.include_router(quarantine.router)
app.include_router(feedback.router)
app.include_router(admin.router)
