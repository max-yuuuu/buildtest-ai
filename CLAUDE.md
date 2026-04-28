# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---------------------

## 单一事实源

设计文档 `buildtest-ai.md` 是产品与技术设计的 **single source of truth**(数据库 schema §3、API 风格 §4、里程碑 §8 都在此)。与代码冲突时,先确认是否是文档滞后;若是,更新文档再改代码。`KEYS.md` 为密钥清单,`.env.example` 为变量模板。

## 产品定位

BuildTest AI 是面向 RAG / Agent 应用的 **开发 + 评测 + 迭代** 一体化平台。核心价值是让 AI 应用从"能跑起来"走到"敢上线",因此评测中心(指标、Bad Case、版本对比)是差异化功能,不是附属模块。做设计决策时优先保证评测链路的可追溯性(dataset → job → results 的完整血缘)。

## 高层架构

三层结构,开发期通过 `scripts/dev` 与 `compose.base.yml` / `compose.dev.yml` / `compose.prod.yml` / `compose.infra.yml` 编排(`postgres` / `redis` / `qdrant` / `backend` / `celery-worker` / `frontend`):

1. **frontend/** — Next.js 15 (App Router, React 19) + TypeScript + shadcn/ui。**同时承担 BFF 角色**:`app/api/backend/[...path]/route.ts` 负责 NextAuth session 校验后透传请求到 Python 后端,并在 header 注入 `X-User-Id`。前端组件**不直连 FastAPI**,统一走 `/api/backend/*`。
2. **backend/** — Python 3.12 + FastAPI。分层:`api/v1/`(参数校验与编排,薄)→ `services/`(业务逻辑,厚)→ `repositories/`(DB 访问)→ `models/`(SQLAlchemy)。耗时操作(文档向量化、评测执行)走 `app/tasks/` 下的 Celery 任务,**不能在请求线程内同步完成**(Phase 1 例外:embedding 允许先同步,需显式 TODO)。
3. **基础设施** — PostgreSQL(业务数据,asyncpg)、Redis(Celery broker/backend)、Qdrant/Milvus(向量存储)。向量库通过 `vector_db_configs` 表做"多租户 + 可切换",**不要把 Qdrant 作为硬编码依赖**。

### 关键数据流

- **文档入库**: 上传 → `documents.status=pending` → Celery `process_document_task` → 调用用户配置的 embedding provider → 写入用户配置的向量库 collection → `status=completed`。
- **评测执行**: `evaluation_jobs` 绑定 (knowledge_base, prompt_template, dataset, llm_model) 四要素 → 异步跑 → 每条 dataset_item 产出一行 `evaluation_results`(含 retrieved_context、scores、is_bad_case)。版本对比依赖同一 dataset 的多个 job 结果做 diff。

### 多租户与加密

所有业务表都有 `user_id` 外键,查询必须按 user_id 隔离。`providers.api_key_encrypted` 和 `vector_db_configs.api_key_encrypted` 使用 Fernet 加密(主密钥 `APP_ENCRYPTION_KEY`,一旦落库**绝不能丢或换**,否则需先解密全部数据再重加密)。

## 命名与约定

- 数据库主键统一 UUID,所有表含 `created_at` / `updated_at`。迁移走 `alembic`,不要手写 SQL。
- API 路径 `/api/v1/<resource>`。异步任务用 `POST .../run` 触发,`GET /tasks/{id}` 查询状态,**不要**用长轮询 GET 阻塞请求线程。
- `models.model_type` 区分 `llm` vs `embedding`:知识库只能绑定 embedding 模型,评测任务只能绑定 llm 模型。
- Prompt 模板更新时 `version` 自动递增,**不要原地覆盖历史版本**——评测结果需回溯到具体 prompt 版本。

## Commit 规范

项目已启用 husky + commitlint + lint-staged(根 `package.json` / `commitlint.config.mjs` / `.husky/`)。生成 commit message 时必须满足:

- **格式**:`<type>(<scope>): <subject>`,遵循 Conventional Commits。
- **type 枚举**(commitlint 硬校验,超出会被拒):`feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert`。
- **scope 建议**(可选但推荐):`frontend` / `backend` / `db`(迁移)/ `kb`(知识库)/ `eval`(评测)/ `auth` / `ci` / `deps` / `docker`,跨域改动可省略 scope。
- **subject**:**使用中文**,祈使句,不加句号,不超过 50 字;header 整体 ≤100 字符。
- **body**(可选):解释 **为什么** 改,不是 **改了什么**——diff 已经能看出 what。跨越多文件或引入 breaking 改动时必须写。
- **footer**:破坏性变更用 `BREAKING CHANGE:` 开头;关联 issue 用 `Refs: #123` 或 `Closes: #123`。
- **范围控制**:一次 commit 聚焦一件事;前后端同步改动若耦合紧密可合并,否则拆开。迁移文件(`alembic/versions/*`)应单独 commit,scope 用 `db`。
- **生成工具**:推荐用 `/buddy:commit`(分析 diff 自动生成)。禁止 `--no-verify` 绕过 hook,除非紧急 hotfix 并在 PR 描述中说明。

示例:

```
feat(kb): 支持 qdrant 多租户 collection 隔离

每个用户的向量数据落到独立 collection,避免跨租户检索泄漏。
collection 名按 user_id 派生,vector_db_configs 新增 namespace 字段。
```

## 开发命令

全栈启动需先 `cp .env.example .env` 并填入 `GITHUB_ID/SECRET`、`GOOGLE_ID/SECRET`、`NEXTAUTH_SECRET`、`APP_ENCRYPTION_KEY`(详见 `KEYS.md`)。Provider 密钥通过应用内 UI 配置并加密存储。

```bash
# 全栈
docker compose up --build                    # 前端 :3000 / 后端 :8000 / API 文档 :8000/docs

# 后端(cd backend)
uvicorn app.main:app --reload                # 单独开发
celery -A app.core.celery_app worker -l info # worker
pytest                                       # 单元(默认含覆盖率门禁 ≥80%)
pytest -m integration                        # 需真实 DB/Redis/Qdrant
pytest -m e2e                                # 端到端
pytest tests/unit/test_foo.py::test_bar -v   # 单测
ruff check app tests                         # lint(E/F/I/UP/B/SIM)
alembic revision --autogenerate -m "msg"     # 生成迁移
alembic upgrade head                         # 应用迁移

# 前端(cd frontend)
pnpm dev                                     # dev server
pnpm build && pnpm start                     # 生产构建
pnpm lint                                    # ESLint
pnpm typecheck                               # tsc --noEmit
pnpm test                                    # vitest(覆盖率门禁 ≥70%)
pnpm test:watch                              # 交互式
pnpm test:e2e                                # Playwright
pnpm gen:api-types                           # 从后端 openapi.json 生成 lib/api-types.ts(改完后端 schema 必跑)
```

## 测试分层

- `backend/tests/unit/` — 纯逻辑,不依赖外部服务。
- `backend/tests/integration/` — 需 docker 起真实 Postgres/Redis/Qdrant(标记 `@pytest.mark.integration`)。
- `backend/tests/e2e/` — 端到端 API 流程(`@pytest.mark.e2e`),外部 API 调用用 VCR cassette 回放。
- `frontend/tests/unit/` — Vitest + Testing Library;`frontend/tests/e2e/` — Playwright。
- TDD(Red-Green-Refactor)是默认开发模式,先写失败的测试再写实现。

## 里程碑优先级

按 `buildtest-ai.md` §8 分阶段推进。**Phase 1 的 Embedding 允许先同步实现**(显式注明 TODO),Phase 3 再切 Celery——不要在 Phase 1 就过度设计异步链路。
