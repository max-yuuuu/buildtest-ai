## 1. API 与模式路由

- [x] 1.1 为 chat 接口增加 `mode=quick|agent|data` 请求校验与默认值（缺省为 `quick`）
- [x] 1.2 在后端路由层实现模式分发，`agent/data` 返回 `MODE_NOT_IMPLEMENTED`
- [x] 1.3 为模式路由补充单元测试（默认 quick、agent/data 占位错误）

## 2. Quick Chat LangGraph MVP 链路

- [x] 2.1 实现 `NormalizeQueryNode`（轻量规范化，不引入复杂重写）
- [x] 2.2 实现 `ToolCallNode` 并接入 `api_retrieve`（首轮检索）
- [x] 2.3 实现“空结果单次 rewrite 重试”分支与 attempt 元数据记录
- [x] 2.4 实现 `AssembleContextNode`（包含 citation 映射）
- [x] 2.5 实现 `GenerateAnswerNode` 流式输出与 `FinalizeNode`

## 3. Tool Registry 统一契约

- [x] 3.1 定义统一 Tool Contract（`tool_id/category/input/result/latency/trace_meta`）
- [x] 3.2 实现 Tool Registry 注册与调用机制（最小版本）
- [x] 3.3 注册 `api_retrieve` 工具并配置 quick 模式 allowlist
- [x] 3.4 对非 allowlist 工具调用返回确定性错误并补充测试

## 4. 流式协议与前端适配

- [x] 4.1 后端按契约发出 `start/token/citation/step/error/done` 事件
- [x] 4.2 BFF 将后端 SSE 事件映射为 AI SDK 可消费流（`text` + `data-*`）
- [x] 4.3 前端 `@ai-sdk/react` 渲染 `data-citation/data-step/data-error`
- [x] 4.4 增加流协议契约测试（事件顺序、done 唯一性、错误终止）

## 5. 可观测性与评测闭环

- [x] 5.1 记录检索 attempt、rewrite 前后 query、hit_count、latency
- [x] 5.2 记录 citation 与 retrieval hit 的可追溯映射
- [x] 5.3 为关键路径添加集成测试（命中、重试命中、重试后仍空、工具异常）
- [x] 5.4 更新文档与运行说明（Quick Chat MVP 行为、限制、扩展位）
