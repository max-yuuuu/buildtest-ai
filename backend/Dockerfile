# ============================================================
# Stage: base — Python 运行时基础
# ============================================================
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
RUN pip install uv

# ============================================================
# Stage: deps — Python 依赖（被 dev / runner 复用）
# ============================================================
FROM base AS deps
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-cache --system -r requirements.txt

# ============================================================
# Stage: dev — 开发镜像（compose backend 使用）
# ============================================================
FROM deps AS dev
COPY . .
RUN chmod +x /app/docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================================
# Stage: runner — 生产运行镜像（compose celery-worker 使用）
# 基础镜像使用带 apt 缓存的定制镜像，apt 包只下载一次
# ============================================================
FROM base AS runner
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY . /app/
RUN chmod +x /app/docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
CMD ["celery", "-A", "app.core.celery_app", "worker", "-l", "info"]
