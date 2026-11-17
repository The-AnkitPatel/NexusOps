"""OpenTelemetry tracing conforming to GenAI semantic conventions.

Spans are always captured by an in-memory exporter (the API/UI read it to show a
live trace log). When ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, spans are ALSO
shipped to a real OTLP/HTTP collector (Jaeger, Grafana Tempo, or the OTel
Collector fronting Google Cloud Trace) via a batch processor.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from nexus.config import settings
from nexus.logging import get_logger

logger = get_logger(__name__)

resource = Resource.create(
    {
        "service.name": settings.OTEL_SERVICE_NAME,
        "service.version": settings.SERVICE_VERSION,
        "deployment.environment": settings.DEPLOYMENT_ENV,
        "cloud.provider": "gcp",
        "cloud.platform": "gcp_cloud_run",
    }
)

provider = TracerProvider(resource=resource)
memory_exporter = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(memory_exporter))


def _maybe_add_otlp_exporter(tracer_provider: TracerProvider) -> bool:
    """Wire a real OTLP/HTTP exporter when an endpoint is configured."""
    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT.strip()
    if not endpoint:
        return False
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        logger.info("OTLP span export enabled -> %s", endpoint)
        return True
    except Exception as exc:  # pragma: no cover - optional dependency / network
        logger.warning("OTLP exporter unavailable (%s); using in-memory only", exc)
        return False


otlp_enabled = _maybe_add_otlp_exporter(provider)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("nexusops.agent", settings.SERVICE_VERSION)


def record_genai_span(
    operation_name: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Emit a span following GenAI semantic conventions (tokens, model, usage)."""
    with tracer.start_as_current_span(f"gen_ai.{operation_name}") as span:
        span.set_attribute("gen_ai.system", settings.GEN_AI_SYSTEM)
        span.set_attribute("gen_ai.operation.name", operation_name)
        span.set_attribute("gen_ai.request.model", model_name)
        # Current semconv names:
        span.set_attribute("gen_ai.usage.input_tokens", prompt_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", completion_tokens)
        # Legacy aliases kept for older dashboards:
        span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
        span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
        span.set_attribute("gen_ai.usage.total_tokens", prompt_tokens + completion_tokens)
        # Cost is a custom (non-semconv) attribute, namespaced honestly:
        span.set_attribute("nexus.usage.cost_usd", cost_usd)
        if attributes:
            for key, value in attributes.items():
                if isinstance(value, (str, bool, int, float)):
                    span.set_attribute(key, value)
                else:
                    span.set_attribute(key, str(value))


def get_captured_spans() -> tuple[ReadableSpan, ...]:
    """Return spans captured by the in-memory exporter (for the telemetry UI)."""
    return memory_exporter.get_finished_spans()
