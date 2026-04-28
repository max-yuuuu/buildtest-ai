## Context

当前仓库已经有 `chat-multi-kb-uimessage-stream-mvp` 负责：

- 多知识库 Quick Chat 请求契约
- Python -> BFF -> AI SDK UIMessage stream 对齐
- tool / data / citation 等 parts 输送到前端

本 change 不再修改这些协议层能力，而是只处理“这些 parts 应该如何被用户阅读”。

目标是在不重写后端事件模型、不引入调试侧栏、不扩大会话持久化范围的前提下，把 `/chat` 页改造成更接近主流聊天产品的阅读体验。

## Goals / Non-Goals

**Goals**

- assistant 正文作为默认主内容展示
- markdown 以流式方式渲染
- 代码块与 Mermaid 图具备稳定、可读、可降级的体验
- step 转换为轻量状态提示
- citation 进入独立来源区
- raw tool / raw step / raw citation JSON 默认隐藏

**Non-Goals**

- 不重构 `/api/chat` 协议
- 不修改后端 SSE 事件模型
- 不实现完整调试面板
- 不实现聊天历史或消息持久化
- 不实现 citation deep-link 到源文档

## Decisions

### Decision 1: 展示层引入 view model，而不是在 `page.tsx` 直接解释 `parts`

- 选择：新增一层 `UIMessage.parts -> ChatMessageViewModel` 的归一化逻辑
- 原因：
  - 当前问题本质是“协议对象直接进入 UI”
  - 如果仍在 `page.tsx` 直接遍历 `parts` 处理条件分支，页面会继续膨胀
  - 归一化后，渲染逻辑、协议逻辑和测试边界都会更清晰
- 结果：
  - `page.tsx` 只负责编排
  - 消息展示决策由独立模块承担

建议 view model 形状：

```ts
type CitationView = {
  id?: string;
  title?: string | null;
  knowledgeBaseId?: string | null;
  snippet?: string | null;
  score?: number | null;
};

type ChatMessageViewModel = {
  id: string;
  role: "user" | "assistant" | string;
  markdownText: string;
  statusText: string | null;
  citations: CitationView[];
  errorText: string | null;
};
```

### Decision 2: `streamdown` 只负责 assistant 正文，不负责整个 chat 页面

- 选择：`streamdown` 仅集成到 assistant 正文渲染组件
- 原因：
  - 当前问题一半是 markdown 渲染，一半是 parts 信息分层
  - 如果把整个消息系统都交给 `streamdown`，会模糊 citation/status/tool 的 UI 边界
- 结果：
  - 正文：`streamdown`
  - 状态：普通 React UI
  - 来源：普通 React UI
  - 输入区与整体布局：保持现有组件体系

### Decision 3: 默认阅读视图只保留“正文 + 轻状态 + 来源”

- 选择：assistant 消息默认只展示三层：
  - 正文
  - 轻量状态
  - 来源区
- 原因：
  - 用户首要目标是“读回答”
  - 当前 raw JSON 最大的问题是打断阅读主线
- 结果：
  - `tool-*` 不进入默认消息正文
  - `data-step` 不直接渲染 JSON
  - `data-citation` 不直接渲染 JSON

### Decision 4: `data-step` 只做语义压缩，不做详细过程展示

- 选择：将 step 映射成短文案，而不是完整 step timeline
- 推荐语义：
  - retrieve running -> `正在检索知识库...`
  - retrieve completed and answer not visible yet -> `已检索到相关内容，正在生成回答...`
  - answer already streaming -> 隐藏或弱化状态
- 字段约束：
  - 归一化层优先从 `data-step` 中读取能稳定表达阶段与状态的字段
  - 第一优先级为 `step_kind` + `status`
  - 若 `step_kind` 缺失，则允许回退到 `name` + `status`
  - 若阶段字段缺失或无法识别，则不生成状态文案，而不是猜测性显示错误状态
- 原因：
  - 当前 change 明确不是调试能力建设
  - 轻量状态足以保留“系统正在工作”的感知

### Decision 5: citation 独立成来源区

- 选择：将 `data-citation` 抽离为来源区，位于正文下方
- 形式：
  - 可折叠或紧凑展示
  - 每条来源支持标题、知识库 badge、可选 snippet
- 原因：
  - citation 属于阅读辅助信息，不应与正文并列竞争注意力
  - JSON dump 无法承担“来源”语义
- 结果：
  - 没有 snippet 时也必须能渲染最小来源卡片

### Decision 6: Mermaid 必须有强制降级路径

- 选择：仅为 fenced `mermaid` block 启用 Mermaid 渲染
- 失败时：
  - 回退为普通代码块
  - 不能中断整条 assistant 消息渲染
- 原因：
  - Mermaid 是增强功能，不应成为消息稳定性的单点故障

### Decision 7: 错误转成友好消息卡片，而不是 JSON

- 选择：`data-error` 渲染为次级错误提示卡片
- 原因：
  - 用户应该知道发生了什么，但不应被底层 payload 淹没
- 结果：
  - 若已有正文流出，保留正文，只附加错误提示

## Architecture Sketch

```text
useChat() -> messages: UIMessage[]
          |
          v
normalizeChatMessage(message)
          |
          +--> markdownText
          +--> statusText
          +--> citations[]
          +--> errorText
          |
          v
ChatMessageBubble
    |
    +--> UserBubble
    |
    +--> AssistantBubble
          |
          +--> ChatStatusLine
          +--> AssistantMarkdownMessage (streamdown)
          +--> ChatCitationList
          +--> ErrorCard
```

## File Boundary Recommendation

- `frontend/app/(dashboard)/chat/page.tsx`
  - 负责 `useChat`、页面布局、消息列表与输入区
- `frontend/lib/chat-message-view-model.ts`
  - 负责消息归一化
- `frontend/components/chat/assistant-markdown-message.tsx`
  - 负责 `streamdown` assistant 正文渲染
- `frontend/components/chat/chat-status-line.tsx`
  - 负责轻量状态
- `frontend/components/chat/chat-citation-list.tsx`
  - 负责来源区

可接受偏差：

- 若实现规模较小，可先新增 2-3 个组件而不是完全拆满
- 但必须满足“页面主文件不再直接承担全部协议解释逻辑”

## Dependency Plan

新增前端依赖：

- `streamdown`
- `@streamdown/code`
- `@streamdown/mermaid`

接入约束：

- 不替换当前 `useChat`
- 不替换当前 `/api/chat`
- 不引入额外 markdown 协议转换层
- 只在 assistant 正文组件中接入

## Testing Plan

### View Model Tests

需要覆盖：

- assistant `text` parts 被聚合为 `markdownText`
- `data-step` 被压缩为 `statusText`
- `data-citation` 被提取为 `citations[]`
- `tool-*` 不进入默认正文展示数据

### UI Tests

需要覆盖：

- assistant 正文可见
- raw citation JSON 不再直接显示
- raw tool 输出默认不可见
- 轻量状态文案会出现
- 错误卡片取代 raw error JSON

### Resilience Tests

需要覆盖：

- Mermaid 渲染失败时降级为普通代码块
- 辅助数据缺失或异常时不导致消息整体崩溃

## Risks / Trade-offs

- [风险] `streamdown` 在当前 React / Next 版本下存在兼容细节
  -> Mitigation: 依赖接入后先以最小组件隔离集成，再扩展到页面使用

- [风险] 当前测试依赖 raw JSON 文案
  -> Mitigation: 测试迁移到 view model 和用户可见行为断言

- [风险] Mermaid 在流式未闭合阶段渲染不稳定
  -> Mitigation: 允许仅在可安全识别时渲染，否则退回普通代码块

## Migration / Rollout Plan

1. 安装 `streamdown` 相关依赖
2. 引入消息归一化层
3. 提取 assistant 正文 / 状态 / 来源组件
4. 接入 markdown、代码块、Mermaid 渲染
5. 隐藏 raw tool / raw step / raw citation JSON
6. 更新前端测试

Rollback:

- 若 `streamdown` 集成不稳定，可整体回退该展示 change
- 因不涉及数据库和协议变更，回滚成本主要在前端代码与依赖层
