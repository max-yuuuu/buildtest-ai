# BuildTest AI

RAG / Agent 应用的 **开发 + 评测 + 迭代** 一体化平台。

## 文档

- `build-test-ai.md` — 产品与技术设计(含附录 A:团队评审决策)
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

## 目录

```
build-test-ai/
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
