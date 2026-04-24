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
   - OpenAI API Key(可选)

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

本项目支持“**基础设施用 Docker，前后端本地启动**”的混合模式，便于调试且不强依赖容器环境。

- **基础设施**：Postgres / Redis / Qdrant 用 Docker 跑
- **应用层**：Next.js / FastAPI 用本机进程跑

### 只启动基础设施（Docker）

在仓库根目录：

```bash
docker compose up -d postgres redis qdrant
```

### 本机启动后端（FastAPI）

后端默认从根目录 `.env` 读取配置（`backend/app/core/config.py`），当后端本机跑时，需要把连接地址指向 `localhost`。推荐用**命令行覆盖**，避免频繁修改 `.env`：

```bash
cd backend

# 使用 uv 管理 Python/虚拟环境，并用 requirements.txt 安装依赖
uv python install 3.12
uv venv
uv pip install -r requirements.txt

DATABASE_URL="postgresql+asyncpg://buildtest:buildtest@localhost:5432/buildtest" \
REDIS_URL="redis://localhost:6379/0" \
CELERY_BROKER_URL="redis://localhost:6379/0" \
CELERY_RESULT_BACKEND="redis://localhost:6379/1" \
QDRANT_URL="http://localhost:6333" \
UPLOAD_DIR="./uploads" \
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 本机启动前端（Next.js）

前端通过 BFF 路由 `/api/backend/*` 代理到 Python 后端（见 `frontend/app/api/backend/[...path]/route.ts`），本机跑前端时把 `BACKEND_URL` 指到本机后端即可：

```bash
cd frontend
pnpm install

BACKEND_URL="http://localhost:8000" \
pnpm dev
```

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
