## Why

当前 Quick Chat 已经具备基础的单知识库 query-time RAG 链路，但仍存在三个明显缺口：

- 交互层只支持单知识库切换，无法通过 `@知识库` 在单轮问题中组合多个知识库。
- 前端流式协议仍停留在旧的自定义 data 映射，未对齐 `ai@6 latest` 的 UI message stream 目标协议。
- 后端 Python（LangChain/LangGraph）与前端 AI SDK UI 之间缺少一层稳定、可测试的协议边界，tool 消息也无法作为一等输出展示。

同时，当前项目处于开发阶段，需要保证 host 开发环境与 Docker 开发环境的行为尽量一致，否则 chat 流协议、依赖版本与环境变量极易漂移，导致“本地能跑 / Docker 不能跑”的问题。

## What Changes

- 将 Quick Chat 请求契约从单 `knowledge_base_id` 重构为统一的 `knowledge_base_ids[]`。
- 引入“默认主知识库 + 输入框 `@知识库` 本轮覆盖”的交互契约，并以此驱动前后端请求体。
- 后端输出稳定的 Python 领域流事件：文本、数据、tool、错误、完成。
- Next BFF 将 Python SSE 领域事件映射为 `ai@6 latest` 可消费的 UI message stream parts。
- 前端 chat UI 升级为 Notion AI 风格的输入/消息布局，并支持 data/tool parts 展示。
- 明确开发环境与 Docker 开发环境的依赖、环境变量与启动约束，确保二者的 chat 行为一致。

## Capabilities

### New Capabilities

- `multi-kb-chat-request-contract`: 定义 `knowledge_base_ids[]` 的唯一请求契约与 `@KB` 绑定规则。
- `python-chat-domain-stream`: 定义 Python 后端 SSE 领域事件模型（text/data/tool/error/done）。
- `ai-sdk6-bff-stream-mapping`: 定义 Next BFF 到 `ai@6 latest` UI message stream parts 的映射约束。
- `quick-chat-multi-kb-ui`: 定义 Quick Chat 的默认主知识库、mention 交互与 tool/data 渲染。
- `dev-docker-chat-env-parity`: 定义 host 开发环境与 Docker 开发环境在 chat 依赖、环境变量、后端发现与运行方式上的一致性要求。

### Modified Capabilities

- `quick-chat-workflow`: 从单知识库检索改为多知识库合并检索，并增加 tool 事件输出。
- `retrieval-lineage-contract`: citation 与 step 需包含 `knowledge_base_id`，支持多库来源追踪。
- `chat-mode-routing`: quick 模式请求体和流式输出契约更新到 `knowledge_base_ids[]` 与 AI SDK 6 目标协议。

## Impact

- Affected code:
  - `backend/app/schemas/chat.py`
  - `backend/app/services/chat_service.py`
  - `backend/app/services/quick_chat_workflow.py` 或 `backend/app/chat/application/quick_chat_use_case.py`
  - `backend/app/chat/*` tool / adapter / facade 相关层
  - `frontend/app/api/chat/route.ts`
  - `frontend/app/(dashboard)/chat/page.tsx`
  - `frontend/package.json` 与相关前端测试
  - `env/*.env` / `frontend/.env` / `docker-compose*.yml` / 启动文档
- Affected APIs:
  - chat 请求体仅保留 `knowledge_base_ids[]`
  - Python→BFF SSE 领域事件
  - BFF→browser UI message stream parts（按 `ai@6 latest` 本地文档确认）
- Dependencies:
  - 前端新增 `ai@6 latest`
  - 可能新增与 `ai@6` 匹配的相关包（以本地文档确认为准）
- Database:
  - **本期 MVP 默认不新增聊天持久化表/字段**
  - 原因：当前 spec 明确不做多会话/历史会话管理，默认主知识库只需作为当前页面与当前请求的交互状态即可
  - 若后续引入 chat session persistence，再单独提 change 增加 `chat_sessions.default_knowledge_base_id` 等字段
  - 具体准入标准见 `docs/superpowers/specs/2026-04-28-chat-db-persistence-scope-guide.md`：
    - 条件 A：需要聊天历史（session/message persistence）
    - 条件 B：需要会话级默认知识库
    - 条件 C：需要评测/审计回放（run/tool/citation trace）

