## 1. 协议与运行入口基线（必须最先完成）

- [x] 1.1 在前端安装并锁定 `ai@6 latest`，确认是否还需要配套安装 `@ai-sdk/react` / 其他相关包的最新兼容版本
- [x] 1.2 从本地 `node_modules/ai/docs` 与源码确认 `useChat` 对 UI message stream 的响应协议、text/data/tool parts 字段与 helper API
- [x] 1.3 将确认后的 AI SDK 6 协议约束回写到实现注释或开发文档，明确 `start/finish`、`text-*`、`data-*`、`tool-input-available`、`tool-output-available`
- [x] 1.4 梳理并统一 `env/common.env`、`env/dev.host.env`、`env/dev.docker.env`、`frontend/.env` 中与 chat/BFF/backend 地址相关的变量语义
- [x] 1.5 统一 compose 入口与文档命名，清理失效的 `compose.base/dev/prod` 或其他漂移引用，确保 `docker-compose*.yml`、`scripts/dev`、`Makefile`、启动文档一致
- [x] 1.6 固定 `BACKEND_URL` 的显式优先级与 fallback 行为，并在 host / Docker 两种模式下确认最终命中的 backend 地址

## 2. 后端请求契约与领域事件（BFF 之前完成）

- [x] 2.1 将 `backend/app/schemas/chat.py` 的请求体重构为唯一契约 `knowledge_base_ids: list[UUID]`
- [x] 2.2 更新后端 chat 路由、service、facade、use case 的所有关联点，移除旧 `knowledge_base_id` 逻辑
- [x] 2.3 在 Quick Chat workflow 中实现多知识库串行检索、全局合并、排序、截断与 citation 来源保留
- [x] 2.4 对单个 KB 检索失败实现局部 error/step 事件，不中断整轮请求
- [x] 2.5 将后端流事件统一为 `start` / `text-delta` / `citation` / `step` / `tool-call` / `tool-result` / `error` / `done`
- [x] 2.6 为 Quick Chat 的 retrieval 工具输出 `tool-call` 与 `tool-result` 事件，保证 `tool_call_id` 稳定可配对
- [x] 2.7 保证同一轮 assistant 回复的 `message_id` 稳定，便于 BFF 聚合为单条消息

## 3. Next BFF 到 AI SDK 6 UI stream 映射

- [x] 3.1 重构 `frontend/app/api/chat/route.ts`，将 Python 领域事件逐条映射为 AI SDK 6 UI message stream chunks
- [x] 3.2 实现 text parts 的开始/增量/结束映射，避免重复 assistant message
- [x] 3.3 实现 data parts（citation/step/error/status）映射
- [x] 3.4 实现 Python `tool-call` / `tool-result` 到 AI SDK 6 `tool-input-available` / `tool-output-available` 的映射

## 4. 前端 Quick Chat UI 与 `@KB` 交互

- [x] 4.1 将 chat 页面升级为“默认主知识库 + `@知识库` mention + pills + Notion 风格输入区”
- [x] 4.2 实现输入文本中的 `@KB` 解析、去重、删除同步与请求体 `knowledge_base_ids[]` 生成
- [x] 4.3 保证没有 `@KB` 时自动使用默认主知识库作为单元素数组发送
- [x] 4.4 更新消息渲染，支持 text / data / tool 三类 parts（含 `tool-input-available` / `tool-output-available`）

## 5. 文档同步（Docker / env 方案定稿后执行）

- [x] 5.1 若本次变更涉及 Docker / compose / env 分层修改，同步更新 `docs/启动文档/1.启动指南.md`
- [x] 5.2 若本次变更涉及 Docker / compose / env 分层修改，同步更新 `CLAUDE.md`
- [x] 5.3 若本次变更涉及 Docker / compose / env 分层修改，同步更新 `AGENTS.md`
- [x] 5.4 更新启动文档，明确 host 与 Docker 两种开发模式下的 chat 验证步骤

## 6. 验证与测试（最后总验收）

- [x] 6.1 补充前端单测：`@KB` 解析、默认主知识库兜底、tool/data parts 渲染
- [x] 6.2 补充后端单测：`knowledge_base_ids[]` 请求契约、多库合并检索、tool 事件、局部错误不中断
- [x] 6.3 补充 BFF/契约测试：Python 领域事件到 AI SDK 6 UI stream chunks 的映射正确性
- [ ] 6.4 验证 `ai@6 latest` 在 host 前端与 Docker 前端中的依赖解析与 chat 行为一致
- [ ] 6.5 校验 Docker 开发环境与 host 开发环境都能通过同一路径 `/api/chat` 正常完成流式请求
- [ ] 6.6 至少完成一次 host 环境与 Docker 环境的端到端验证，确认二者行为一致

