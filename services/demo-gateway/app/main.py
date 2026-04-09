from __future__ import annotations

import os

import requests
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing() -> None:
    resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "demo-gateway")})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4318") + "/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


configure_tracing()
app = FastAPI(title="SLZ Demo Gateway", version="0.1.0")
FastAPIInstrumentor.instrument_app(app)
RequestsInstrumentor().instrument()
tracer = trace.get_tracer(__name__)
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://demo-order:8083")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "demo-gateway"}


@app.get("/api/v1/checkout")
async def checkout() -> dict[str, object]:
    with tracer.start_as_current_span("checkout-flow"):
        response = requests.post(f"{ORDER_SERVICE_URL}/api/v1/orders/reserve", json={"sku": "SKU-1001", "quantity": 1}, timeout=5)
        response.raise_for_status()
        return {
            "status": "accepted",
            "order": response.json(),
        }
