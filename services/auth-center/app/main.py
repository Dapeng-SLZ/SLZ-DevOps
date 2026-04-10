from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter, time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_CENTER_")

    app_name: str = "SLZ Auth Center"
    platform_db_path: str = "/app/runtime/platform.db"
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "Admin@123456"
    bootstrap_admin_display_name: str = "平台管理员"
    session_cookie_name: str = "slz_session"
    session_ttl_seconds: int = 60 * 60 * 12


class LoginRequest(BaseModel):
    username: str
    password: str


class UserProfile(BaseModel):
    username: str
    display_name: str
    role: str
    permissions: list[str]


settings = Settings()
REQUEST_COUNTER = Counter("auth_center_requests_total", "Total auth center requests.", ["path", "method", "status"])
REQUEST_LATENCY = Histogram("auth_center_request_duration_seconds", "Auth center request latency.", ["path", "method"])


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


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"slz-auth::{password}".encode("utf-8")).hexdigest()


def _initialize_db() -> None:
    with _connect_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                permissions_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        existing_admin = connection.execute(
            "SELECT id FROM auth_users WHERE username = ?",
            (settings.bootstrap_admin_username,),
        ).fetchone()
        if existing_admin is None:
            connection.execute(
                """
                INSERT INTO auth_users (id, username, display_name, role, password_hash, permissions_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    settings.bootstrap_admin_username,
                    settings.bootstrap_admin_display_name,
                    "platform-admin",
                    _hash_password(settings.bootstrap_admin_password),
                    '["platform:read","platform:write","jobs:run","events:manage","cmdb:manage"]',
                    time(),
                ),
            )
        connection.commit()


def _row_to_user(row: sqlite3.Row) -> UserProfile:
    import json

    return UserProfile(
        username=row["username"],
        display_name=row["display_name"],
        role=row["role"],
        permissions=json.loads(row["permissions_json"]),
    )


def _get_user_by_username(username: str) -> sqlite3.Row | None:
    with _connect_db() as connection:
        return connection.execute(
            "SELECT * FROM auth_users WHERE username = ?",
            (username,),
        ).fetchone()


def _create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = time()
    with _connect_db() as connection:
        connection.execute(
            "INSERT INTO auth_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now, now + settings.session_ttl_seconds),
        )
        connection.commit()
    return token


def _get_user_from_token(token: str | None) -> UserProfile:
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


def _delete_session(token: str | None) -> None:
    if not token:
        return
    with _connect_db() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        connection.commit()


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


@app.post("/api/v1/login")
async def login(payload: LoginRequest, response: Response) -> dict[str, object]:
    user = _get_user_by_username(payload.username)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    expected_hash = user["password_hash"]
    if not hmac.compare_digest(expected_hash, _hash_password(payload.password)):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = _create_session(user["id"])
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        path='/',
    )
    return {"authenticated": True, "user": _row_to_user(user).model_dump()}


@app.post("/api/v1/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    _delete_session(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(settings.session_cookie_name, path='/')
    return {"logged_out": True}


@app.get("/api/v1/me")
async def me(request: Request) -> dict[str, object]:
    user = _get_user_from_token(request.cookies.get(settings.session_cookie_name))
    return {"user": user.model_dump()}


@app.get("/api/v1/navigation")
async def navigation(request: Request) -> dict[str, object]:
    _get_user_from_token(request.cookies.get(settings.session_cookie_name))
    return {"groups": NAVIGATION}
