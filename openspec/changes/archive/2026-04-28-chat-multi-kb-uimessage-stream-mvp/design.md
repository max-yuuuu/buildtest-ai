## Context

本次变更基于 `docs/superpowers/specs/2026-04-28-chat-multi-kb-at-mentions-uimessage-stream.md`，目标是在不引入聊天会话持久化与重型富文本编辑器的前提下，完成以下闭环：

- Quick Chat 支持默认主知识库 + `@知识库` 多知识库绑定
- 后端 Python（LangChain/LangGraph）输出可测试的领域流事件
- Next BFF 将领域事件映射为 `ai@6 latest` 可消费的 UI message stream parts
- 前端 `useChat` 正确展示 text / data / tool 消息
- host 开发环境与 Docker 开发环境对同一链路表现一致

约束：

- 只保留一个新的 chat 请求契约：`knowledge_base_ids[]`
- 不兼容旧 `knowledge_base_id`
- 不做聊天会话持久化，因此本期不引入 DB schema 变更
- 实现必须以本地安装后的 `ai@6 latest` 文档与源码为准，不凭 v5 迁移记忆编码

## Goals / Non-Goals

**Goals**

- 建立单一的多知识库 Quick Chat 请求契约
- 建立 Python→BFF→AI SDK 6 UI 的双段流协议边界
- 将 tool 调用与工具结果纳入一等 UI 输出，并与 `ai@6` 的 tool chunks 对齐
- 明确开发环境与 Docker 开发环境的依赖与 env 一致性

**Non-Goals**

- 不实现聊天历史/会话持久化
- 不实现 tool input delta streaming
- 不实现并发检索或高级 KB 权重策略
- 不引入数据库表或字段，仅在现有 schema 足够时完成 MVP

## Decisions

### Decision 1: 请求契约统一为 `knowledge_base_ids[]`

- 选择：前端发送体与后端 schema 全部切换为 `knowledge_base_ids: list[UUID]`
- 原因：避免双轨兼容逻辑污染整个链路；多知识库是本次变更的核心，不应以临时兼容稀释边界
- 结果：
  - `@KB` 解析结果直接落到请求体
  - 无 `@` 时由默认主知识库兜底形成单元素数组

### Decision 2: 默认主知识库不持久化到数据库

- 选择：默认主知识库只存在于页面/请求层状态，不新增 `chat_sessions` 或其他表字段
- 原因：
  - 当前 spec 非目标明确排除了聊天历史与多会话管理
  - 仅为了“当前页面默认值”引入 DB schema，会扩大 MVP 范围并带来 migration / fixture / env 复杂度
- 风险：
  - 页面刷新后的默认主知识库恢复策略只能依赖前端本地状态或默认列表策略
- 结论：
  - 本期 **无数据库 schema 变更**
  - 若后续要支持会话列表/聊天历史，再单独新增 change 做持久化建模
  - 是否值得将 DB 纳入范围，统一参考 `docs/superpowers/specs/2026-04-28-chat-db-persistence-scope-guide.md`

### Decision 2.1: 数据库持久化的准入标准不是“想记点状态”，而是明确的产品能力

- 选择：只有满足以下任一条件时，后续计划才应引入 DB 持久化：
  - 条件 A：需要聊天历史（左侧会话列表、点击恢复、刷新后继续）
  - 条件 B：需要会话级默认知识库（某个 chat 长期绑定默认 KB）
  - 条件 C：需要评测/审计回放（回看 citations/tool results、版本对比、query-time lineage）
- 原因：
  - 这三类需求分别对应三种不同的数据层级：session/message、session state、run trace
  - 如果在不满足这些条件时提前加表或字段，模型会碎裂，并干扰本期 MVP 主链路
- 结果：
  - 本期默认主知识库仍采用前端本地偏好
  - `@KB` 绑定仍然是 message/request 级状态
  - tool / citation / step / error 仅做流式展示，不做持久化

### Decision 3: Python 后端输出“领域事件”，BFF 才做 AI SDK 6 映射

- 选择：
  - Python backend SSE：`start` / `text-delta` / `citation` / `step` / `tool-call` / `tool-result` / `error` / `done`
  - Next BFF：映射为 `ai@6 latest` 的 UI message stream chunks：
    - `start`
    - `text-start` / `text-delta` / `text-end`
    - `data-*`
    - `tool-input-available`
    - `tool-output-available`
    - `finish`
- 原因：
  - Python 不需要了解 Node 侧 helper API
  - AI SDK 协议升级成本集中在 BFF 层
  - 单元测试更清晰：后端测领域事件，前端/BFF 测协议映射

### Decision 4: 多知识库检索 MVP 采用串行聚合

- 选择：对 `knowledge_base_ids[]` 串行检索，合并 hits，全局排序后生成 context/citation
- 原因：
  - 串行更利于调试事件顺序和错误边界
  - 在开发阶段优先要“正确和可测”，而不是过早并发优化
- 后续可演进：
  - 并发检索
  - 按 KB 分组引用
  - 权重或优先级控制

### Decision 5: tool 消息 MVP 只支持 Python 领域事件 `tool-call` / `tool-result`

- 选择：
  - Python 领域事件只输出 `tool-call` / `tool-result`
  - BFF 将它们映射到 `ai@6` 的 `tool-input-available` / `tool-output-available`
  - 不实现 `tool-input-start/delta` 等更细粒度流式输入
- 原因：
  - 用户最关心的是“调用了哪个工具”和“结果是什么”
  - 输入流式细节对当前 MVP 的价值不足以覆盖复杂度

### Decision 6: host / Docker 开发环境必须共享同一套 chat 开发约束

- 选择：把环境一致性作为显式任务，而不是附属文档
- 必须对齐的内容：
  - 前端依赖版本（尤其 `ai@6 latest`）
  - `BACKEND_URL` 解析策略
  - `env/common.env` / `env/dev.host.env` / `env/dev.docker.env` / `frontend/.env`
  - 启动文档与 Docker compose 的开发模式
- 原因：
  - BFF 流协议与 SSE 在 host/docker 环境最容易出现不同表现
  - 如果环境不对齐，契约测试结论不可信

### Decision 6.1: compose 入口、env 分层与文档引用必须只有一套真相

- 选择：实现阶段若发现 compose 文件、`scripts/dev`、`Makefile`、启动文档之间存在命名或入口漂移，必须统一到当前仓库实际有效的入口
- 最少需要校验并统一：
  - `docker-compose*.yml` 的真实文件名与调用方式
  - `scripts/dev` / `Makefile` 实际使用的 compose 入口
  - `env/common.env`、`env/dev.host.env`、`env/dev.docker.env`、根 `.env`、`frontend/.env(.local)` 各自的消费方
  - `BACKEND_URL` 的优先级与 fallback 行为
- 原因：
  - 当前仓库中已存在“文档引用 compose.base/dev/prod，但实际文件为 docker-compose*.yml”的漂移信号
  - 如果不统一，host 与 Docker 的验证结论不可信

### Decision 6.2: 若 Docker 配置修改，文档与规则必须同步更新

- 选择：只要本次 change 触及 Docker / compose / env 分层，就必须同步检查并更新以下文档：
  - `docs/启动文档/1.启动指南.md`
  - `CLAUDE.md`
  - `AGENTS.md`
- 原因：
  - 这三个文件已经承担“项目运行方式 / 架构约束 / agent 行为边界”的单一事实源角色
  - Docker 配置变了但规则文档没变，会让后续实现与协作持续建立在旧假设上
- 结果：
  - Docker 相关改动不允许只改 compose 文件本身
  - 必须把运行说明与规则说明一并对齐

## Architecture Sketch

```text
Browser (useChat + chat UI)
    |
    | UI message stream parts
    v
Next BFF /api/chat
    |
    | map domain SSE -> ai@6 UI stream parts
    v
Python backend /api/v1/chat/stream
    |
    | domain SSE events
    v
ChatService.stream
    |
    v
RunQuickChatUseCase.execute(knowledge_base_ids[], message)
    |
    +--> retrieve KB A
    +--> retrieve KB B
    +--> merge / rank / trim hits
    +--> emit tool-call / tool-result / citation / step
    +--> generate answer text-delta
```

## Environment Parity Plan

为保证开发阶段 host 与 Docker 表现一致，计划要求：

1. 只维护一套明确的 chat 依赖目标版本（`ai@6 latest`）
2. host 与 Docker 开发环境都通过同一请求入口 `/api/chat`
3. host 与 Docker 下的 BFF 都能解析到正确 backend 地址
4. 启动文档明确：
   - host 开发如何启动 frontend/backend
   - Docker 开发如何启动 compose
   - 两种模式下如何验证 chat 流式链路
5. 若 `env` 文件存在重复或冲突定义，在实现前先统一语义，再编码

## Risks / Trade-offs

- [风险] `ai@6 latest` 实际协议与当前认知不一致  
  -> Mitigation: 计划第一步先安装并读取本地文档/源码，确认 helper API 和 part 结构后再改代码

- [风险] `@KB` mention UI 和请求解析不同步  
  -> Mitigation: 提取独立解析函数并补单测；UI 只消费解析结果，不在多个位置重复推导

- [风险] 多知识库串行检索导致时延上升  
  -> Mitigation: MVP 接受；先保证正确性，后续再优化并发

- [风险] host 与 Docker backend 地址发现逻辑不一致  
  -> Mitigation: 将地址解析与 env 约束纳入实现任务和验证任务

## Migration / Rollout Plan

1. 确认 `ai@6 latest` 本地协议与依赖要求  
2. 后端 schema / quick chat workflow / 领域事件重构  
3. BFF 映射到 AI SDK 6 UI stream  
4. 前端 `@KB` UI 与新 parts 渲染  
5. 统一 compose / env / 文档入口真相  
6. 补充测试  
7. 验证 host 与 Docker 两种开发模式

Rollback:

- 若新链路不稳定，整体回滚整个 change，不保留中间兼容层
- 因本期不涉及数据库 migration，回滚成本主要在代码与依赖层

