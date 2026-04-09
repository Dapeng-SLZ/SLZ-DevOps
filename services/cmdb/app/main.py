from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CMDB_")

    app_name: str = "SLZ CMDB Service"
    data_file: str = "/app/data/seed.json"


class ServiceRecord(BaseModel):
    id: str
    name: str
    tier: str
    owner: str
    criticality: str
    dependencies: list[str]


class TopologyEdge(BaseModel):
    source_id: str
    source_name: str
    target_id: str
    target_name: str


settings = Settings()
REQUEST_COUNTER = Counter("cmdb_requests_total", "Total CMDB requests.", ["path", "method", "status"])
REQUEST_LATENCY = Histogram("cmdb_request_duration_seconds", "CMDB request latency.", ["path", "method"])


def load_services() -> list[ServiceRecord]:
    data = json.loads(Path(settings.data_file).read_text(encoding="utf-8"))
    return [ServiceRecord(**item) for item in data.get("services", [])]


def build_topology_edges() -> list[TopologyEdge]:
    services = load_services()
    service_by_id = {service.id: service for service in services}
    edges: list[TopologyEdge] = []
    for service in services:
      for dependency_id in service.dependencies:
          dependency = service_by_id.get(dependency_id)
          if dependency is None:
              continue
          edges.append(
              TopologyEdge(
                  source_id=service.id,
                  source_name=service.name,
                  target_id=dependency.id,
                  target_name=dependency.name,
              )
          )
    return edges


def build_cypher() -> str:
    services = load_services()
    edges = build_topology_edges()
    statements = [
        "MATCH (n) DETACH DELETE n;",
    ]
    for service in services:
        statements.append(
            "MERGE (:Service {id: '%s', name: '%s', tier: '%s', owner: '%s', criticality: '%s'});"
            % (service.id, service.name, service.tier, service.owner, service.criticality)
        )
    for edge in edges:
        statements.append(
            "MATCH (a:Service {id: '%s'}), (b:Service {id: '%s'}) MERGE (a)-[:DEPENDS_ON]->(b);"
            % (edge.source_id, edge.target_id)
        )
    return "\n".join(statements)


app = FastAPI(title=settings.app_name, version="0.1.0")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    elapsed = perf_counter() - start
    path = request.url.path
    method = request.method
    status = str(response.status_code)
    REQUEST_COUNTER.labels(path=path, method=method, status=status).inc()
    REQUEST_LATENCY.labels(path=path, method=method).observe(elapsed)
    return response


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/services")
async def get_services() -> dict[str, list[dict[str, object]]]:
    return {"services": [service.model_dump() for service in load_services()]}


@app.get("/api/v1/services/{service_id}")
async def get_service(service_id: str) -> dict[str, object]:
    for service in load_services():
        if service.id == service_id or service.name == service_id:
            return service.model_dump()
    raise HTTPException(status_code=404, detail="service not found")


@app.get("/api/v1/topology")
async def get_topology() -> dict[str, object]:
    return {
        "services": [service.model_dump() for service in load_services()],
        "edges": [edge.model_dump() for edge in build_topology_edges()],
    }


@app.get("/api/v1/topology/edges")
async def get_topology_edges() -> dict[str, list[dict[str, str]]]:
    return {
        "edges": [
            {"source": edge.source_name, "target": edge.target_name}
            for edge in build_topology_edges()
        ]
    }


@app.get("/api/v1/topology/cypher")
async def get_topology_cypher() -> PlainTextResponse:
    return PlainTextResponse(build_cypher(), media_type="text/plain")
