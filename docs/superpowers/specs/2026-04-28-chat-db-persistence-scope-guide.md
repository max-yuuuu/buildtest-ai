# Chat 何时值得引入数据库持久化

## 目的

这份文档用于回答一个边界问题：

> Quick Chat / 多知识库 / AI SDK UI message stream 这条链路，什么时候才值得把数据库持久化纳入 scope？

结论先行：

- **本期不实现数据库持久化**
- 只有当产品目标明确进入“会话”“恢复”“审计”“回放”这些长期状态能力时，才值得把 DB 纳入 scope
- 一旦纳入，就不应该只“补一个字段”，而应按明确的目标能力建模

## 为什么本期不做

当前 MVP 的核心目标是：

- 跑通多知识库请求契约 `knowledge_base_ids[]`
- 跑通 Python 后端领域事件 -> Next BFF -> AI SDK 6 UI message stream
- 支持 text / data / tool 消息渲染
- 保证 host 开发环境与 Docker 开发环境一致

如果现在把 DB 持久化加入 scope，会立即引出新的建模问题：

- 要不要引入 `chat_sessions` / `chat_messages`
- 默认知识库是用户级偏好、会话级状态，还是页面级状态
- tool / citation / step / error 存原始事件、归一化表，还是 UI parts
- 页面刷新恢复的是“消息历史”，还是“当前输入态 + 当前绑定知识库”

这些问题并不是本期 MVP 的主问题。现在引入只会扩大范围，降低主链路落地速度。

因此，本期的正确边界是：

- 默认主知识库：前端本地状态（必要时 `localStorage`）
- `@知识库` 绑定：当前输入与当前请求级别状态
- citation / step / tool / error：只流式展示，不落库

## 什么时候值得把 DB 纳入 scope

只有在以下任一条件成立时，才建议将数据库持久化正式纳入 chat 范围。

### 条件 A：要做聊天历史

如果产品开始要求以下能力：

- 左侧会话列表
- 点击恢复历史聊天
- 页面刷新后还能继续同一会话

那么就必须引入：

- `chat_sessions`
- `chat_messages`

因为这时“聊天”已经不再是一次性请求，而是一个可恢复、可持续追加的状态容器。

#### 最佳实现建议

最合理的建模方向是：

### `chat_sessions`

建议至少包含：

- `id`
- `user_id`
- `mode` (`quick` / `agent` / `data`)
- `title`
- `created_at`
- `updated_at`
- `archived_at`（可选）

### `chat_messages`

建议至少包含：

- `id`
- `session_id`
- `role`
- `sequence_no`
- `content_json`
- `created_at`

其中：

- `content_json` 不建议只存纯文本
- 应存一份**可恢复消息结构**，至少能覆盖：
  - text parts
  - data parts
  - tool-call / tool-result

也就是说，这里更适合存“面向 UI / replay 的消息结构”，而不是只存 LLM 原始字符串。

#### 为什么这是最佳实现

因为聊天历史的本质是“恢复用户看到过的内容”，而不是“重新推导一次后端运行过程”。

如果只存纯文本：

- tool 调用会丢
- citation 来源会丢
- step / error 信息会丢
- UI replay 会失真

所以一旦做历史，消息必须按结构化内容持久化。

---

### 条件 B：要做会话级默认知识库

如果产品开始要求：

- “这个 chat 永久绑定 postgres 知识库作为默认库”
- “以后再打开这个对话，仍然保留默认主知识库 + mention 绑定状态”

那么就不能再只用前端本地状态，必须把默认知识库存到 **session 层**。

#### 最佳实现建议

推荐在 `chat_sessions` 增加：

- `default_knowledge_base_id`（单主知识库）

如果未来会话本身就需要保存一个长期的绑定集合，再考虑：

- `chat_session_knowledge_bases`

但在绝大多数场景下，建议先区分两层语义：

1. **session default KB**
   - 长期默认值
   - 用于“没写 `@KB` 时”的兜底检索范围

2. **message-level mentioned KBs**
   - 当前消息临时覆盖
   - 不必回写 session 默认值

#### 为什么这是最佳实现

因为“默认值”与“本轮显式指定”不是一回事。

如果把它们混在同一层：

- 用户会搞不清“这次 @ 了，是不是永久改默认？”
- 后端也会混淆 session state 和 message intent

所以最佳模型应该是：

```text
session.default_knowledge_base_id
    +
message.mentioned_knowledge_base_ids
```

没有 mention 时走 session default；有 mention 时走 message 级覆盖。

---

### 条件 C：要做评测 / 审计回放

如果产品开始要求：

- 回看某次用户问题对应的 citations / tool results
- 对比不同版本回答
- 做 query-time lineage 审计

那么只保存聊天消息已经不够了，还需要保存**响应链路运行产物**。

#### 最佳实现建议

这里不建议把所有审计信息都塞进 `chat_messages.content_json`，而是分两层：

### 层 1：用户可见消息

存到 `chat_messages.content_json`

用于：

- 会话恢复
- UI replay
- 用户看到的最终内容

### 层 2：运行链路追踪

新增独立表，例如：

- `chat_turn_runs`
- `chat_turn_tool_calls`
- `chat_turn_citations`

建议最少覆盖：

#### `chat_turn_runs`

- `id`
- `session_id`
- `user_message_id`
- `assistant_message_id`
- `mode`
- `request_payload_json`
- `response_summary_json`
- `created_at`

#### `chat_turn_tool_calls`

- `id`
- `run_id`
- `tool_call_id`
- `tool_name`
- `input_json`
- `output_json`
- `status`
- `latency_ms`

#### `chat_turn_citations`

- `id`
- `run_id`
- `knowledge_base_id`
- `document_id`
- `chunk_index`
- `score`
- `citation_json`

#### 为什么这是最佳实现

因为“用户可见消息”和“系统内部审计”服务的是两类完全不同的需求：

- UI replay 关注恢复界面
- 审计/评测 关注可比性、可追溯性、结构化查询

如果把两者混在一个 JSON 大字段里：

- 后期查询困难
- lineage 分析困难
- 对比不同回答版本困难

所以只要进入评测/审计范围，就应该拆出运行表。

## 三种条件对应的最小建模层级

```text
条件 A：聊天历史
  -> chat_sessions + chat_messages

条件 B：会话级默认知识库
  -> 在 chat_sessions 上增加 default_knowledge_base_id

条件 C：评测 / 审计回放
  -> 在 A/B 基础上再增加 run / tool / citation 追踪表
```

也就是说：

- **A 是会话持久化的起点**
- **B 是 session state 的增强**
- **C 是运行追踪与评测闭环**

## 建议的演进顺序

如果未来真的要把 DB 纳入 scope，推荐顺序如下：

1. **先做 A：聊天历史**
   - 先把 session/message 变成稳定基础设施
2. **再做 B：会话级默认知识库**
   - 挂在 session 上，自然且清晰
3. **最后做 C：评测 / 审计回放**
   - 在已有 session/message 基础上补 run-level trace

不要反过来：

- 不要为了“默认主知识库”单独先往 `users` 或其他表塞字段
- 不要在没有 session/message 的前提下直接做 run trace

这两种做法都容易造成模型碎裂。

## 对下一次计划的建议

当下一次计划要评估是否纳入 DB 范围时，可以先问这三个问题：

1. 我们是不是要支持“恢复历史聊天”？
2. 我们是不是要支持“这个 chat 长期绑定默认知识库”？
3. 我们是不是要支持“回放某次回答的 citations / tools / lineage”？

如果三者都不是，**不要加数据库**。

如果只满足 A，做最小 session/message 持久化即可。

如果满足 A + B，增加 session default KB。

如果满足 A + C 或 A + B + C，再设计 run/tool/citation 追踪层。

## 当前结论（供本期引用）

本期 Quick Chat 多知识库 + AI SDK 6 stream MVP：

- **不新增数据库字段**
- **不新增聊天持久化表**
- 默认主知识库采用前端本地偏好保存
- `@知识库` 绑定仅作用于当前输入与当前请求
- tool / citation / step / error 只做流式展示，不做持久化

后续若要把 DB 纳入 scope，应以本文件定义的 A / B / C 条件作为准入标准。

