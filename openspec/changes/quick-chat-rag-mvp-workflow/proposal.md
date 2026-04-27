## Why

当前项目已具备文档切分与入库能力，但缺少面向用户可稳定交付的读取链路（query-time RAG chat）。需要先落地一条最小可用、可观测、可评测的 Quick Chat 流程，为后续智能体 chat、数据定制 chat 及工具编排提供统一基础。

## What Changes

- 新增 Quick Chat MVP 工作流：`normalize -> retrieve -> context -> generate(stream) -> citations -> done`。
- 采用单一向量检索策略（MVP 仅 vector retrieval），并支持“检索为空时一次 query rewrite 重试”。
- 新增统一 Tool Registry 契约，并在 Quick Chat 中仅启用被动工具 `api_retrieve`。
- 新增 chat 流式事件与前端 AI SDK 映射对齐的执行约束，复用 `docs/active/ai-sdk-stream-mapping.md` 定义。
- 统一模式入口：`mode=quick|agent|data`，MVP 仅放开 `quick`，其余模式保留接口占位与标准错误返回。
- 明确后续扩展点：`mcp`、`skill`、`cli`、LangFlow/工具路由节点，以不破坏 Quick Chat 主链路为前提渐进启用。

## Capabilities

### New Capabilities

- `quick-chat-workflow`: 定义 Quick Chat 的最小 LangGraph 链路、输入输出契约、流式事件与降级策略。
- `tool-registry-contract`: 定义统一工具注册/调用接口，覆盖 `api/mcp/skill/cli` 分类与 Quick 模式启用策略。
- `chat-mode-routing`: 定义统一 chat 模式路由契约与占位模式的行为边界（quick/agent/data）。

### Modified Capabilities

- `retrieval-lineage-contract`: 补充 query 阶段链路事件与引用映射要求，确保回答可追溯到检索命中。
- `pgvector-native-retrieval`: 补充 Quick Chat 的查询时检索参数约束与空结果重试行为（单次 rewrite）。

## Impact

- Affected code:
  - `backend/app/services/*`（新增/调整 quick chat workflow orchestration）
  - `backend/app/api/v1/*`（新增 chat mode 路由与流式接口约束）
  - `frontend/app/api/backend/[...path]/route.ts` 或 `frontend/app/api/chat/route.ts`（流式适配）
  - `frontend` chat UI（渲染 `text` + `data-*` parts）
- Affected APIs:
  - chat 流接口请求体新增/统一 `mode`
  - SSE 事件格式遵循 `start/token/citation/step/error/done`
- Dependencies:
  - 后端 LangChain + LangGraph
  - 前端 `@ai-sdk/react`（可选 `@ai-sdk/langchain` 仅用于 TS 侧适配场景）
- Systems:
  - 评测与可观测链路新增 query-time 节点数据（attempt、latency、citation mapping）
