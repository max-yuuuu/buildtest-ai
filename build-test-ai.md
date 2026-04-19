

# BuildTest AI 平台技术实现文档

## 1. 项目概述

### 1.1 产品定位
BuildTest AI 是一个面向 RAG 和 Agent 应用的开发、评测、迭代一体化平台。让 AI 应用从“能跑起来”到“敢上线”。

### 1.2 核心功能模块
- **Provider 管理**：统一管理 LLM 和 Embedding 模型的 API Key
- **向量库连接器**：支持 **PostgreSQL（pgvector）**、Qdrant、Milvus 等可插拔向量存储（详见附录 A.15）
- **知识库管理**：文档上传、切片策略配置、向量化与存储
- **Prompt 模板库**：版本化的 Prompt 管理，支持变量插槽
- **数据集管理**：QA 问答对和 Agent 轨迹数据的导入与管理
- **评测中心**：一键跑分、多维指标报告、版本对比
- **Agent 流程编排**（进阶）：可视化拖拽构建 Agent 工作流

### 1.3 技术栈总览
| 层级 | 技术选型 |
| :--- | :--- |
| 前端框架 | Next.js 16 (App Router) + TypeScript |
| UI 组件库 | shadcn/ui + Tailwind CSS |
| 后端框架 | Python FastAPI |
| 数据库 | PostgreSQL |
| 异步队列 | Celery + Redis |
| 向量数据库 | PostgreSQL(pgvector) / Qdrant / Milvus 等(可配置,见 A.15) |
| 认证 | NextAuth.js (GitHub / Google OAuth) |
| 部署 | Docker + Docker Compose |

## 2. 项目结构

```
buildtest-ai/
├── frontend/                    # Next.js 前端项目
│   ├── app/
│   │   ├── (auth)/             # 登录/注册页面
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── (dashboard)/        # 主控制台
│   │   │   ├── providers/      # Provider 管理
│   │   │   ├── knowledge/      # 知识库管理
│   │   │   ├── prompts/        # Prompt 模板
│   │   │   ├── datasets/       # 数据集管理
│   │   │   ├── evaluations/    # 评测中心
│   │   │   └── agents/         # Agent 编排 (进阶)
│   │   ├── api/                # Next.js API 路由 (BFF层)
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ui/                 # shadcn 组件
│   │   └── custom/             # 业务组件
│   ├── lib/
│   │   ├── auth.ts             # NextAuth 配置
│   │   └── api-client.ts       # 后端 API 调用封装
│   └── package.json
│
├── backend/                     # Python FastAPI 后端
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── providers/
│   │   │   │   ├── knowledge/
│   │   │   │   ├── embeddings/
│   │   │   │   ├── prompts/
│   │   │   │   ├── datasets/
│   │   │   │   └── evaluations/
│   │   ├── core/
│   │   │   ├── config.py       # 配置管理
│   │   │   ├── database.py     # DB 连接
│   │   │   └── celery_app.py   # Celery 配置
│   │   ├── models/             # SQLAlchemy 模型
│   │   ├── schemas/            # Pydantic 模型
│   │   ├── services/           # 业务逻辑层
│   │   │   ├── embedding_service.py
│   │   │   ├── vector_db_connector.py
│   │   │   └── evaluation_service.py
│   │   └── tasks/              # Celery 异步任务
│   │       ├── embedding_tasks.py
│   │       └── eval_tasks.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── docker-compose.yml
└── README.md
```

## 3. 数据库表结构设计

### 3.1 核心表清单

```sql
-- 用户表 (NextAuth 自动管理，此为扩展信息)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Provider 配置表
CREATE TABLE providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    provider_type VARCHAR(50) NOT NULL, -- 'openai', 'azure', 'anthropic', 'zhipu'
    api_key_encrypted TEXT NOT NULL,
    base_url VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 模型表 (关联到 Provider)
CREATE TABLE models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES providers(id) ON DELETE CASCADE,
    model_id VARCHAR(100) NOT NULL, -- 'gpt-4o', 'text-embedding-3-small'
    model_type VARCHAR(50) NOT NULL, -- 'llm', 'embedding'
    context_window INT,
    vector_dimension INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 向量库连接配置表
CREATE TABLE vector_db_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    db_type VARCHAR(50) NOT NULL, -- 枚举见附录 A.15；Phase 1 连接器优先: postgres_pgvector、qdrant
    connection_string TEXT NOT NULL,
    api_key_encrypted TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 知识库表
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    vector_db_config_id UUID REFERENCES vector_db_configs(id),
    collection_name VARCHAR(255) NOT NULL,
    embedding_model_id UUID REFERENCES models(id),
    chunk_size INT DEFAULT 512,
    chunk_overlap INT DEFAULT 50,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 知识库文档表
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_base_id UUID REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    file_size BIGINT,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    chunk_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Prompt 模板表
CREATE TABLE prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    version INT DEFAULT 1,
    system_prompt TEXT,
    user_prompt TEXT,
    variables JSONB DEFAULT '[]',
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 数据集表
CREATE TABLE datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    dataset_type VARCHAR(50) NOT NULL, -- 'qa', 'agent_trajectory'
    total_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 数据集条目表 (QA 类型)
CREATE TABLE dataset_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID REFERENCES datasets(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    expected_answer TEXT,
    context_ground_truth TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 评测任务表
CREATE TABLE evaluation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    knowledge_base_id UUID REFERENCES knowledge_bases(id),
    prompt_template_id UUID REFERENCES prompt_templates(id),
    dataset_id UUID REFERENCES datasets(id),
    llm_model_id UUID REFERENCES models(id),
    status VARCHAR(50) DEFAULT 'pending',
    metrics JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- 评测结果表
CREATE TABLE evaluation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES evaluation_jobs(id) ON DELETE CASCADE,
    dataset_item_id UUID REFERENCES dataset_items(id),
    question TEXT NOT NULL,
    actual_answer TEXT,
    retrieved_context TEXT,
    scores JSONB, -- { "faithfulness": 0.95, "answer_correctness": 0.8 }
    is_bad_case BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 4. API 接口设计

### 4.1 认证与用户
```
GET    /api/v1/users/me           # 获取当前用户信息
PUT    /api/v1/users/me           # 更新用户信息
```

### 4.2 Provider 管理
```
GET    /api/v1/providers          # 获取 Provider 列表
POST   /api/v1/providers          # 创建 Provider
PUT    /api/v1/providers/{id}     # 更新 Provider
DELETE /api/v1/providers/{id}     # 删除 Provider
GET    /api/v1/providers/{id}/models  # 获取 Provider 下的模型列表
```

### 4.3 向量库连接器
```
GET    /api/v1/vector-dbs         # 获取向量库配置列表
POST   /api/v1/vector-dbs         # 创建向量库配置
PUT    /api/v1/vector-dbs/{id}    # 更新向量库配置
DELETE /api/v1/vector-dbs/{id}    # 删除向量库配置
POST   /api/v1/vector-dbs/{id}/test  # 测试连接
```

### 4.4 知识库管理
```
GET    /api/v1/knowledge-bases        # 获取知识库列表
POST   /api/v1/knowledge-bases        # 创建知识库
GET    /api/v1/knowledge-bases/{id}   # 获取知识库详情
PUT    /api/v1/knowledge-bases/{id}   # 更新知识库
DELETE /api/v1/knowledge-bases/{id}   # 删除知识库
POST   /api/v1/knowledge-bases/{id}/documents  # 上传文档
GET    /api/v1/knowledge-bases/{id}/documents  # 获取文档列表
DELETE /api/v1/knowledge-bases/{id}/documents/{doc_id}  # 删除文档
POST   /api/v1/knowledge-bases/{id}/rebuild  # 重新向量化
```

### 4.5 Embedding 服务 (异步)
```
POST   /api/v1/embedding/process     # 触发文档向量化任务
GET    /api/v1/embedding/tasks/{task_id}  # 查询任务状态
```

### 4.6 Prompt 模板
```
GET    /api/v1/prompts           # 获取模板列表
POST   /api/v1/prompts           # 创建模板
GET    /api/v1/prompts/{id}      # 获取模板详情
PUT    /api/v1/prompts/{id}      # 更新模板 (自动版本递增)
DELETE /api/v1/prompts/{id}      # 删除模板
POST   /api/v1/prompts/{id}/preview  # 预览渲染后的 Prompt
```

### 4.7 数据集管理
```
GET    /api/v1/datasets          # 获取数据集列表
POST   /api/v1/datasets          # 创建数据集
GET    /api/v1/datasets/{id}     # 获取数据集详情
PUT    /api/v1/datasets/{id}     # 更新数据集
DELETE /api/v1/datasets/{id}     # 删除数据集
POST   /api/v1/datasets/{id}/items   # 批量导入条目
GET    /api/v1/datasets/{id}/items   # 获取条目列表
```

### 4.8 评测中心
```
GET    /api/v1/evaluations/jobs      # 获取评测任务列表
POST   /api/v1/evaluations/jobs      # 创建评测任务
GET    /api/v1/evaluations/jobs/{id} # 获取任务详情
POST   /api/v1/evaluations/jobs/{id}/run  # 执行评测
GET    /api/v1/evaluations/jobs/{id}/results  # 获取评测结果
GET    /api/v1/evaluations/jobs/{id}/report  # 获取评测报告
POST   /api/v1/evaluations/compare   # 对比多个评测任务
```

## 5. 前端页面规划

### 5.1 页面路由与功能

| 路由 | 页面名称 | 核心功能 |
| :--- | :--- | :--- |
| `/login` | 登录页 | GitHub/Google OAuth 登录 |
| `/dashboard` | 仪表盘 | 平台概览、快速入口、最近任务 |
| `/providers` | Provider 管理 | 增删改查模型厂商配置 |
| `/vector-dbs` | 向量库连接 | 先选类型(卡片展示优缺点),再填连接参数；文案数据源 `frontend/lib/vector-db-catalog.ts` |
| `/knowledge` | 知识库列表 | 展示所有知识库，支持创建/删除 |
| `/knowledge/[id]` | 知识库详情 | 文档上传、切片配置、向量化状态 |
| `/prompts` | Prompt 模板库 | 模板列表、版本管理 |
| `/prompts/[id]` | 模板编辑 | 变量定义、实时预览 |
| `/datasets` | 数据集管理 | 数据集列表、导入导出 |
| `/datasets/[id]` | 数据集详情 | 条目浏览、在线标注 |
| `/evaluations` | 评测任务 | 任务列表、创建新任务 |
| `/evaluations/[id]` | 评测报告 | 指标雷达图、Bad Case 分析 |
| `/agents` | Agent 编排 (进阶) | 嵌入 LangFlow 或自研画布 |

### 5.2 shadcn 组件使用建议
- 布局：`Sidebar` + `Header` + `Main`
- 数据表格：`Table` + `DataTable` (tanstack/react-table)
- 表单：`Form` + `Input` + `Select` + `Textarea`
- 反馈：`Toast` (sonner), `Dialog`, `Alert`
- 进度：`Progress` (用于文档处理状态)
- 图表：`Chart` (recharts，用于评测报告)

## 6. 关键实现细节

### 6.1 NextAuth 配置 (GitHub/Google)

```typescript
// frontend/lib/auth.ts
import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";
import Google from "next-auth/providers/google";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GitHub({ clientId: process.env.GITHUB_ID, clientSecret: process.env.GITHUB_SECRET }),
    Google({ clientId: process.env.GOOGLE_ID, clientSecret: process.env.GOOGLE_SECRET }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) token.id = user.id;
      return token;
    },
    async session({ session, token }) {
      if (token) session.user.id = token.id as string;
      return session;
    },
  },
});
```

### 6.2 FastAPI 与 Next.js BFF 层的对接

Next.js API 路由作为 BFF，负责：
1. 验证用户 Session
2. 转发请求到 Python 后端
3. 处理 SSE/WebSocket 连接

```typescript
// frontend/app/api/backend/[...path]/route.ts
import { auth } from "@/lib/auth";
import { NextRequest } from "next/server";

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  const session = await auth();
  if (!session) return new Response("Unauthorized", { status: 401 });

  const path = params.path.join("/");
  const body = await req.json();

  const response = await fetch(`${process.env.BACKEND_URL}/api/v1/${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": session.user.id,
    },
    body: JSON.stringify(body),
  });

  return response;
}
```

### 6.3 Celery 异步任务配置

```python
# backend/app/core/celery_app.py
from celery import Celery

celery_app = Celery(
    "buildtest-ai",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# 自动发现任务
celery_app.autodiscover_tasks(["app.tasks"])
```

### 6.4 文档向量化异步任务

```python
# backend/app/tasks/embedding_tasks.py
from app.core.celery_app import celery_app
from app.services.embedding_service import EmbeddingService

@celery_app.task(bind=True)
def process_document_task(self, document_id: str, knowledge_base_id: str):
    service = EmbeddingService()
    try:
        result = await service.process_document(document_id, knowledge_base_id)
        return result
    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise e
```

## 7. Docker Compose 部署配置

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: buildtest-ai
      POSTGRES_PASSWORD: buildtest-ai
      POSTGRES_DB: buildtest-ai
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://buildtest-ai:buildtest-ai@postgres:5432/buildtest-ai
      REDIS_URL: redis://redis:6379
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    environment:
      BACKEND_URL: http://backend:8000
      NEXTAUTH_URL: http://localhost:3000
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  postgres_data:
```

## 8. 开发优先级与里程碑

### Phase 1 (MVP - 4周)
- [x] 项目初始化，Docker 环境搭建
- [x] 用户认证 (NextAuth + GitHub/Google)
- [x] Provider 管理 CRUD
- [ ] 向量库连接器 CRUD
- [ ] 知识库管理 (创建/删除/上传文档)
- [ ] Embedding 服务 (同步处理，后续改异步)

### Phase 2 (核心评测 - 3周)
- [ ] Prompt 模板管理
- [ ] 数据集管理 (QA 对导入)
- [ ] 评测任务创建与执行
- [ ] 基础评测指标 (Faithfulness, Answer Correctness)
- [ ] 评测报告页面

### Phase 3 (进阶功能 - 4周)
- [ ] Embedding 服务异步化 (Celery)
- [ ] 评测结果对比 (A/B Test)
- [ ] Bad Case 归因与标注
- [ ] LangFlow 集成 (Agent 编排)

### Phase 4 (生产就绪 - 2周)
- [ ] 性能优化
- [ ] 错误处理与日志
- [ ] 部署文档
- [ ] 用户引导与文档

## 9. 注意事项

1. **API Key 安全存储**：生产环境务必使用 AWS KMS 或 HashiCorp Vault 加密存储
2. **文件上传大小限制**：前端和后端需统一配置，建议 50MB
3. **Embedding 模型限流**：调用 OpenAI 等 API 时需实现请求队列和重试机制
4. **评测结果持久化**：大规模评测时注意数据库写入性能
5. **LangFlow 集成**：如选择 iframe 嵌入，需处理跨域和认证令牌传递

---

## 附录 A:技术决策补遗(2026-04-17 团队评审)

原文档偏产品/架构视角,以下为开发启动前需要锁定的技术决策。

### A.1 评测指标与算法

| 指标 | 算法来源 | 说明 |
| :--- | :--- | :--- |
| faithfulness | RAGAS | 答案是否 grounded 于检索上下文 |
| answer_correctness | RAGAS | 与 expected_answer 的语义+事实一致性 |
| context_precision | RAGAS | 检索上下文的相关性排序质量 |
| context_recall | RAGAS | ground_truth 是否被上下文覆盖 |

- LLM-as-judge 模型与 Provider 在 `evaluation_jobs.judge_model_id` 中显式指定,默认 `gpt-4o-mini`
- 所有指标以 0~1 float 存入 `evaluation_results.scores` JSONB
- 黄金回归集:仓库内置 `backend/tests/fixtures/golden_qa.jsonl`(≥20 条),每次 CI 跑以防止指标回归

### A.2 RAG 检索链路

- 默认 `top_k=5`, `similarity_threshold=0.7`,可在知识库级别覆盖
- 初版仅支持向量检索,不做 hybrid/rerank(Phase 3 再加)
- 切片策略:`RecursiveCharacterTextSplitter`,按文件类型分派 loader
  - PDF: PyMuPDF / pypdf
  - DOCX: python-docx
  - Markdown: 按标题层级切,保留 front-matter 元数据
  - TXT: 直接按 chunk_size 切

### A.3 Embedding 维度管理

- `knowledge_bases` 表新增 `embedding_dimension INT NOT NULL` 字段
- 切换 embedding 模型时,若维度不一致强制提示"必须重建 collection"
- collection 命名:`kb_{knowledge_base_id}_{embedding_dimension}`

### A.4 加密与密钥管理

- 算法:**Fernet**(cryptography 库,AES-128-CBC + HMAC-SHA256)
- 主密钥:环境变量 `APP_ENCRYPTION_KEY`,44 字符 base64
- 所有 `*_encrypted` 字段进出数据库均经过 `EncryptedField` SQLAlchemy TypeDecorator,业务代码无感
- 生产环境主密钥托管:AWS KMS / HashiCorp Vault,通过 init container 注入

### A.5 多租户隔离

- 落地层:**Repository 层**(非 Service 层)统一注入 `user_id` 过滤
- SQLAlchemy 使用 session-level `info["user_id"]`,Repository 基类读取并拼接 WHERE
- 任何 raw SQL 必须过代码审查,禁止绕过 Repository

### A.6 Celery 任务规范

- 默认 `task_acks_late=True` + `max_retries=3` + 指数退避
- 幂等键:`task_id = hash(entity_id + version)` 作为 `self.request.id`
- 进度回传:`self.update_state(state="PROGRESS", meta={"progress": 0.5})`,前端 SSE 订阅
- 测试环境 `CELERY_TASK_ALWAYS_EAGER=True`,E2E 环境起真 worker

### A.7 限流

- LLM/Embedding 调用统一经过 `RateLimiter`(`aiolimiter`),按 `provider_id` 隔离令牌桶
- 默认 OpenAI embedding 500 req/min、gpt-4 50 req/min,可配置

### A.8 Prompt 渲染

- 引擎:**Jinja2**(StrictUndefined 模式)
- 变量 schema:`prompt_templates.variables` 存 JSONSchema,渲染前校验
- 预览接口 `/prompts/{id}/preview` 同步返回渲染结果+未填变量清单

### A.9 数据库迁移

- 工具:**Alembic**
- 迁移脚本放 `backend/alembic/versions/`,CI 强制要求 `alembic upgrade head` 可跑通
- 软删除:业务表统一加 `deleted_at TIMESTAMP NULL`,查询默认过滤

### A.10 前端技术选型补遗

| 关切 | 选型 |
| :--- | :--- |
| 数据请求 | TanStack Query v5 + axios |
| 类型同步 | openapi-typescript 从后端 OpenAPI 生成 `@/types/api.ts` |
| 表单 | react-hook-form + zod |
| UI 状态 | Zustand(仅侧栏折叠、主题等 UI 态) |
| 进度推送 | SSE,`/evaluations/jobs/{id}/stream` |
| 文件上传 | tus-js-client,分片 5MB |
| Prompt 编辑器 | Monaco Editor,变量 `{{name}}` 语法高亮 |
| 图表 | recharts(评测雷达图、柱状对比) |
| i18n | next-intl,中英双语,默认中文 |
| 暗黑模式 | next-themes + shadcn 内置 |

### A.11 测试策略(TDD)

**测试金字塔:**

| 层 | 工具 | 覆盖率门禁 |
| :--- | :--- | :--- |
| 后端单测 | pytest + pytest-asyncio | ≥80% |
| 后端集成 | pytest + testcontainers(postgres/redis/qdrant) | 关键路径 100% |
| 前端组件 | Vitest + Testing Library | ≥70% |
| E2E | Playwright | 冒烟路径 100% |
| 契约 | schemathesis(基于 OpenAPI) | 所有公开 API |

**外部依赖隔离:**
- LLM / Embedding 调用:**VCR.py**(后端) 录制回放,`tests/cassettes/`
- 前端:**MSW** 拦截 fetch,mock 响应固化在 `frontend/mocks/`
- OAuth:测试环境用固定 JWT,不走真 GitHub/Google

**TDD 节奏(三人协作):**
1. Tester 先写失败的 **E2E/集成测试**(Red),提交 PR
2. Backend/Frontend 并行写各自单元测试 + 实现,直到 E2E 转绿(Green)
3. Pair 重构(Refactor),覆盖率达标后合并

### A.12 CI/CD

- 平台:GitHub Actions
- Pipeline:`lint` → `typecheck` → `unit` → `integration`(带 testcontainers) → `e2e`(Playwright) → `build` → `deploy`
- 每个 PR 必须全绿才可合并,覆盖率下降阻断合并

### A.13 观测性

- 日志:**structlog** JSON 格式,字段 `trace_id / user_id / event`
- Metrics:Prometheus `/metrics`,关键指标 `celery_task_duration`、`llm_tokens_total`
- 健康检查:`/healthz`(存活)、`/readyz`(依赖就绪:DB/Redis/向量库)

### A.14 表结构补丁

针对附录中的新字段,执行以下 DDL:

```sql
ALTER TABLE knowledge_bases ADD COLUMN embedding_dimension INT NOT NULL DEFAULT 1536;
ALTER TABLE evaluation_jobs ADD COLUMN judge_model_id UUID REFERENCES models(id);

-- 所有业务表统一加软删除
ALTER TABLE providers        ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE vector_db_configs ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE knowledge_bases  ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE documents        ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE prompt_templates ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE datasets         ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE evaluation_jobs  ADD COLUMN deleted_at TIMESTAMP;
```

### A.15 向量库选型、后端枚举与前端目录（Phase 1）

**原则**

- 向量存储通过 `vector_db_configs` 多租户配置,**禁止**在业务代码中硬编码某一厂商 SDK 为唯一路径；检索/写入经统一 `VectorDbConnector` 接口。
- **PostgreSQL + pgvector 为必选能力**（可与业务库同实例或只读副本）,满足合规与「一套库」运维诉求。
- Phase 1 **连接器实现优先级**：`postgres_pgvector` → `qdrant`；其余类型可先出现在**类型选择 UI**（展示优缺点、表单占位或「后续开放」）,待后续里程碑再接 SDK。

**`vector_db_configs.db_type` 建议枚举值**（小写 + 下划线,与前端 `VectorDbTypeId` 对齐）

| `db_type` | 说明 |
| :--- | :--- |
| `postgres_pgvector` | 现有 PostgreSQL 实例 + `pgvector` 扩展 |
| `qdrant` | Qdrant HTTP/gRPC |
| `milvus` | Milvus / Zilliz Cloud |
| `weaviate` | Weaviate |
| `pinecone` | Pinecone 托管索引 |
| `chroma` | Chroma（嵌入式或服务模式） |

**`/vector-dbs` 页面 UI 字段**（每种类型同一结构,便于卡片组件复用）

| 字段 | 说明 |
| :--- | :--- |
| `id` | 与上表 `db_type` 一致 |
| `name` | 展示名 |
| `tagline` | 一句话定位 |
| `pros` | 优点列表（3～5 条） |
| `cons` | 缺点列表（3～5 条） |
| `bestFor` | 更适合的场景（一句） |
| `connectorAvailable` | Phase 1 是否已接好「创建配置 + 测试连接」（其余为 `false`,仅展示文案） |
| `docsUrl` | 官方文档外链（可选） |

**各类型优缺点文案（与前端 `vector-db-catalog.ts` 保持同步）**

| 类型 | 优点 | 缺点 |
| :--- | :--- | :--- |
| PostgreSQL + pgvector | 与业务库同栈; ACID、权限与备份策略一致; 便于多租户与审计; 数据驻留友好 | 超大规模纯向量高 QPS 时成本与调优压力常高于专用库; 索引与参数需一定经验 |
| Qdrant | 部署轻、过滤丰富; 自托管/云可选; 适合 RAG 常见 metadata+向量 | 多一套基础设施与灾备设计; 与业务库分离时一致性需单独考虑 |
| Milvus | 海量向量、分布式与索引类型较全; 托管云可减负 | 组件与概念多、运维与排障成本高; 小规模易过重 |
| Weaviate | 模块生态、对象+向量建模; hybrid 等能力利于后续增强 | 资源与部署相对重; 与 Postgres 事实源并存时需划清主从边界 |
| Pinecone | 免运维、接入快、弹性由厂商承担 | 数据在第三方; 成本与网络依赖; 强 VPC/合规场景需单独评估 |
| Chroma | 开发体验好、嵌入式极轻 | 大规模生产 HA/多租户需审慎评估部署模式 |

**可选后续 API**：`GET /api/v1/vector-db-types` 返回上表结构化数据,便于运营改文案；Phase 1 默认以前端静态目录为准,避免前后端重复维护。

**实现落盘**：`frontend/lib/vector-db-catalog.ts` 导出 `VECTOR_DB_CATALOG`、`getVectorDbCatalogEntry`；连接器开发完成后将 `connectorAvailable` 按实际上线情况改为 `true`。

