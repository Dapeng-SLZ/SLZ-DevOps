from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from time import perf_counter, time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CMDB_")

    app_name: str = "SLZ CMDB Service"
    data_file: str = "/app/data/seed.json"
    platform_db_path: str = "/app/runtime/platform.db"


class ServiceRecord(BaseModel):
    id: str
    name: str
    tier: str
    owner: str
    criticality: str
    dependencies: list[str]


class ServiceMutation(BaseModel):
    id: str
    name: str
    tier: str
    owner: str
    criticality: str
    dependencies: list[str] = Field(default_factory=list)


class TopologyEdge(BaseModel):
    source_id: str
    source_name: str
    target_id: str
    target_name: str


settings = Settings()
REQUEST_COUNTER = Counter("cmdb_requests_total", "Total CMDB requests.", ["path", "method", "status"])
REQUEST_LATENCY = Histogram("cmdb_request_duration_seconds", "CMDB request latency.", ["path", "method"])


def _connect_db() -> sqlite3.Connection:
    db_path = Path(settings.platform_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL;")
    return connection


def _seed_json_services() -> list[ServiceRecord]:
    data = json.loads(Path(settings.data_file).read_text(encoding="utf-8"))
    return [ServiceRecord(**item) for item in data.get("services", [])]


def _initialize_db() -> None:
    with _connect_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cmdb_services (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tier TEXT NOT NULL,
                owner TEXT NOT NULL,
                criticality TEXT NOT NULL,
                dependencies_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                operator TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        existing_count = connection.execute("SELECT COUNT(*) FROM cmdb_services").fetchone()[0]
        if existing_count == 0:
            for service in _seed_json_services():
                connection.execute(
                    """
                    INSERT INTO cmdb_services (id, name, tier, owner, criticality, dependencies_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        service.id,
                        service.name,
                        service.tier,
                        service.owner,
                        service.criticality,
                        json.dumps(service.dependencies, ensure_ascii=False),
                    ),
                )
        connection.commit()


def _row_to_service(row: sqlite3.Row) -> ServiceRecord:
    return ServiceRecord(
        id=row["id"],
        name=row["name"],
        tier=row["tier"],
        owner=row["owner"],
        criticality=row["criticality"],
        dependencies=json.loads(row["dependencies_json"]),
    )


def _record_audit(action: str, resource_type: str, resource_id: str, operator: str, detail: str) -> None:
    with _connect_db() as connection:
        connection.execute(
            """
            INSERT INTO audit_logs (id, action, resource_type, resource_id, operator, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (str(uuid4()), action, resource_type, resource_id, operator, detail, time()),
        )
        connection.commit()


def load_services() -> list[ServiceRecord]:
    with _connect_db() as connection:
        rows = connection.execute("SELECT * FROM cmdb_services ORDER BY id ASC").fetchall()
    return [_row_to_service(row) for row in rows]


def save_services(services: list[ServiceRecord]) -> None:
    with _connect_db() as connection:
        connection.execute("DELETE FROM cmdb_services")
        connection.executemany(
            """
            INSERT INTO cmdb_services (id, name, tier, owner, criticality, dependencies_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    service.id,
                    service.name,
                    service.tier,
                    service.owner,
                    service.criticality,
                    json.dumps(service.dependencies, ensure_ascii=False),
                )
                for service in services
            ],
        )
        connection.commit()

    data_file = Path(settings.data_file)
    payload = {"services": [service.model_dump() for service in services]}
    data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_service_dependencies(services: list[ServiceRecord], target: ServiceMutation) -> None:
    service_ids = {service.id for service in services}
    for dependency in target.dependencies:
        if dependency == target.id:
            raise HTTPException(status_code=400, detail="service cannot depend on itself")
        if dependency not in service_ids and dependency != target.id:
            raise HTTPException(status_code=400, detail=f"dependency not found: {dependency}")


def upsert_service(target: ServiceMutation, replace_id: str | None = None) -> ServiceRecord:
    services = load_services()
    existing_index = next((index for index, item in enumerate(services) if item.id == (replace_id or target.id)), None)

    if replace_id and replace_id != target.id and any(service.id == target.id for service in services):
        raise HTTPException(status_code=409, detail="service id already exists")

    candidate_services = [service for service in services if service.id != (replace_id or target.id)]
    validate_service_dependencies(candidate_services, target)

    service = ServiceRecord(**target.model_dump())

    if existing_index is None:
        services.append(service)
    else:
        services[existing_index] = service

    save_services(services)
    return service


def delete_service_record(service_id: str) -> None:
    services = load_services()
    if not any(service.id == service_id for service in services):
        raise HTTPException(status_code=404, detail="service not found")

    referenced_by = [service.name for service in services if service_id in service.dependencies]
    if referenced_by:
        raise HTTPException(
            status_code=409,
            detail=f"service is still referenced by: {', '.join(referenced_by)}",
        )

    save_services([service for service in services if service.id != service_id])


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


@app.on_event("startup")
async def startup_event() -> None:
    _initialize_db()


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


@app.post("/api/v1/services")
async def create_service(payload: ServiceMutation) -> dict[str, object]:
    if any(service.id == payload.id for service in load_services()):
        raise HTTPException(status_code=409, detail="service id already exists")
    service = upsert_service(payload)
    _record_audit("create", "cmdb_service", service.id, "console-user", f"创建服务: {service.name}")
    return {"created": True, "service": service.model_dump()}


@app.get("/api/v1/services/{service_id}")
async def get_service(service_id: str) -> dict[str, object]:
    for service in load_services():
        if service.id == service_id or service.name == service_id:
            return service.model_dump()
    raise HTTPException(status_code=404, detail="service not found")


@app.put("/api/v1/services/{service_id}")
async def update_service(service_id: str, payload: ServiceMutation) -> dict[str, object]:
    service = upsert_service(payload, replace_id=service_id)
    _record_audit("update", "cmdb_service", service.id, "console-user", f"更新服务: {service.name}")
    return {"updated": True, "service": service.model_dump()}


@app.delete("/api/v1/services/{service_id}")
async def delete_service(service_id: str) -> dict[str, object]:
    delete_service_record(service_id)
    _record_audit("delete", "cmdb_service", service_id, "console-user", f"删除服务: {service_id}")
    return {"deleted": True, "service_id": service_id}


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
