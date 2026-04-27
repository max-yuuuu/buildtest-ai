# AI SDK Stream Mapping (v1)

本文档定义 BuildTest AI 在 **Python LangChain/LangGraph 后端** 与 **`@ai-sdk/react` 前端**之间的流式协议映射规范。

目标：

- 保持后端工作流控制权在 Python 侧
- 前端使用 AI SDK 标准消息渲染，减少自定义状态管理
- 为后续评测与可观测性提供稳定事件契约

## 1. 范围与原则

v1 只覆盖聊天主链路：

1. 请求进入工作流
2. 检索与上下文构建
3. LLM 流式生成
4. 引用与步骤状态回传
5. 结束与错误处理

设计原则：

- **单一状态机**：业务状态机仅在后端（LangGraph）维护
- **前端轻逻辑**：前端仅做展示与交互，不承载业务编排
- **协议稳定**：事件类型固定，字段逐步向后兼容扩展

## 2. 总体架构

```text
@ai-sdk/react(useChat)
          |
          v
frontend/app/api/chat/route.ts  (BFF adapter)
          |
          v
backend FastAPI (LangGraph workflow)
          |
          v
SSE events (start/token/citation/step/error/done)
```

说明：

- Python 后端输出统一 SSE 事件
- BFF 将 SSE 事件映射为 AI SDK 可消费的数据流
- 前端通过 `useChat` 渲染 `text` 与 `data-*` parts

## 3. 后端 SSE 事件规范（Python -> BFF）

后端事件类型固定为 6 类：

- `start`
- `token`
- `citation`
- `step`
- `error`
- `done`

### 3.1 通用字段

建议所有事件包含：

- `type`: 事件类型
- `ts`: 事件时间戳（ISO8601）
- `trace_id`: 链路追踪标识（同一次回答保持一致）

### 3.2 各事件字段

#### start

```json
{
  "type": "start",
  "ts": "2026-04-27T11:00:00.000Z",
  "trace_id": "trc_xxx",
  "run_id": "run_xxx"
}
```

#### token

```json
{
  "type": "token",
  "ts": "2026-04-27T11:00:00.100Z",
  "trace_id": "trc_xxx",
  "text": "这是增量内容"
}
```

#### citation

```json
{
  "type": "citation",
  "ts": "2026-04-27T11:00:00.200Z",
  "trace_id": "trc_xxx",
  "id": "cit_1",
  "doc_id": "doc_123",
  "chunk_id": "chk_45",
  "title": "设计文档",
  "snippet": "与问题相关的片段",
  "score": 0.87
}
```

#### step

```json
{
  "type": "step",
  "ts": "2026-04-27T11:00:00.050Z",
  "trace_id": "trc_xxx",
  "id": "step_retrieve_1",
  "name": "retrieve",
  "status": "running"
}
```

`status` 建议枚举：`running | completed | failed`

#### error

```json
{
  "type": "error",
  "ts": "2026-04-27T11:00:01.000Z",
  "trace_id": "trc_xxx",
  "code": "MODEL_TIMEOUT",
  "message": "模型响应超时",
  "retryable": true
}
```

#### done

```json
{
  "type": "done",
  "ts": "2026-04-27T11:00:01.100Z",
  "trace_id": "trc_xxx",
  "latency_ms": 1100,
  "prompt_tokens": 523,
  "completion_tokens": 314,
  "total_tokens": 837
}
```

## 4. BFF 映射规范（SSE -> AI SDK UIMessage）

实现位置建议：`frontend/app/api/chat/route.ts`

映射规则：

- `start` -> 初始化 assistant 消息上下文（可发 `data-status`）
- `token` -> assistant `text` 增量 part
- `citation` -> `data-citation`（建议包含 `id`，用于持久渲染）
- `step` -> `data-step`（建议包含 `id`，用于过程可视化）
- `error` -> `data-error`，并终止流
- `done` -> `data-status`（`complete`）并关闭流

### 4.1 `data-*` 类型约定

- `data-citation`
- `data-step`
- `data-status`
- `data-error`

命名与 payload 结构应保持稳定，避免 UI 解析分叉。

## 5. 前端渲染约定（`@ai-sdk/react`）

`useChat` 侧建议行为：

- 渲染 `text` 作为主回答
- 渲染 `data-citation` 为引用区（右侧面板或消息折叠）
- 渲染 `data-step` 为过程状态（检索中/生成中）
- 渲染 `data-error` 为错误提示（消息内 + toast）

事件持久化建议：

- 带 `id` 的 `data-*` 作为持久 part 渲染
- 无 `id` 事件仅走 `onData` 瞬态处理

## 6. 最小实现里程碑

### M1（可聊天）

- 打通 `token + done`
- 前端可稳定流式展示文本

### M2（可追溯）

- 增加 `citation`
- 前端展示引用并可跳转到文档片段

### M3（可观测）

- 增加 `step`
- 前端展示 workflow 进度状态

### M4（稳健性）

- 增加 `error` 分类与重试提示
- 完成异常链路验证

## 7. 验收检查清单

- 同一请求 `trace_id` 在所有事件中一致
- `token` 顺序无乱序拼接
- `done` 必达（成功链路）且只出现一次
- `error` 出现时流正确终止
- `citation` 与回答内容可关联验证
- 前端 `useChat` 无需自定义复杂流解析器

## 8. 非目标（v1 不做）

- 多 Agent 并行流合并
- 多模态（图片/音频）消息 part 规范
- 完整工具调用可视化面板
- 复杂人机中断恢复协议

---

后续若将部分编排迁移到 TypeScript（LangGraph.js），本规范仍可作为跨实现协议基线，保持 UI 与评测侧稳定。
