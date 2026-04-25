# BuildTest AI - OpenSpec Project Context

## 1) 项目目标

BuildTest AI 是面向 RAG / Agent 应用的开发、评测、迭代一体化平台。
平台核心目标不是“只把应用跑起来”，而是让 AI 应用具备可评测、可回溯、可持续优化的上线能力。

在所有需求讨论和实现决策中，评测链路的可追溯性优先级最高，尤其是：

- dataset -> evaluation_job -> evaluation_results 的血缘完整
- prompt / model / knowledge_base 的版本可回放
- bad case 可沉淀并用于下一轮优化

## 2) 单一事实源（SSOT）

- 产品与技术设计以 `buildtest-ai.md` 为 single source of truth
- 密钥与变量说明以 `KEYS.md` 为准
- 环境变量模板以 `.env.example` 为准

若实现与文档冲突，先判断是否文档滞后：

1. 若文档过期，先更新文档再改代码
2. 若代码偏离设计且无明确决策记录，按设计回归

## 3) 技术栈与分层

### 前端（含 BFF）

- Next.js App Router + TypeScript + React + shadcn/ui
- BFF 路由：`frontend/app/api/backend/[...path]/route.ts`
- 前端组件统一访问 `/api/backend/*`，不直连 FastAPI
- BFF 负责会话校验并注入 `X-User-Id`

### 后端

- Python 3.12 + FastAPI + SQLAlchemy + Alembic
- 分层约定：
  - `api/v1/`: 参数校验与编排（薄）
  - `services/`: 业务逻辑（厚）
  - `repositories/`: 数据访问
  - `models/`: ORM 模型
- 耗时任务走 Celery（如文档处理、评测执行）

### 基础设施

- PostgreSQL：业务数据
- Redis：Celery broker/backend
- Qdrant（可扩展 Milvus）：向量存储

向量存储必须通过 `vector_db_configs` 配置，不允许把 Qdrant 写成硬编码依赖。

## 4) 核心业务流

### 文档入库

上传文档 -> `documents.status=pending` -> 异步处理 -> 生成向量 -> 写入用户配置向量库 -> `status=completed`

### 评测执行

创建 `evaluation_jobs`（绑定 knowledge_base / prompt_template / dataset / llm_model）
-> 异步执行
-> 为每条 dataset_item 产出一条 `evaluation_results`
-> 记录 retrieved_context、scores、is_bad_case

## 5) 多租户与安全

- 所有业务查询必须按 `user_id` 隔离
- API key 使用加密字段存储：
  - `providers.api_key_encrypted`
  - `vector_db_configs.api_key_encrypted`
- 使用 `APP_ENCRYPTION_KEY`（Fernet）进行加解密

禁止更换或丢失已投入使用的 `APP_ENCRYPTION_KEY`。若必须轮换，需先完成全量解密/重加密迁移方案。

## 6) API 与数据约定

- API 路径统一：`/api/v1/<resource>`
- 长耗时动作通过 `POST .../run` 触发，`GET /tasks/{id}` 查询状态
- 禁止在请求线程中长时间阻塞等待任务完成
- 主键统一 UUID，表统一 `created_at` / `updated_at`
- 数据库变更统一走 Alembic migration，不直接手写 SQL 变更生产结构

模型类型约束：

- `models.model_type=embedding`：用于知识库向量化
- `models.model_type=llm`：用于评测与生成

Prompt 模板更新必须递增版本，不允许覆盖历史版本。

## 7) 工程实践

### 测试策略

- 后端：
  - unit：纯逻辑
  - integration：依赖真实中间件
  - e2e：端到端流程
- 前端：
  - unit：Vitest + Testing Library
  - e2e：Playwright

默认采用 TDD（Red -> Green -> Refactor）。

### 质量门禁

- 后端测试覆盖率目标 >= 80%
- 前端测试覆盖率目标 >= 70%
- 前端提交前至少通过 lint + typecheck
- 后端提交前至少通过 lint + tests

## 8) OpenSpec 产物编写偏好

本文件用于指导 OpenSpec 生成 `proposal.md` / `tasks.md` / 设计文档时的风格：

- 先写“为什么”（用户价值、风险、收益），再写“做什么”
- 每个提案至少说明：
  - 目标与非目标
  - 影响范围（前端/后端/数据/任务队列）
  - 回滚策略
  - 验收标准（可测试）
- 任务拆分以可独立验证为准，优先 0.5-2 天粒度
- 涉及 schema 变更时，必须单列 migration 与回填/兼容策略
- 涉及评测链路改动时，必须明确血缘字段和可追溯性检查点

## 9) 非目标（当前阶段）

- 不追求一次性支持所有向量数据库能力差异
- 不在早期阶段做过度通用化插件系统
- 不为了“看起来实时”而牺牲任务可观测性和稳定性

## 10) 术语约定

- Knowledge Base（KB）：知识库，包含文档与向量索引配置
- Dataset：评测数据集，包含多条测试样本
- Evaluation Job：一次完整评测执行实例
- Bad Case：未达到阈值或人工标注为问题样本的结果

