---
status: Ready for Review
title: 无感启动模式（本地单启前后端 + Docker 公共服务）
date: 2026-04-24
slug: seamless-dev-startup
owners:
  - platform
---

## 背景与问题

当前项目已支持“基础设施用 Docker、前后端本地启动”的混合开发模式（见 `README.md`、`build-test-ai.md` §2.1）。但在实践中仍存在以下痛点：

- 本地启动前端/后端时，需要在多处/多次覆盖 `BACKEND_URL`、`DATABASE_URL`、`REDIS_URL`、`QDRANT_URL` 等，团队成员容易出错，切换模式成本高。
- 前后端互相访问、以及访问公共服务（Postgres/Redis/Qdrant）时，`localhost` 与 compose service name（如 `postgres`、`redis`、`qdrant`、`backend`）之间语义不同，导致“要记住当前谁在 Docker、谁在本机”。
- 全 Docker 模式虽省心，但本地调试时常需要单独起前端或后端；希望两种模式在配置上都“无感”。

## 目标

- **无感切换**：开发者只需要选择“我要本机起前端/后端/两者”，无需手动改 `.env` 或到处改 URL。
- **单组件启动友好**：前端可单独本机启动；后端可单独本机启动；两者都本机启动时也无需额外配置。
- **公共服务容器化**：Postgres/Redis/Qdrant（以及可选的 celery-worker）通过 Docker 提供，默认一条命令拉起。
- **全 Docker 零额外配置**：`docker compose up --build` 仍然开箱即用，不引入新的必填配置。
- **团队协作简洁**：统一入口命令、统一约定的环境变量文件与加载规则；新成员按文档执行即可。

## 非目标

- 不改变现有前端“BFF 透传后端”的架构约束：前端组件仍只走 `/api/backend/*`，不直连 FastAPI。
- 不改变后端分层与异步任务原则（Celery 等）。
- 不在本规格中引入生产部署体系（K8s/Helm 等）。

## 用户故事

- 作为前端开发，我希望在 `frontend/` 里一条命令启动前端，本地自动能访问到后端（无论后端在 Docker 还是本机）。
- 作为后端开发，我希望在 `backend/` 里一条命令启动后端，本地自动能连上 Docker 里的 Postgres/Redis/Qdrant。
- 作为新同学，我希望只需复制 `.env.example` 并填密钥，然后按文档运行“默认开发模式”，无需理解网络细节。
- 作为 CI/集成测试，我希望仍可使用全 Docker 模式，保证环境一致性。

## 约束与现状（事实）

- 根目录 `.env.example` 默认是 docker compose 语义（服务名网络：`postgres`/`redis`/`qdrant`/`backend`）。
- 前端 BFF 代理读取 `BACKEND_URL`（见 `frontend/app/api/backend/[...path]/route.ts`）。
- 后端读取环境变量（见 `backend/app/core/config.py`），本机启动时通常需要把基础设施地址切到 `localhost`。
- 当前仓库已有 `docker-compose.infra.yml`（仅基础设施）与 `docker-compose.yml`（全栈）。

## 设计概览

### 核心思路：用“启动入口脚本 + 分层 env 文件”消灭手动改 URL

引入一套**统一启动入口**（脚本或 package scripts），由入口根据“组件运行位置（本机/容器）”加载相应 env 片段，从而做到：

- `.env` 继续用于**密钥与共享默认值**（单一事实源，避免复制敏感信息）。
- 新增“模式覆盖文件”，仅覆盖网络地址类变量（非敏感）。
- 启动命令永远不要求开发者手工输入 `DATABASE_URL=...` 这种覆盖。

### 环境变量分层（提案）

新增以下文件（均不包含密钥，仅承载“运行位置相关的 URL/端口覆盖”）：

- `env/.env.shared`：非敏感默认值（端口、feature flags、路径等）
- `env/.env.docker`：全 Docker 模式下，容器内互访用 service name（如 `postgres`、`redis`、`qdrant`、`backend`）
- `env/.env.host`：本机进程访问 Docker 暴露端口（如 `localhost:5432`、`localhost:6379`、`localhost:6333`、`localhost:8000`）
- `env/.env.frontend-host`：前端本机运行时的最小覆盖（`BACKEND_URL=http://localhost:8000`）
- `env/.env.frontend-docker`：前端容器运行时访问后端的位置（通常 `BACKEND_URL=http://backend:8000`）
- `env/.env.backend-host`：后端本机运行时访问基础设施（`DATABASE_URL`/`REDIS_URL`/`QDRANT_URL` 指向 `localhost`）
- `env/.env.backend-docker`：后端容器运行时访问基础设施（指向 service name）

约定：

- 仓库中仅提交 `env/*.example`（例如 `env/.env.shared.example`、`env/.env.backend-host.example` 等）
- 开发者本地按需复制为无后缀文件（例如 `cp env/.env.backend-host.example env/.env.backend-host`）
- 根目录 `.env` 仍用于密钥与少量共享默认值，且必须保持在 `.gitignore` 中不提交

### 统一启动入口（提案）

在仓库根目录提供 `./scripts/dev`（或 `make dev-*`）作为统一入口：

- `dev infra`：起基础设施（docker compose infra）
- `dev frontend`：本机启动 Next.js（自动加载前端 host 模式 env）
- `dev backend`：本机启动 FastAPI（自动加载后端 host 模式 env）
- `dev full`：全 Docker 启动（保持现状）
- `dev up`：默认开发模式（推荐：infra + backend(host) + frontend(host)）

入口脚本负责：

- 按命令选择要加载的 env 文件组合（shared + 组件模式覆盖 + `.env` 密钥）
- 在 macOS/Linux 下尽可能一致地工作
- 提供 `--print-env` 用于排错

决策：

- 采用 **Makefile 作为主入口**（命令短、目标清晰），但 **Makefile 内部调用 `scripts/dev`** 处理 env 合并与跨目录启动（减少 Makefile 复杂度）
- Windows 支持边界：**不承诺原生 CMD/PowerShell 直接运行**；允许通过 **WSL2**（或 Git Bash）使用 `make`/`bash` 完成开发（后续如团队需要再补充原生脚本）

## 启动模式定义（期望行为）

### 模式 A：默认开发（推荐）

- Docker：`postgres`/`redis`/`qdrant`
- Host：`backend`（可选 worker）+ `frontend`
- 前端访问后端：`http://localhost:8000`
- 后端访问基础设施：`localhost` 端口

### 模式 B：前端本地 + 后端 Docker

- Docker：`postgres`/`redis`/`qdrant`/`backend`/`celery-worker`
- Host：`frontend`
- 前端访问后端：`http://localhost:8000`（因为后端容器端口映射到宿主机）

### 模式 C：后端本地 + 前端 Docker

- Docker：`postgres`/`redis`/`qdrant`/`frontend`（可选 worker）
- Host：`backend`
- 前端访问后端：通过 `host.docker.internal:8000`（macOS/Windows）

说明：

- 团队当前不以 Linux 作为本地开发环境；Linux 主要用于 **部署运行 Docker**
- 因此本规格 **不强制** 为“Linux 本地开发 + 前端容器访问宿主机后端”提供开箱即用方案
- 若未来需要支持 Linux 本地开发，再引入 `extra_hosts: ["host.docker.internal:host-gateway"]`（Docker 20.10+）或提供单独 override 文件

### 模式 D：全 Docker

- Docker：全部服务
- Host：仅浏览器访问 `localhost:3000`
- 服务间访问：全部用 compose service name

## 具体需求（Requirements）

### R1. 零手改 `.env`

- 开发者不需要编辑 `.env` 里的 URL 来切换模式。
- `.env` 只承担密钥与少量环境无关默认值；地址类变量通过模式 env 覆盖。

### R2. 一条命令启动任意组合

- 必须提供标准入口命令，覆盖模式 A/B/C/D。
- 入口命令应在根目录运行，避免“要进不同目录才能启动”的认知负担。

### R3. 互访无感

- 前端始终通过 `BACKEND_URL` 控制 BFF 代理指向。
- 后端通过 `DATABASE_URL` / `REDIS_URL` / `QDRANT_URL` 指向基础设施。
- 当某组件运行在 Docker 中时，地址自动切换为 service name 语义；运行在 Host 时自动切换为 localhost 语义。

### R4. 可观测与可排错

- 提供 `dev doctor`（或等价命令）检查端口占用、基础设施连通性、关键 env 是否加载成功。
- 提供 `dev logs <service>` 查看 docker 服务日志。

`doctor` 检查深度（决策）：

- 必须做“真实连通性”检查：
  - Postgres：建立连接并执行 `SELECT 1`
  - Redis：`PING`
  - Qdrant：请求 health/version 等轻量接口（或 list collections）

## 实施设计（Implementation Design）

### 方案 1：Bash 脚本 `scripts/dev`（推荐默认）

- 优点：无额外依赖、跨 Node/Python 项目统一；对 CI 友好
- 缺点：Windows 原生不友好（需 WSL）；复杂逻辑可读性一般

实现要点：

- `scripts/dev` 负责解析命令，组合 env 文件，并 `export` 后启动对应进程
- 对前端：在 `frontend/` 下运行 `pnpm dev`，但 env 由脚本注入
- 对后端：在 `backend/` 下运行 `uv run uvicorn ...`，env 由脚本注入
- 对 docker：调用 `docker compose -f docker-compose.infra.yml up -d` 或 `docker compose up ...`

### 方案 2：Makefile

- 优点：最短命令、标准化目标
- 缺点：Windows 依赖 make；env 合并与跨平台处理仍需脚本辅助

> 本规格允许二选一或组合：Makefile 调 scripts。

### env 加载规则（强约定）

- 始终加载（顺序从低到高覆盖）：`env/.env.shared` → `.env` → 模式覆盖文件
- 禁止把密钥写进 `env/.env.*`，密钥仍只放 `.env`
- 模式覆盖文件只覆盖如下“网络相关”变量：`BACKEND_URL`、`DATABASE_URL`、`REDIS_URL`、`CELERY_*`、`QDRANT_URL`

兼容性说明（决策）：

- 当前根目录 `.env` 已包含 `DATABASE_URL/REDIS_URL/QDRANT_URL/BACKEND_URL`（偏 docker 语义）。
- **允许启动入口在运行时覆盖这些变量**，以实现“无感模式切换”，从而避免开发者手动改 `.env`。
- 覆盖范围仅限“地址类变量”，不会覆盖密钥。

### docker compose 调整（可能需要）

- 为 Linux 场景支持后端（Host）被前端（Docker）访问：在 `docker-compose.yml` 的 `frontend` 增加 `extra_hosts: ["host.docker.internal:host-gateway"]`
- 或提供 `docker-compose.linux.override.yml` 单独覆盖，避免影响 macOS/Windows

团队现状：

- 本地开发以 macOS/Windows 为主（Windows 通过 WSL2 运行 make/bash）
- Linux 用于部署与运行 Docker，不作为必须支持的本地开发环境

## 命令与交互（拟定）

以下为目标用户体验（示例）：

```bash
# 起基础设施
./scripts/dev infra

# 默认开发：infra + backend(host) + frontend(host)
./scripts/dev up

# 只起后端（host）并自动连 docker infra
./scripts/dev backend

# 只起前端（host），自动指向 localhost:8000
./scripts/dev frontend

# 全 docker（保持现状）
./scripts/dev full

# 诊断
./scripts/dev doctor
```

## 文档要求

- 更新 `README.md`：把“推荐做法：命令行覆盖”升级为“推荐做法：统一入口命令”，并保留高级用户手动覆盖方式作为备选。
- 更新 `build-test-ai.md`：在“本地开发模式与切换”补充“无感启动入口”的说明与排错章节。

## 兼容性与迁移

- 不破坏现有 `docker compose up --build` 行为。
- 现有开发方式（进入目录手动 `BACKEND_URL=... pnpm dev` / 手动覆写 `DATABASE_URL=... uvicorn ...`）仍可用，但不再是推荐路径。

## 测试计划

- 在 macOS 上验证四种模式 A/B/C/D 的启动、登录、以及最小 CRUD（任选一个资源）可用。
- 验证 `doctor` 能发现常见错误：端口被占用、容器未启动、`BACKEND_URL` 指向错误、DB 连不上等。
- 验证 CI 不受影响（若 CI 依赖 compose，保持命令兼容）。

## 风险与权衡

- 跨平台差异（尤其 Linux 的 `host.docker.internal`）可能带来维护成本，需要明确支持范围。
- env 分层文件若处理不当可能导致变量覆盖顺序混乱，必须在脚本中固定优先级，并提供 `--print-env` 排错。

## Clarifications Received

1. 入口采用 Makefile 可接受；Windows 不强制原生支持，可通过 WSL2 使用。
2. 当前无 Linux 本地开发同事；Linux 主要用于部署运行 Docker。
3. env 文件含密钥不应提交；仓库只提供 `.example`，本地复制生成实际文件。
4. `doctor` 需要做真实连通性检查（而非仅端口/容器健康）。
5. `.env` 当前包含这些 URL；不希望为切换模式手动修改 `.env`，而是通过启动时覆盖地址类变量实现无感切换。

