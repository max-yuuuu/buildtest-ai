## 1. 依赖与集成边界

- [x] 1.1 在前端安装 `streamdown`、`@streamdown/code`、`@streamdown/mermaid`
- [x] 1.2 确认这些依赖与当前 Next / React / 测试环境兼容
- [x] 1.3 明确 `streamdown` 只用于 assistant 正文，不扩展到整页布局或协议层

## 2. 消息展示层重构

- [x] 2.1 新增 `UIMessage.parts -> view model` 的归一化逻辑
- [x] 2.2 将 assistant `text` parts 聚合为单一 markdown 文本流
- [x] 2.3 将 `data-step` 映射为轻量状态文案
- [x] 2.4 将 `data-citation` 抽取为来源结构
- [x] 2.5 将 `data-error` 映射为友好错误提示
- [x] 2.6 确保 raw `tool-*`、raw `data-step`、raw citation JSON 不进入默认阅读视图

## 3. 组件拆分与页面接线

- [x] 3.1 从 `frontend/app/(dashboard)/chat/page.tsx` 中提取 assistant 正文渲染组件
- [x] 3.2 新增轻量状态组件
- [x] 3.3 新增 citation 来源区组件
- [x] 3.4 将页面改为按“正文 / 状态 / 来源 / 错误”分层渲染 assistant 消息
- [x] 3.5 确保 citation 缺少 snippet 时仍能渲染最小可用来源卡片（至少包含标题或知识库标识）
- [x] 3.6 确保 `data-error` 以友好错误卡片展示，而不是 raw JSON `pre` 块

## 4. Markdown / 代码块 / Mermaid 体验

- [x] 4.1 使用 `streamdown` 渲染 assistant markdown 正文
- [x] 4.2 接入代码块增强，保证流式代码块阅读稳定
- [x] 4.3 仅对 fenced `mermaid` block 启用 Mermaid 渲染
- [x] 4.4 Mermaid 渲染失败时降级为普通代码块

## 5. 测试与验收

- [x] 5.1 新增或更新 view-model 单测，覆盖 text / step / citation / tool 的归一化逻辑
- [x] 5.2 新增或更新 UI 测试，验证 raw JSON 不再进入默认阅读视图
- [x] 5.3 新增或更新 UI 测试，验证状态文案和来源区展示
- [x] 5.4 新增或更新韧性测试，验证 Mermaid 失败降级与异常辅助数据容错
- [x] 5.5 新增或更新测试，验证 citation 在缺少 snippet 时仍能展示最小来源信息
- [x] 5.6 新增或更新测试，验证 `data-error` 被渲染为友好错误卡片且不覆盖已生成正文
