# Quick Chat MVP 大局架构方案

## 1. 架构目标

- 先交付可稳定运行的 `quick` 模式（检索-生成-引用-流式输出）。
- 保留 `agent/data` 扩展位，但不在 MVP 引入复杂工具编排。
- 保证 query-time 可追溯（attempt、citation、latency）。

## 2. 分层与依赖方向

基于 Clean + Hexagonal，chat 侧采用三层：

- `domain`：核心模型和端口，不依赖 FastAPI/DB/LangChain。
- `application`：用例编排（normalize/rewrite/retrieve/assemble/generate）。
- `infrastructure`：适配已有 `KnowledgeBaseService`、`ToolRegistry` 等外部实现。

依赖方向固定为：

`infrastructure -> application -> domain`

## 3. 代码落地结构

新增目录：

- `backend/app/chat/domain/models.py`
- `backend/app/chat/domain/ports.py`
- `backend/app/chat/application/quick_chat_use_case.py`
- `backend/app/chat/infrastructure/adapters.py`
- `backend/app/chat/facade.py`

现有 `backend/app/services/chat_service.py` 保持 API 入口职责，内部改为调用 `ChatFacade`。

## 4. 与 OpenSpec 对齐关系

- `quick-chat-workflow`：由 `RunQuickChatUseCase` 承担主流程编排。
- `tool-registry-contract`：通过 `QuickModeToolInvokerAdapter` 执行 `api_retrieve`，保留 mode allowlist 约束。
- `chat-mode-routing`：仍由 `ChatService` 在入口处处理 `quick|agent|data` 行为边界。
- `retrieval-lineage-contract`：`RetrievalAttempt + citation_mappings` 作为链路事实记录继续输出。

## 5. 运行时流程（Quick）

1. `ChatService` 处理 HTTP/SSE 请求与 mode 分发。
2. `ChatFacade.run_quick()` 调用 `RunQuickChatUseCase.execute()`。
3. 用例执行：
   - query normalize
   - attempt#1 检索（tool call + KB retrieve）
   - 空结果时 attempt#2 rewrite + 重检
   - 上下文装配与 citation 映射
   - 生成回答（命中/降级两条路径）
4. `ChatService.stream()` 负责将结果映射到 `start/token/citation/step/error/done` 事件。

## 6. 扩展路线（不破坏 MVP）

- `agent/data`：新增对应 use case，不修改已稳定的 quick 用例。
- 工具扩展：在 `ToolInvokerPort` 下新增 agent/data 专用适配器，维持 mode allowlist。
- 生成扩展：替换 `TemplateAnswerGeneratorAdapter` 为 LLM 实现，不改 domain/application 接口。
- 检索扩展：在 `KnowledgeRetrieverPort` 适配层增加 hybrid/rerank，仅替换 adapter。

## 7. 验证与风险

已验证：

- `tests/unit/test_chat_mode_routing.py`
- `tests/unit/test_chat_stream_contract.py`
- `tests/unit/test_quick_chat_workflow.py`

命令：

- `uv run pytest --no-cov tests/unit/test_chat_mode_routing.py tests/unit/test_chat_stream_contract.py tests/unit/test_quick_chat_workflow.py`

注意：

- 仓库默认 pytest 带全量覆盖率门禁，单独跑局部测试需使用 `--no-cov` 避免被整体覆盖率拦截。
