from __future__ import annotations

import os
import time

from fastapi import FastAPI
from pydantic import BaseModel
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


class ReserveRequest(BaseModel):
    sku: str
    quantity: int


def configure_tracing() -> None:
    resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "demo-order")})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4318") + "/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


configure_tracing()
app = FastAPI(title="SLZ Demo Order", version="0.1.0")
FastAPIInstrumentor.instrument_app(app)
tracer = trace.get_tracer(__name__)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "demo-order"}


@app.post("/api/v1/orders/reserve")
async def reserve(request: ReserveRequest) -> dict[str, object]:
    with tracer.start_as_current_span("reserve-inventory"):
        time.sleep(0.05)
        return {
            "reservation_id": "RSV-1001",
            "sku": request.sku,
            "quantity": request.quantity,
            "status": "reserved",
        }
