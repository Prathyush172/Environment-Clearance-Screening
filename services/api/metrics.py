"""Prometheus metrics for API service."""

from prometheus_client import Counter, Histogram, Gauge, make_asgi_app

validation_rejected_total = Counter(
    "validation_rejected_total",
    "Validation rejections",
    ["reason"]
)

http_requests_total = Counter(
    "http_requests_total",
    "HTTP requests",
    ["method", "path", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"]
)

runs_queued_total = Counter(
    "runs_queued_total",
    "Total runs queued"
)

queue_depth = Gauge(
    "queue_depth",
    "Current Celery queue depth"
)

# ASGI app for mounting under /metrics
metrics_app = make_asgi_app()
