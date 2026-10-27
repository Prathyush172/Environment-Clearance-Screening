"""OpenTelemetry distributed tracing configuration."""

import os
from contextlib import contextmanager
from typing import Optional, Dict, Any

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False


_tracer = None


def setup_tracing(service_name: str, endpoint: Optional[str] = None) -> Any:
    """Initialize OpenTelemetry tracer provider with OTLP exporter."""
    global _tracer
    if not HAS_OTEL:
        return None

    otlp_endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    try:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(processor)
    except Exception:
        # Fallback to console if OTLP fails
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    return _tracer


def get_tracer(service_name: str = "default"):
    """Get active tracer or fallback mock."""
    global _tracer
    if _tracer is not None:
        return _tracer
    if HAS_OTEL:
        return trace.get_tracer(service_name)
    return None


@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Context manager for tracing spans."""
    tracer = get_tracer()
    if tracer is not None and HAS_OTEL:
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, str(v) if not isinstance(v, (bool, int, float, str)) else v)
            yield span
    else:
        # No-op dummy span
        class NoopSpan:
            def set_attribute(self, key, value): pass
            def record_exception(self, exc): pass
            def set_status(self, status, description=None): pass
        yield NoopSpan()
