# BuildTest AI

RAG / Agent 应用的 **开发 + 评测 + 迭代** 一体化平台。

## 文档

- `buildtest-ai.md` — 产品与技术设计(含附录 A:团队评审决策)
- `KEYS.md` — 密钥与环境变量清单
- `.env.example` — 环境变量模板

## 快速开始

1. **准备密钥**(详见 `KEYS.md`):
   - GitHub/Google OAuth
   - `NEXTAUTH_SECRET`:`openssl rand -base64 32`
   - `APP_ENCRYPTION_KEY`:`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

2. **创建 `.env`**:
   ```bash
   cp .env.example .env
   # 填入上一步生成的值
   ```

3. **启动**:
   ```bash
   docker compose up --build
   ```
   - 前端:http://localhost:3000
   - 后端:http://localhost:8000
   - API 文档:http://localhost:8000/docs

## 本地开发模式（推荐）

本项目支持“**基础设施用 Docker，前后端 + worker 本地启动**”的混合模式，便于调试且不强依赖容器环境。

- **基础设施**：Postgres / Redis / Qdrant 用 Docker 跑
- **应用层**：Next.js / FastAPI / Celery Worker 用本机进程跑

### 一次性准备（仅首次）

0) 安装本机工具：

- Docker（含 `docker compose`）
- `uv`
- `pnpm`

1) 创建根目录 `.env`（密钥放这里）：

```bash
cp .env.example .env
# 按 KEYS.md 填写必要密钥（OAuth / NEXTAUTH_SECRET / APP_ENCRYPTION_KEY 等）
```

`.env` 建议仅放密钥与通用配置；`DATABASE_URL` / `REDIS_URL` / `QDRANT_URL` / `BACKEND_URL` 等地址类变量统一放到 `env/dev.*`。
`UPLOAD_DIR` 建议保持默认（`env/dev.shared` 中配置），由启动脚本统一解析为仓库根目录下的绝对路径，避免 backend 与 worker 因工作目录不同产生 `backend/uploads` 与 `uploads` 混用。

2) 复制开发模式覆盖文件（不含密钥，仅 URL/端口/路径）：

```bash
cp env/dev.shared.example env/dev.shared
cp env/dev.backend-host.example env/dev.backend-host
cp env/dev.frontend-host.example env/dev.frontend-host
```

3) 安装依赖（仅首次或依赖变更后）：

- 后端：`cd backend && uv pip install -r requirements.txt`
- 前端：`cd frontend && pnpm install`

### 只启动基础设施（Docker）

在仓库根目录：

```bash
make infra
```

### 本机启动后端（FastAPI）

后端默认从根目录 `.env` 读取密钥等配置，地址类变量通过 `env/dev.*` 覆盖实现无感切换：

```bash
make backend
```

### 本机启动 Celery Worker

```bash
make worker
```

### 本机启动前端（Next.js）

前端通过 BFF 路由 `/api/backend/*` 代理到 Python 后端（见 `frontend/app/api/backend/[...path]/route.ts`）：

```bash
make frontend
```

### 默认推荐：一条命令拉起（infra + 后端本机 + worker 本机 + 前端本机）

```bash
make up
```

> `make up` / `make backend` 会在启动后端前自动执行 `alembic upgrade head`，通常无需手动迁移。

### 排错

```bash
make print-env
make doctor
```

若出现“文档入库失败：原文文件不存在”，优先检查是否同时运行了多套 worker（如 docker worker + 本地 worker），并确认 `make print-env` 输出的 `UPLOAD_DIR` 为同一绝对路径。

> 更多“全 Docker / 前端本地 / 后端本地 / 全本地”的组合与切换策略，见 `build-test-ai.md` 的“本地开发模式与切换”章节。

## 目录

```
buildtest-ai/
├── backend/           FastAPI + Celery + Alembic
│   ├── app/
│   ├── tests/
│   └── alembic/
├── frontend/          Next.js 16 + shadcn/ui
│   ├── app/
│   ├── components/
│   └── tests/
├── docker-compose.yml
└── .github/workflows/ CI 流水线
```

## 开发命令

**后端:**
```bash
cd backend
pytest                                       # 单元测试
pytest -m integration                        # 集成测试(需 docker)
alembic revision --autogenerate -m "msg"    # 新迁移
alembic upgrade head                         # 应用迁移
```

**前端:**
```bash
cd frontend
pnpm dev                                     # 开发
pnpm test                                    # 单元测试
pnpm test:e2e                                # Playwright E2E
pnpm gen:api-types                           # 从后端 OpenAPI 生成 TS 类型
```

## 开发模式

**TDD(Red-Green-Refactor)**:
1. 先写失败的测试
2. 写最小实现让测试通过
3. 重构,保持测试绿色

覆盖率门禁:后端 ≥80%,前端 ≥70%。
