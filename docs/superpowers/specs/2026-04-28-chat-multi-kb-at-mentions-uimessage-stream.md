# Chat 多知识库 @ 绑定 + AI SDK 6 UIMessageStream 传输协议

## 背景与目标

当前 Quick Chat：

- 前端使用 `@ai-sdk/react` 的 `useChat`，UI 以 `UIMessage.parts` 渲染。
- Next Route `frontend/app/api/chat/route.ts` 作为 BFF，将后端 SSE 事件映射为前端可消费的 “parts”。
- 后端 `ChatRequest` 仅支持单知识库：`knowledge_base_id`。

本变更目标：

1. **每个 chat 必须有默认主知识库**（用户进入即可直接提问）。
2. 支持在发送框中通过 **`@知识库`** 绑定多个知识库作为**本轮请求**检索范围（Notion AI 风格）。
3. 将前后端的流式传输对齐到 **AI SDK 6 latest 的 UI message streams**，以前端 `useChat` 的最新协议为准。
4. 支持 **tool 消息**，让前端能够在同一条 assistant message 下渲染工具调用与工具结果。

非目标：

- 不引入重型富文本编辑器（先用轻量文本输入 + mention 弹层实现）。
- 不在本次引入“多会话管理/历史会话列表”等新能力（保持在现有 Quick Chat 页面内演进）。

## UX 需求（Notion AI 风格）

### 信息架构

页面拆分为三段：

1. **顶部上下文栏**
   - 标题 + 简短说明
   - 右侧：主知识库选择器（单选）
   - 下方提示：
     - 默认：展示“默认知识库：{主知识库名}”
     - 当本轮输入中存在 `@KB` 时：展示“本轮将检索 N 个知识库”
2. **消息区**
   - 类似 Notion 的克制气泡：轻边框/浅背景（跟随项目主题色 token）
   - 仍需展示 data 部分：citation/step/error（可保持现有 `pre` 风格，后续可迭代折叠）
3. **底部输入区**
   - 贴底大圆角输入容器
   - 支持 `@` 触发知识库选择弹层
   - 输入框下方展示已绑定的 KB pills（可删除）

### 默认主知识库与 @ 覆盖规则

我们采用 “主知识库默认 + `@` 本轮覆盖/追加”：

- **没有任何 `@KB`**：本轮请求使用 `knowledge_base_ids=[defaultKbId]`
- **存在一个或多个 `@KB`**：本轮请求使用 `knowledge_base_ids=[...mentionedKbIds]`，忽略主知识库（主知识库仅作为默认兜底，不被本轮自动加入）

### Mention 交互（键盘优先）

- 输入 `@` 打开候选面板；`@` 后输入用于过滤。
- 键盘：
  - `ArrowUp/ArrowDown` 移动高亮项
  - `Enter` 选中并插入
  - `Esc` 关闭面板
- 删除：
  - 删除文本中的 `@KB` → pills 同步移除
  - 点击 pill “×” → 文本中的 `@KB` 同步移除（如果实现成本高，可先只做 pill 删除，不强制回写文本；但最终体验应双向同步）

### 可用性细节

- 主知识库未选择：禁止发送，placeholder 提示“请先选择上方知识库”。
- KB 重名：候选列表中增加辅助信息（例如 KB id 的短后缀或向量库/文档数），避免误选。

## API & 数据契约

### 前端发送体（目标契约）

将目前的单 `knowledge_base_id` 升级为多选：

```json
{
  "mode": "quick",
  "message": "用户问题文本（去掉 @KB mention 后）",
  "knowledge_base_ids": ["uuid-1", "uuid-2"]
}
```

约束：

- `knowledge_base_ids` 至少 1 个（由主知识库兜底保证）。
- `message` 为最终用于检索/回答生成的 query（不包含 UI mention token 文本）。

### 后端 schema（目标契约）

`backend/app/schemas/chat.py`：

- 将 `knowledge_base_id: UUID` 改为 `knowledge_base_ids: list[UUID]`。
- 不保留 `knowledge_base_id` 兼容分支，前后端、BFF、测试一次性统一到 `knowledge_base_ids`。

### Quick Chat 多知识库检索策略（MVP）

后端 quick chat 使用多 KB 合并检索：

1. 对每个 `knowledge_base_id` 运行一次 retrieve（MVP 先串行，后续再并发优化）
2. 合并 hits
3. 全局按 score 降序排序
4. 截断 top N（N 由现有检索策略决定）
5. 组装 context + citations，citation 中必须保留 `knowledge_base_id`，便于前端标识来源

当单个 KB 失败：

- 不中断整体：产生一个 error/step 事件标注该 KB 失败，其余 KB 继续。

## 后端流式事件模型（Python 侧）

后端不直接实现 Node 侧的 AI SDK adapter，而是输出稳定的**领域事件流**，由 Next BFF 负责映射到 AI SDK 6 UI message streams。

### 事件类型

MVP 统一支持以下领域事件：

- **文本**
  - `start`
  - `text-delta`
  - `done`
- **数据**
  - `citation`
  - `step`
  - `error`
  - `status`
- **工具**
  - `tool-call`
  - `tool-result`

说明：

- `tool-input-start` / `tool-input-delta` / `tool-input-end` 不是 Python 领域事件的 MVP 必需项；后续若 LangGraph 需要更细粒度输入流再补充。
- `message_id` 必须由后端在一轮 assistant 回复内保持稳定，保证 BFF 可以正确映射成单条 assistant message。

### 事件结构要求

#### 文本

```json
{ "type": "start", "message_id": "msg_xxx" }
```

```json
{ "type": "text-delta", "message_id": "msg_xxx", "delta": "..." }
```

```json
{ "type": "done", "message_id": "msg_xxx" }
```

#### 数据

```json
{
  "type": "citation",
  "message_id": "msg_xxx",
  "knowledge_base_id": "kb_xxx",
  "document_id": "doc_xxx",
  "chunk_index": 1,
  "score": 0.92,
  "source": {}
}
```

```json
{
  "type": "step",
  "message_id": "msg_xxx",
  "step_kind": "retrieve",
  "knowledge_base_id": "kb_xxx",
  "attempt": 1,
  "query": "什么是 pgvector"
}
```

```json
{
  "type": "error",
  "message_id": "msg_xxx",
  "scope": "knowledge_base",
  "knowledge_base_id": "kb_xxx",
  "code": "RETRIEVE_FAILED",
  "message": "..."
}
```

#### 工具

```json
{
  "type": "tool-call",
  "message_id": "msg_xxx",
  "tool_call_id": "tool_xxx",
  "tool_name": "retrieve_knowledge",
  "input": {
    "knowledge_base_ids": ["kb1", "kb2"],
    "query": "什么是 pgvector"
  }
}
```

```json
{
  "type": "tool-result",
  "message_id": "msg_xxx",
  "tool_call_id": "tool_xxx",
  "tool_name": "retrieve_knowledge",
  "output": {
    "hit_count": 4,
    "knowledge_base_ids": ["kb1", "kb2"]
  }
}
```

## AI SDK 6 UIMessageStream 传输协议（对齐要求）

### 版本目标与来源

本项目的目标版本为 **`ai@6 latest`**。

当前 spec 参考了此前 AI SDK 迁移文档里已经明确的方向：

- LangChain adapter 独立到 `@ai-sdk/langchain`
- UI 层使用 **UI message streams**
- streaming part 采用带 `id` 的生命周期模式，而不是旧式单块 data stream

但本次实现**不以 v5 迁移文档字段为最终准则**；最终 wire part 字段与 helper API 必须以 `ai@6 latest` 安装后的本地文档/源码为准。

### 我们的约束与落地路径

本项目后端是 Python（LangChain / LangGraph），无法直接使用 `@ai-sdk/langchain`。

因此我们需要定义 **Python → Next BFF → AI SDK UI** 的 wire format，使得 `useChat` 可以直接消费，并且未来（如果引入 Node adapter 或复用官方工具）不需要再次推翻协议。

### 目标：对齐 `ai@6` 的 UI message stream chunks

我们将后端领域事件映射到 `ai@6` 的 UI message stream chunks：

- **Message lifecycle**
  - `start` → 映射为 `start`
  - `done` → 映射为 `finish`
- **Text**
  - `start` + `text-delta` + `done` 之间的文本内容 → 映射为 `text-start` / `text-delta` / `text-end`
- **自定义数据（citation/step/error）**
  - 使用 UI message streams 中的 `data-*` chunks 表达（保持结构化 JSON）
  - 这些 `data-*` chunks 将成为 `UIMessage.parts` 中的非文本部分（前端以 `type === "data-..."` 渲染）
- **Tool**
  - Python `tool-call` → 映射为 `tool-input-available`
  - Python `tool-result` → 映射为 `tool-output-available`
  - `tool_call_id` 必须在调用与结果之间保持一致，便于前端在同一 tool invocation 下展示状态与结果
- **状态**
  - 若需要额外状态展示，可补充 `data-status`，但不替代 `start` / `finish`

重要约束：

- 同一条 assistant message 的流式输出必须具备稳定的 `messageId` / text chunk `id` / `toolCallId`，避免重复消息与错位。
- BFF 只做协议映射，不做业务推断；知识库聚合、工具调用、错误范围判断都在 Python 后端完成。

### Wire 选择（SSE vs NDJSON）

保持现有 BFF `text/event-stream`（SSE），因为：

- 现有 `/api/chat` 已是 SSE，改动最小
- `useChat` 已可消费流式响应

协议细节：

- **Python 后端 → Next BFF**：每个 SSE `data:` payload 为一个 JSON 领域事件（如 `text-delta` / `citation` / `tool-call`）
- **Next BFF → 浏览器**：每个 SSE `data:` payload 为一个 JSON UI message stream chunk
- UI chunk 需要包含 `type` 与必要字段（例如 `messageId`、`id`、`delta`、`toolCallId` 等）

实现前置条件：

- 前端安装 `ai@6 latest`
- 根据 `ai@6 latest` 的本地 `node_modules/ai/docs` 与相关包源码，确认：
  - `useChat` 当前依赖的响应协议
  - tool chunks 的精确结构
  - `start` / `finish` / 文本 / data / tool chunk 的字段命名

> 注：具体 part 字段名需以项目中实际使用的 `@ai-sdk/react`/`ai` 版本为准；实现阶段必须从本地依赖的 `node_modules` 文档/源码校验（避免凭记忆实现）。

## 测试需求

### 前端

1. `@` mention 解析：从输入文本提取 mentioned KB ids，并生成清洗后的 message
2. 无 `@` 时自动使用默认主 KB
3. 有多个 `@` 时请求体包含 `knowledge_base_ids`
4. 删除 mention/pill 后绑定列表同步变化
5. 候选面板键盘导航可用

### 后端

1. schema 支持 `knowledge_base_ids`
2. 多 KB 检索合并排序正确
3. citation 输出包含来源 KB
4. 单 KB 失败不阻断整体流式输出

### 协议/契约

1. `/api/chat` 输出符合 `ai@6` UI message stream chunk 约定（`start` / `text-*` / `data-*` / `tool-*` / `finish`）
2. 前端 `useChat` 渲染不出现重复 assistant message（需要稳定 id 与结束信号）
3. Python `tool-call` 与 `tool-result` 在前端能按同一 `toolCallId` 正确配对

## 发布/兼容策略（建议）

阶段 1（MVP）：

- UI：主 KB + `@KB` 多选 + pills
- 后端：多 KB 检索合并 + citation 来源
- 流：将 Python 领域事件映射为 `ai@6` UI message stream chunks（满足 `useChat`）
- tool：Python 侧支持 `tool-call` + `tool-result`，BFF 映射为 `tool-input-available` + `tool-output-available`

阶段 2（增强）：

- 并发检索、KB 权重、按 KB 分组引用展示
- 输入体验（更接近 Notion 的 inline token）
- tool input 的 start/delta/end streaming

