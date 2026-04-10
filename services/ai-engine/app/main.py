from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from collections.abc import Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter, time
from uuid import uuid4

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIOPS_")

    app_name: str = "SLZ AIOps Engine"
    alert_webhook_token: str | None = None
    cmdb_url: str | None = None
    platform_db_path: str = "/app/runtime/platform.db"


settings = Settings()

REQUEST_COUNTER = Counter(
    "aiops_requests_total",
    "Total number of requests handled by the AIOps engine.",
    ["path", "method", "status"],
)
REQUEST_LATENCY = Histogram(
    "aiops_request_duration_seconds",
    "Latency distribution for AIOps engine requests.",
    ["path", "method"],
)
ACTIVE_ALERTS = Gauge(
    "aiops_active_alerts",
    "Number of active alerts received from Alertmanager.",
)
EVENT_COUNTER = Counter(
    "aiops_events_total",
    "Total number of events recorded by the AIOps engine.",
    ["source", "severity", "status"],
)


class AnomalyRequest(BaseModel):
    values: list[float] = Field(min_length=3, description="Time-series values ordered by time.")
    sensitivity: float = Field(default=3.0, gt=0.1, le=10.0)


class CorrelateSignal(BaseModel):
    source: str
    severity: str
    summary: str


class CorrelationRequest(BaseModel):
    alerts: list[CorrelateSignal]
    logs: list[str] = Field(default_factory=list)
    traces: list[str] = Field(default_factory=list)


class AlertWebhookPayload(BaseModel):
    receiver: str
    status: str
    alerts: list[dict]
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    source: str
    target: str


class EventRecord(BaseModel):
    id: str
    source: str
    severity: str
    summary: str
    status: str
    labels: dict[str, str] = Field(default_factory=dict)
    created_at: float
    updated_at: float


class ManualEventRequest(BaseModel):
    source: str
    severity: str
    summary: str
    labels: dict[str, str] = Field(default_factory=dict)


class EventActionRequest(BaseModel):
    operator: str = "system"
    comment: str = ""


class RootCauseRequest(BaseModel):
    alerts: list[CorrelateSignal]
    impacted_services: list[str] = Field(default_factory=list)
    topology_edges: list[TopologyEdge] = Field(default_factory=list)
    recent_changes: list[str] = Field(default_factory=list)


class AuditRecord(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str
    operator: str
    detail: str
    created_at: float


def _connect_db() -> sqlite3.Connection:
    db_path = Path(settings.platform_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL;")
    return connection


def _initialize_db() -> None:
    with _connect_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS aiops_events (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                severity TEXT NOT NULL,
                summary TEXT NOT NULL,
                status TEXT NOT NULL,
                labels_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
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
        existing_count = connection.execute("SELECT COUNT(*) FROM aiops_events").fetchone()[0]
        if existing_count == 0:
            timestamp = time()
            connection.execute(
                """
                INSERT INTO aiops_events (id, source, severity, summary, status, labels_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    "platform",
                    "warning",
                    "初始示例事件：请确认事件中心联调链路。",
                    "open",
                    json.dumps({"origin": "seed"}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            )
        connection.commit()


def _row_to_event(row: sqlite3.Row) -> EventRecord:
    return EventRecord(
        id=row["id"],
        source=row["source"],
        severity=row["severity"],
        summary=row["summary"],
        status=row["status"],
        labels=json.loads(row["labels_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_audit(row: sqlite3.Row) -> AuditRecord:
    return AuditRecord(
        id=row["id"],
        action=row["action"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        operator=row["operator"],
        detail=row["detail"],
        created_at=row["created_at"],
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


def _list_audit_logs(limit: int) -> list[AuditRecord]:
    with _connect_db() as connection:
        rows = connection.execute(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_audit(row) for row in rows]


def _record_event(source: str, severity: str, summary: str, status: str, labels: dict[str, str] | None = None) -> EventRecord:
    timestamp = time()
    event = EventRecord(
        id=str(uuid4()),
        source=source,
        severity=severity,
        summary=summary,
        status=status,
        labels=labels or {},
        created_at=timestamp,
        updated_at=timestamp,
    )
    with _connect_db() as connection:
        connection.execute(
            """
            INSERT INTO aiops_events (id, source, severity, summary, status, labels_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.source,
                event.severity,
                event.summary,
                event.status,
                json.dumps(event.labels, ensure_ascii=False),
                event.created_at,
                event.updated_at,
            ),
        )
        connection.commit()
    EVENT_COUNTER.labels(source=source, severity=severity.lower(), status=status.lower()).inc()
    return event


def _list_events() -> list[EventRecord]:
    with _connect_db() as connection:
        rows = connection.execute(
            "SELECT * FROM aiops_events ORDER BY updated_at DESC, created_at DESC"
        ).fetchall()
    return [_row_to_event(row) for row in rows]


def _get_event(event_id: str) -> EventRecord:
    with _connect_db() as connection:
        row = connection.execute("SELECT * FROM aiops_events WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    return _row_to_event(row)


def _update_event_status(event_id: str, status: str, operator: str, comment: str) -> EventRecord:
    event = _get_event(event_id)
    updated = event.model_copy(
        update={
            "status": status,
            "updated_at": time(),
            "labels": {
                **event.labels,
                "last_operator": operator,
                "last_comment": comment,
            },
        }
    )
    with _connect_db() as connection:
        connection.execute(
            """
            UPDATE aiops_events
            SET status = ?, labels_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated.status,
                json.dumps(updated.labels, ensure_ascii=False),
                updated.updated_at,
                updated.id,
            ),
        )
        connection.commit()
    return updated


def _refresh_active_alert_gauge() -> None:
    with _connect_db() as connection:
        open_count = connection.execute(
            "SELECT COUNT(*) FROM aiops_events WHERE status = 'open'"
        ).fetchone()[0]
    ACTIVE_ALERTS.set(open_count)


def _calculate_z_scores(values: Sequence[float]) -> list[float]:
    array = np.asarray(values, dtype=float)
    mean = float(array.mean())
    std = float(array.std())
    if std == 0:
        return [0.0 for _ in values]
    return [abs((value - mean) / std) for value in array]


def _fetch_cmdb_edges() -> list[TopologyEdge]:
    if not settings.cmdb_url:
        return []

    url = settings.cmdb_url.rstrip("/") + "/api/v1/topology/edges"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []

    return [TopologyEdge(**edge) for edge in payload.get("edges", [])]


@asynccontextmanager
async def lifespan(_: FastAPI):
    _initialize_db()
    ACTIVE_ALERTS.set(0)
    _refresh_active_alert_gauge()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


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


@app.post("/api/v1/anomaly/detect")
async def detect_anomaly(payload: AnomalyRequest) -> dict[str, object]:
    z_scores = _calculate_z_scores(payload.values)
    anomalies = [
        {"index": index, "value": payload.values[index], "z_score": round(z_score, 4)}
        for index, z_score in enumerate(z_scores)
        if z_score >= payload.sensitivity
    ]
    return {
        "baseline": round(float(np.mean(payload.values)), 4),
        "stddev": round(float(np.std(payload.values)), 4),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    }


@app.post("/api/v1/events/correlate")
async def correlate_events(payload: CorrelationRequest) -> dict[str, object]:
    if not payload.alerts:
        raise HTTPException(status_code=400, detail="at least one alert is required")

    severity_rank = {"critical": 3, "warning": 2, "info": 1}
    primary = max(payload.alerts, key=lambda item: severity_rank.get(item.severity.lower(), 0))
    suspected_domains = sorted({alert.source for alert in payload.alerts})
    return {
        "primary_event": primary.summary,
        "suspected_domains": suspected_domains,
        "log_signal_count": len(payload.logs),
        "trace_signal_count": len(payload.traces),
        "recommended_actions": [
            f"检查 {primary.source} 近 15 分钟变更记录",
            "关联查询同批次告警与异常日志",
            "若影响持续，执行标准化回滚或重启 Playbook",
        ],
    }


@app.get("/api/v1/events")
async def list_events() -> dict[str, object]:
    events = _list_events()
    summary = {
        "open": sum(1 for event in events if event.status == "open"),
        "acknowledged": sum(1 for event in events if event.status == "acknowledged"),
        "resolved": sum(1 for event in events if event.status == "resolved"),
    }
    return {
        "total": len(events),
        "summary": summary,
        "events": [event.model_dump() for event in events],
    }


@app.post("/api/v1/events/manual")
async def create_manual_event(payload: ManualEventRequest) -> dict[str, object]:
    event = _record_event(
        source=payload.source,
        severity=payload.severity,
        summary=payload.summary,
        status="open",
        labels=payload.labels,
    )
    _refresh_active_alert_gauge()
    _record_audit("create", "event", event.id, "console-user", f"创建事件: {event.summary}")
    return {"created": True, "event": event.model_dump()}


@app.post("/api/v1/events/{event_id}/ack")
async def acknowledge_event(event_id: str, payload: EventActionRequest) -> dict[str, object]:
    event = _update_event_status(event_id, "acknowledged", payload.operator, payload.comment)
    _refresh_active_alert_gauge()
    _record_audit("ack", "event", event.id, payload.operator, payload.comment or f"确认事件: {event.summary}")
    return {"updated": True, "event": event.model_dump()}


@app.post("/api/v1/events/{event_id}/resolve")
async def resolve_event(event_id: str, payload: EventActionRequest) -> dict[str, object]:
    event = _update_event_status(event_id, "resolved", payload.operator, payload.comment)
    _refresh_active_alert_gauge()
    _record_audit("resolve", "event", event.id, payload.operator, payload.comment or f"关闭事件: {event.summary}")
    return {"updated": True, "event": event.model_dump()}


@app.post("/api/v1/alerts/webhook")
async def alert_webhook(payload: AlertWebhookPayload) -> dict[str, object]:
    firing_count = 0
    for alert in payload.alerts:
        alert_status = str(alert.get("status", "firing"))
        source = alert.get("labels", {}).get("job") or payload.commonLabels.get("job") or "alertmanager"
        severity = alert.get("labels", {}).get("severity") or payload.commonLabels.get("severity") or "warning"
        summary = (
            alert.get("annotations", {}).get("summary")
            or payload.commonAnnotations.get("summary")
            or payload.commonLabels.get("alertname")
            or "Alertmanager event"
        )
        if alert_status == "firing":
            firing_count += 1
            event = _record_event(
                source=source,
                severity=severity,
                summary=summary,
                status="open",
                labels={
                    **payload.commonLabels,
                    **alert.get("labels", {}),
                },
            )
            _record_audit("ingest", "event", event.id, "alertmanager", f"接收告警事件: {summary}")

    _refresh_active_alert_gauge()
    return {
        "accepted": True,
        "receiver": payload.receiver,
        "status": payload.status,
        "alert_count": len(payload.alerts),
        "firing_count": firing_count,
    }


@app.post("/api/v1/root-cause/analyze")
async def analyze_root_cause(payload: RootCauseRequest) -> dict[str, object]:
    if not payload.alerts:
        raise HTTPException(status_code=400, detail="at least one alert is required")

    severity_rank = {"critical": 3, "warning": 2, "info": 1}
    primary_alert = max(payload.alerts, key=lambda item: severity_rank.get(item.severity.lower(), 0))

    topology_edges = payload.topology_edges or _fetch_cmdb_edges()

    adjacency: dict[str, set[str]] = {}
    for edge in topology_edges:
        adjacency.setdefault(edge.source, set()).add(edge.target)
        adjacency.setdefault(edge.target, set()).add(edge.source)

    root_service = primary_alert.source
    related_services = sorted(adjacency.get(root_service, set()))
    blast_radius = sorted({root_service, *related_services, *payload.impacted_services})
    confidence = min(0.55 + 0.1 * len(related_services) + 0.05 * len(payload.recent_changes), 0.95)

    reasoning = [
        f"最高严重级别告警来自 {root_service}",
        f"拓扑上与其直接相邻的服务数为 {len(related_services)}",
    ]
    if payload.recent_changes:
        reasoning.append(f"近 15 分钟检测到 {len(payload.recent_changes)} 条相关变更记录")
    if topology_edges and not payload.topology_edges:
        reasoning.append("拓扑关系由 CMDB 自动补全")

    return {
        "probable_root_cause": root_service,
        "primary_alert": primary_alert.summary,
        "blast_radius": blast_radius,
        "confidence": round(confidence, 2),
        "reasoning": reasoning,
        "recommended_actions": [
            f"优先检查 {root_service} 的发布、配置和依赖链路",
            "结合 Tempo 调用链确认异常传播方向",
            "从 CMDB 核对上下游依赖与负责人，并执行受控回滚或限流",
        ],
    }


@app.get("/api/v1/root-cause/topology")
async def get_cmdb_topology() -> dict[str, object]:
    edges = _fetch_cmdb_edges()
    return {"edge_count": len(edges), "edges": [edge.model_dump() for edge in edges]}


@app.get("/api/v1/audit")
async def list_audit(limit: int = 50) -> dict[str, object]:
    items = _list_audit_logs(max(1, min(limit, 200)))
    return {"total": len(items), "items": [item.model_dump() for item in items]}

