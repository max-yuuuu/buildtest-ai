## Why

当前 Quick Chat 的流式链路已经可以把 assistant 文本、step、citation、tool 等事件送到前端，但默认展示体验仍然偏“调试输出”而不是“聊天阅读”：

- assistant 正文没有作为第一优先级内容呈现
- `data-step`、`data-citation`、`tool-*` 等内部结构会以原始 JSON 形式进入消息区
- 代码块和 Mermaid 图没有针对流式 markdown 做专门的阅读体验优化

这导致页面看起来更像日志面板，而不是类似 ChatGPT / DeepSeek 的主流聊天界面。

## What Changes

- 为 Quick Chat 引入基于 `streamdown` 的 assistant 正文流式 markdown 渲染。
- 增强代码块流式展示体验，并支持 Mermaid fenced block 渲染。
- 将 `data-step` 转换为轻量状态提示，而不是直接展示原始 JSON。
- 将 citation 从正文中抽离为独立来源区。
- 默认隐藏 raw tool payload、raw step payload 与其他底层协议元数据。
- 在前端引入 `UIMessage.parts -> view model` 的展示层归一化逻辑，并围绕它补充测试。

## Capabilities

### New Capabilities

- `chat-streaming-markdown-rendering`: assistant 消息正文以流式 markdown 形式展示。
- `chat-code-and-mermaid-rendering`: 代码块增强与 Mermaid fenced block 支持。
- `chat-message-presentation-model`: 将 `UIMessage.parts` 归一化为展示层 view model。
- `chat-lightweight-status-and-sources`: 将 step 转为轻量状态，将 citation 转为独立来源区。

### Modified Capabilities

- `quick-chat-ui`: 从直接渲染 raw parts 改为按正文、状态、来源分层渲染。
- `chat-default-reading-view`: 保持协议不变，但默认阅读视图不再直接展示 raw tool/raw step/raw citation JSON。

## Impact

- Affected code:
  - `frontend/app/(dashboard)/chat/page.tsx`
  - `frontend/components/chat/*`（新增或重构）
  - `frontend/lib/chat-message-view-model.ts`（新增）
  - `frontend/tests/unit/chat-page.test.tsx`
  - 相关前端测试文件
- Affected APIs:
  - **无后端 API / 协议变更**
  - 仍沿用当前 `/api/chat` 与 UIMessage parts 输入
- Dependencies:
  - 前端新增 `streamdown`
  - 前端新增 `@streamdown/code`
  - 前端新增 `@streamdown/mermaid`
- Database:
  - 无数据库变更
