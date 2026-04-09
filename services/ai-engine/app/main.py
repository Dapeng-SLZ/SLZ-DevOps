from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from contextlib import asynccontextmanager
from time import perf_counter

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


class RootCauseRequest(BaseModel):
    alerts: list[CorrelateSignal]
    impacted_services: list[str] = Field(default_factory=list)
    topology_edges: list[TopologyEdge] = Field(default_factory=list)
    recent_changes: list[str] = Field(default_factory=list)


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
    ACTIVE_ALERTS.set(0)
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


@app.post("/api/v1/alerts/webhook")
async def alert_webhook(payload: AlertWebhookPayload) -> dict[str, object]:
    firing_count = sum(1 for alert in payload.alerts if alert.get("status") == "firing")
    ACTIVE_ALERTS.set(firing_count)
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

