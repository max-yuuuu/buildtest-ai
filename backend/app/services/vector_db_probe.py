"""向量库连通性探测（Phase 1：postgres_pgvector、qdrant）。"""

from __future__ import annotations

import socket
import time
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.schemas.vector_db import VectorDbTestResult


def _normalize_postgres_dsn(dsn: str) -> str:
    s = dsn.strip()
    if s.startswith("postgresql+asyncpg://"):
        return "postgresql://" + s.removeprefix("postgresql+asyncpg://")
    if s.startswith("postgres+asyncpg://"):
        return "postgresql://" + s.removeprefix("postgres+asyncpg://")
    return s


_DOCKER_SERVICE_HOSTS = {"postgres", "redis", "qdrant", "backend"}


def _with_localhost_host(dsn: str) -> str:
    parts = urlsplit(dsn)
    host = parts.hostname or ""
    if host not in _DOCKER_SERVICE_HOSTS:
        return dsn
    if "@" not in parts.netloc:
        return dsn

    userinfo, hostport = parts.netloc.rsplit("@", 1)
    if hostport.startswith("["):
        return dsn

    if ":" in hostport:
        _, port = hostport.split(":", 1)
        netloc = f"{userinfo}@localhost:{port}"
    else:
        netloc = f"{userinfo}@localhost"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _is_host_resolution_error(exc: Exception) -> bool:
    if isinstance(exc, socket.gaierror):
        return True
    msg = str(exc).lower()
    return "nodename nor servname provided" in msg or "name or service not known" in msg


async def probe_postgres(connection_string: str) -> VectorDbTestResult:
    started = time.perf_counter()
    try:
        import asyncpg
    except ImportError as e:
        return VectorDbTestResult(
            ok=False,
            latency_ms=0,
            message=f"asyncpg 不可用: {e}",
        )

    dsn = _normalize_postgres_dsn(connection_string)
    tried_fallback = False
    try:
        conn = await asyncpg.connect(dsn, timeout=8.0)
    except Exception as e:
        fallback_dsn = _with_localhost_host(dsn)
        if fallback_dsn != dsn and _is_host_resolution_error(e):
            tried_fallback = True
            try:
                conn = await asyncpg.connect(fallback_dsn, timeout=8.0)
            except Exception as e2:
                elapsed = int((time.perf_counter() - started) * 1000)
                return VectorDbTestResult(ok=False, latency_ms=elapsed, message=str(e2))
        else:
            elapsed = int((time.perf_counter() - started) * 1000)
            return VectorDbTestResult(ok=False, latency_ms=elapsed, message=str(e))
    try:
        await conn.fetchval("SELECT 1")
        has_vec = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        if not has_vec:
            return VectorDbTestResult(
                ok=False,
                latency_ms=elapsed,
                message="已连接 PostgreSQL，但未安装 pgvector 扩展（CREATE EXTENSION vector）",
            )
        if tried_fallback:
            return VectorDbTestResult(
                ok=True,
                latency_ms=elapsed,
                message="ok（已自动回退 host=localhost，请更新连接地址）",
            )
        return VectorDbTestResult(ok=True, latency_ms=elapsed, message="ok")
    finally:
        await conn.close()


async def probe_qdrant(base_url: str, api_key: str | None) -> VectorDbTestResult:
    started = time.perf_counter()
    url = base_url.rstrip("/") + "/collections"
    headers = {}
    if api_key:
        headers["api-key"] = api_key
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, headers=headers)
    except Exception as e:
        elapsed = int((time.perf_counter() - started) * 1000)
        return VectorDbTestResult(ok=False, latency_ms=elapsed, message=str(e))
    elapsed = int((time.perf_counter() - started) * 1000)
    if r.status_code >= 400:
        return VectorDbTestResult(
            ok=False,
            latency_ms=elapsed,
            message=f"HTTP {r.status_code}: {r.text[:200]}",
        )
    return VectorDbTestResult(ok=True, latency_ms=elapsed, message="ok")


async def probe(
    db_type: str,
    connection_string: str,
    api_key_plain: str | None,
) -> VectorDbTestResult:
    started = time.perf_counter()
    if db_type == "postgres_pgvector":
        return await probe_postgres(connection_string)
    if db_type == "qdrant":
        return await probe_qdrant(connection_string, api_key_plain)
    elapsed = int((time.perf_counter() - started) * 1000)
    return VectorDbTestResult(
        ok=False,
        latency_ms=elapsed,
        message=f"类型 {db_type} 的连通性探测尚未实现",
    )
