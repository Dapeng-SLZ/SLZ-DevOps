from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter, time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_GATEWAY_")

    app_name: str = "SLZ API Gateway"
    platform_db_path: str = "/app/runtime/platform.db"
    session_cookie_name: str = "slz_session"
    ai_engine_url: str = "http://host.containers.internal:18080"
    cmdb_url: str = "http://host.containers.internal:18081"
    job_runner_url: str = "http://host.containers.internal:18084"
    prometheus_url: str = "http://host.containers.internal:19090"
    alertmanager_url: str = "http://host.containers.internal:19093"
    loki_url: str = "http://host.containers.internal:13100"


class UserProfile(BaseModel):
    username: str
    display_name: str
    role: str
    permissions: list[str]


settings = Settings()
REQUEST_COUNTER = Counter("api_gateway_requests_total", "Total API gateway requests.", ["path", "method", "status"])
REQUEST_LATENCY = Histogram("api_gateway_request_duration_seconds", "API gateway request latency.", ["path", "method"])


NAVIGATION = [
    {
        "title": "配置与资产",
        "items": [
            {"key": "cmdb", "label": "CMDB", "implemented": True},
            {"key": "host-center", "label": "主机中心", "implemented": True},
            {"key": "multi-cloud", "label": "多云管理", "implemented": False},
        ],
    },
    {
        "title": "变更与执行",
        "items": [
            {"key": "jobs", "label": "任务中心", "implemented": True},
            {"key": "tickets", "label": "工单系统", "implemented": False},
            {"key": "containers", "label": "容器管理", "implemented": False},
        ],
    },
    {
        "title": "可观测与事件",
        "items": [
            {"key": "overview", "label": "平台总览", "implemented": True},
            {"key": "observability", "label": "可观测性", "implemented": True},
            {"key": "events", "label": "事件墙", "implemented": True},
        ],
    },
    {
        "title": "智能助手",
        "items": [{"key": "assistant", "label": "AIOps 助手", "implemented": True}],
    },
]


def _connect_db() -> sqlite3.Connection:
    db_path = Path(settings.platform_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL;")
    return connection


def _row_to_user(row: sqlite3.Row) -> UserProfile:
    return UserProfile(
        username=row["username"],
        display_name=row["display_name"],
        role=row["role"],
        permissions=json.loads(row["permissions_json"]),
    )


def _require_user(request: Request) -> UserProfile:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="unauthorized")

    with _connect_db() as connection:
        row = connection.execute(
            """
            SELECT u.*
            FROM auth_sessions s
            JOIN auth_users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, time()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return _row_to_user(row)


def _fetch_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def _safe_health(name: str, url: str) -> dict[str, str]:
    try:
        _fetch_text(url)
        return {"name": name, "status": "healthy"}
    except Exception:
        return {"name": name, "status": "degraded"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    elapsed = perf_counter() - start
    REQUEST_COUNTER.labels(path=request.url.path, method=request.method, status=str(response.status_code)).inc()
    REQUEST_LATENCY.labels(path=request.url.path, method=request.method).observe(elapsed)
    return response


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/me")
async def me(request: Request) -> dict[str, object]:
    user = _require_user(request)
    return {"user": user.model_dump()}


@app.get("/api/v1/navigation")
async def navigation(request: Request) -> dict[str, object]:
    _require_user(request)
    return {"groups": NAVIGATION}


@app.get("/api/v1/workspace-summary")
async def workspace_summary(request: Request) -> dict[str, object]:
    _require_user(request)

    health = [
        _safe_health("AI Engine", settings.ai_engine_url.rstrip('/') + '/healthz'),
        _safe_health("Prometheus", settings.prometheus_url.rstrip('/') + '/-/healthy'),
        _safe_health("Alertmanager", settings.alertmanager_url.rstrip('/') + '/-/healthy'),
        _safe_health("Loki", settings.loki_url.rstrip('/') + '/ready'),
        _safe_health("Job Runner", settings.job_runner_url.rstrip('/') + '/healthz'),
    ]

    try:
        events = _fetch_json(settings.ai_engine_url.rstrip('/') + '/api/v1/events')
    except urllib.error.URLError:
        events = {"summary": {"open": 0, "acknowledged": 0, "resolved": 0}, "total": 0}

    try:
        jobs = _fetch_json(settings.job_runner_url.rstrip('/') + '/api/v1/jobs')
    except urllib.error.URLError:
        jobs = {"total": 0, "jobs": []}

    try:
        topology = _fetch_json(settings.cmdb_url.rstrip('/') + '/api/v1/topology')
    except urllib.error.URLError:
        topology = {"services": [], "edges": []}

    return {
        "health": health,
        "events": events.get("summary", {}),
        "job_total": jobs.get("total", 0),
        "cmdb": {
            "service_total": len(topology.get("services", [])),
            "edge_total": len(topology.get("edges", [])),
        },
        "quick_actions": [
            {"key": "jobs", "label": "执行平台巡检", "template_id": "platform-health-scan"},
            {"key": "events", "label": "查看待处理事件", "filter": "open"},
            {"key": "cmdb", "label": "检查高优服务", "filter": "criticality=high"},
        ],
    }
