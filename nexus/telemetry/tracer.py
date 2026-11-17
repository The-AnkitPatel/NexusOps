from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.resources import Resource
from nexus.config import settings
from typing import Dict, Any, Optional

# Resource attribution for OpenTelemetry
resource = Resource.create({
    "service.name": settings.OTEL_SERVICE_NAME,
    "service.version": "0.1.0",
    "deployment.environment": "production-fde",
    "cloud.provider": "gcp",
    "cloud.platform": "gcp_cloud_run"
})

provider = TracerProvider(resource=resource)
memory_exporter = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("nexusops.agent", "0.1.0")

def record_genai_span(
    operation_name: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    attributes: Optional[Dict[str, Any]] = None
):
    """
    Emits an OpenTelemetry span strictly conforming to GenAI Semantic Conventions.
    """
    with tracer.start_as_current_span(f"gen_ai.{operation_name}") as span:
        span.set_attribute("gen_ai.system", "google_vertex_ai")
        span.set_attribute("gen_ai.request.model", model_name)
        span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
        span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
        span.set_attribute("gen_ai.usage.total_tokens", prompt_tokens + completion_tokens)
        span.set_attribute("gen_ai.usage.cost_usd", cost_usd)
        
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
