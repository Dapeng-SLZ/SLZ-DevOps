from __future__ import annotations

import asyncio
import json
import sqlite3
import urllib.error
import urllib.request
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter, time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOB_RUNNER_")

    app_name: str = "SLZ Job Runner"
    ai_engine_url: str = "http://ai-engine:8080"
    cmdb_url: str = "http://cmdb:8081"
    prometheus_url: str = "http://prometheus:9090"
    alertmanager_url: str = "http://alertmanager:9093"
    platform_db_path: str = "/app/runtime/platform.db"


class JobTemplate(BaseModel):
    id: str
    name: str
    description: str
    category: str


class JobRecord(BaseModel):
    id: str
    template_id: str
    template_name: str
    operator: str
    status: str
    started_at: float
    finished_at: float | None = None
    result_summary: str = ""
    logs: list[str] = Field(default_factory=list)


class RunJobRequest(BaseModel):
    template_id: str
    operator: str = "console-user"


settings = Settings()
REQUEST_COUNTER = Counter("job_runner_requests_total", "Total job runner requests.", ["path", "method", "status"])
REQUEST_LATENCY = Histogram("job_runner_request_duration_seconds", "Job runner request latency.", ["path", "method"])
JOB_EXECUTIONS = Counter("job_runner_executions_total", "Total executed jobs.", ["template_id", "status"])

TEMPLATES = [
    JobTemplate(
        id="platform-health-scan",
        name="平台健康巡检",
        description="检查 AI Engine、Prometheus、Alertmanager 的健康接口。",
        category="inspection",
    ),
    JobTemplate(
        id="cmdb-topology-export",
        name="CMDB 拓扑导出",
        description="拉取 CMDB 拓扑并生成摘要，便于后续同步到图数据库。",
        category="cmdb",
    ),
    JobTemplate(
        id="event-summary-report",
        name="事件摘要报告",
        description="拉取事件中心数据并统计待处理、已确认、已关闭数量。",
        category="event",
    ),
]


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
            CREATE TABLE IF NOT EXISTS job_runs (
                id TEXT PRIMARY KEY,
                template_id TEXT NOT NULL,
                template_name TEXT NOT NULL,
                operator TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at REAL NOT NULL,
                finished_at REAL,
                result_summary TEXT NOT NULL,
                logs_json TEXT NOT NULL
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
        connection.commit()


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


def _row_to_job(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        id=row["id"],
        template_id=row["template_id"],
        template_name=row["template_name"],
        operator=row["operator"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        result_summary=row["result_summary"],
        logs=json.loads(row["logs_json"]),
    )


def _fetch_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def _get_template(template_id: str) -> JobTemplate:
    for template in TEMPLATES:
        if template.id == template_id:
            return template
    raise HTTPException(status_code=404, detail="job template not found")


def _create_job_record(template: JobTemplate, operator: str) -> JobRecord:
    job = JobRecord(
        id=str(uuid4()),
        template_id=template.id,
        template_name=template.name,
        operator=operator,
        status="queued",
        started_at=time(),
    )
    with _connect_db() as connection:
        connection.execute(
            """
            INSERT INTO job_runs (id, template_id, template_name, operator, status, started_at, finished_at, result_summary, logs_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.template_id,
                job.template_name,
                job.operator,
                job.status,
                job.started_at,
                job.finished_at,
                job.result_summary,
                json.dumps(job.logs, ensure_ascii=False),
            ),
        )
        connection.commit()
    _record_audit("run", "job", job.id, operator, f"执行作业模板: {template.name}")
    return job


def _append_log(job_id: str, message: str) -> None:
    job = _get_job_record(job_id)
    logs = [*job.logs, message]
    with _connect_db() as connection:
        connection.execute(
            "UPDATE job_runs SET logs_json = ? WHERE id = ?",
            (json.dumps(logs, ensure_ascii=False), job_id),
        )
        connection.commit()


def _update_job(job_id: str, **updates: object) -> JobRecord:
    job = _get_job_record(job_id)
    updated = job.model_copy(update=updates)
    with _connect_db() as connection:
        connection.execute(
            """
            UPDATE job_runs
            SET status = ?, finished_at = ?, result_summary = ?, logs_json = ?
            WHERE id = ?
            """,
            (
                updated.status,
                updated.finished_at,
                updated.result_summary,
                json.dumps(updated.logs, ensure_ascii=False),
                updated.id,
            ),
        )
        connection.commit()
    return updated


def _get_job_record(job_id: str) -> JobRecord:
    with _connect_db() as connection:
        row = connection.execute("SELECT * FROM job_runs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _row_to_job(row)


def _run_platform_health_scan() -> tuple[str, list[str]]:
    endpoints = [
        ("AI Engine", settings.ai_engine_url.rstrip("/") + "/healthz"),
        ("Prometheus", settings.prometheus_url.rstrip("/") + "/-/healthy"),
        ("Alertmanager", settings.alertmanager_url.rstrip("/") + "/-/healthy"),
    ]
    logs: list[str] = []
    for name, url in endpoints:
        try:
            payload = _fetch_text(url)
            logs.append(f"[OK] {name}: {url} -> {payload[:120]}")
        except urllib.error.URLError as error:
            logs.append(f"[FAIL] {name}: {url} -> {error}")
            raise RuntimeError(f"{name} health check failed") from error
    return ("平台核心健康巡检完成", logs)


def _run_cmdb_topology_export() -> tuple[str, list[str]]:
    payload = _fetch_json(settings.cmdb_url.rstrip("/") + "/api/v1/topology")
    services = payload.get("services", [])
    edges = payload.get("edges", [])
    logs = [
        f"服务数量: {len(services)}",
        f"依赖边数量: {len(edges)}",
    ]
    if services:
        logs.append(f"首个服务: {services[0].get('name', 'unknown')}")
    return ("CMDB 拓扑导出完成", logs)


def _run_event_summary_report() -> tuple[str, list[str]]:
    payload = _fetch_json(settings.ai_engine_url.rstrip("/") + "/api/v1/events")
    summary = payload.get("summary", {})
    logs = [
        f"待处理事件: {summary.get('open', 0)}",
        f"已确认事件: {summary.get('acknowledged', 0)}",
        f"已关闭事件: {summary.get('resolved', 0)}",
        f"总事件数: {payload.get('total', 0)}",
    ]
    return ("事件摘要生成完成", logs)


JOB_EXECUTORS: dict[str, Callable[[], tuple[str, list[str]]]] = {
    "platform-health-scan": _run_platform_health_scan,
    "cmdb-topology-export": _run_cmdb_topology_export,
    "event-summary-report": _run_event_summary_report,
}


async def _execute_job(job_id: str) -> None:
    job = _get_job_record(job_id)
    _update_job(job_id, status="running")
    _append_log(job_id, f"作业开始执行: {job.template_name}")

    try:
        executor = JOB_EXECUTORS[job.template_id]
        result_summary, logs = await asyncio.to_thread(executor)
        for log in logs:
            _append_log(job_id, log)
        _update_job(job_id, status="succeeded", finished_at=time(), result_summary=result_summary)
        _record_audit("complete", "job", job_id, job.operator, result_summary)
        JOB_EXECUTIONS.labels(template_id=job.template_id, status="succeeded").inc()
    except Exception as error:
        _append_log(job_id, f"作业执行失败: {error}")
        _update_job(job_id, status="failed", finished_at=time(), result_summary=str(error))
        _record_audit("fail", "job", job_id, job.operator, str(error))
        JOB_EXECUTIONS.labels(template_id=job.template_id, status="failed").inc()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _initialize_db()
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


@app.get("/api/v1/templates")
async def list_templates() -> dict[str, list[dict[str, object]]]:
    return {"templates": [template.model_dump() for template in TEMPLATES]}


@app.get("/api/v1/jobs")
async def list_jobs() -> dict[str, object]:
    with _connect_db() as connection:
        rows = connection.execute("SELECT * FROM job_runs ORDER BY started_at DESC").fetchall()
    jobs = [_row_to_job(row) for row in rows]
    return {"total": len(jobs), "jobs": [job.model_dump() for job in jobs]}


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    return _get_job_record(job_id).model_dump()


@app.post("/api/v1/jobs/run")
async def run_job(payload: RunJobRequest) -> dict[str, object]:
    template = _get_template(payload.template_id)
    job = _create_job_record(template, payload.operator)
    asyncio.create_task(_execute_job(job.id))
    return {"accepted": True, "job": job.model_dump()}