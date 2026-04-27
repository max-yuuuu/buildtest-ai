# Quick Chat MVP 运行说明

## 行为概览

当前 MVP 仅开放 `mode=quick`，请求入口：

- 同步响应：`POST /api/v1/chat`
- 流式响应：`POST /api/v1/chat/stream`

请求体最小示例：

```json
{
  "mode": "quick",
  "message": "如何配置 embedding 模型？",
  "knowledge_base_id": "<kb_uuid>"
}
```

`mode=agent|data` 在 MVP 阶段返回 `MODE_NOT_IMPLEMENTED`。

## Quick 链路

后端固定执行以下流程：

1. `NormalizeQueryNode`：轻量规范化 query（压缩空白字符）
2. `ToolCallNode(api_retrieve)`：首轮检索
3. 空结果时进行一次 rewrite 并二次检索（最多重试一次）
4. `AssembleContextNode`：组装上下文与 citation
5. `GenerateAnswerNode`：生成回答
6. `FinalizeNode`：输出 attempts / citation mapping

## 可追溯字段

`/api/v1/chat` 响应包含：

- `attempts`：每轮检索的 `attempt/query/hit_count/latency_ms`
- `citation_mappings`：`citation_id` 到检索命中（`knowledge_base_id/document_id/chunk_index/score`）的映射

`/api/v1/chat/stream` 的 `done` 事件同样包含 `attempts` 与 `citation_mappings`，用于评测与回放。

## SSE 事件

流式接口遵循：

- `start`
- `step`
- `token`
- `citation`
- `error`
- `done`

成功链路保证 `done` 恰好一次；错误链路发出 `error` 并终止，不再发送 `done`。

## 当前限制

- 仅支持 `quick`，`agent/data` 仍为占位
- 仅支持 `api_retrieve`（quick allowlist）
- rewrite 为单次轻量规则，不做复杂语义改写
- `token` 为服务端分词后的增量片段，非模型原生 token

## 扩展位

- 新增 `mcp/skill/cli` 工具时，优先沿用 Tool Registry 契约与 mode allowlist
- 若替换为真实 LLM 流式生成，保持 `start/token/citation/step/error/done` 事件名与顺序不变
- 前端保持 `text + data-*` 渲染方式，避免协议分叉
