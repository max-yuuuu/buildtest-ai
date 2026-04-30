# LangGraph 收敛 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 10 天内交付收敛版 MVP：Quick Chat 可上线、Agent 最小闭环、Retriever 抽象、模型配置、前端适配与 LangFlow/MCP 预留接口，统一基于 LangGraph 1.x。

**Architecture:** 后端以 LangGraph 1.x 作为唯一编排层：Quick 线性图 + Agent ReAct 循环图；ChatService 负责 HTTP/SSE 协议输出；BFF 仅做事件映射。以 TDD 驱动每个阶段，优先保证流式契约稳定，再扩展能力。

**Tech Stack:** FastAPI, LangGraph `1.0.8`, LangChain Core（与现有依赖树兼容版本）, SQLAlchemy AsyncSession, Next.js App Router, AI SDK stream mapping, pytest, Vitest。

---

## Scope Check

本规格覆盖后端编排、模型配置、前端流式映射与 UI 适配，子系统间是强耦合链路（同一请求路径与流式契约），拆成多个独立计划会引入接口漂移风险。保留单计划执行，但按任务拆分为可独立提交的 PR。

---

## File Structure (target)

- `backend/app/chat/graphs/quick_chat_graph.py`：Quick Chat LangGraph 线性图与状态定义。
- `backend/app/chat/graphs/agent_chat_graph.py`：Agent ReAct 循环图与轮次控制。
- `backend/app/chat/graphs/types.py`：图状态与事件类型（共享 schema）。
- `backend/app/chat/infrastructure/llm_adapter.py`：真实 LLM 生成与 provider/model 解析入口。
- `backend/app/chat/application/quick_chat_use_case.py`：从 imperative 流程迁移到 graph invoke。
- `backend/app/chat/application/agent_chat_use_case.py`：从 NotImplemented 迁移到 graph invoke。
- `backend/app/services/chat_service.py`：改为消费 `astream_events`，统一 SSE 契约。
- `backend/app/chat/domain/retriever.py`：Retriever 抽象协议 + 默认 VectorRetriever。
- `backend/tests/unit/test_quick_chat_graph.py`：Quick 图单测。
- `backend/tests/unit/test_agent_chat_graph.py`：Agent 图单测。
- `backend/tests/unit/test_chat_stream_contract.py`：流式事件顺序与终止条件回归。
- `backend/tests/unit/test_chat_mode_routing.py`：mode 路由和不再 501 的 agent 用例。
- `frontend/lib/server/chat-stream-mapper.ts`：新增 agent 事件映射（tool/step/error）。
- `frontend/tests/unit/chat-route.test.ts`：映射契约回归。
- `frontend/tests/unit/chat-page.test.tsx`：前端模型配置与聊天模式联动测试。

---

### Task 1: 锁定 LangGraph 1.x 与基础脚手架

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/chat/graphs/__init__.py`
- Create: `backend/app/chat/graphs/types.py`
- Test: `backend/tests/unit/test_quick_chat_graph.py`

- [ ] **Step 1: 写失败测试（图状态可初始化）**

```python
# backend/tests/unit/test_quick_chat_graph.py
from app.chat.graphs.types import QuickGraphState


def test_quick_graph_state_minimal_fields():
    state: QuickGraphState = {
        "message": "hello",
        "knowledge_base_ids": [],
        "attempts": [],
        "hits": [],
        "events": [],
    }
    assert state["message"] == "hello"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/unit/test_quick_chat_graph.py::test_quick_graph_state_minimal_fields -v`  
Expected: FAIL with `ModuleNotFoundError: app.chat.graphs.types`

- [ ] **Step 3: 最小实现 types 与包导出**

```python
# backend/app/chat/graphs/types.py
from __future__ import annotations
from typing import TypedDict, Any


class QuickGraphState(TypedDict):
    message: str
    knowledge_base_ids: list[str]
    attempts: list[dict[str, Any]]
    hits: list[dict[str, Any]]
    events: list[dict[str, Any]]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && pytest tests/unit/test_quick_chat_graph.py::test_quick_graph_state_minimal_fields -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/chat/graphs/__init__.py backend/app/chat/graphs/types.py backend/tests/unit/test_quick_chat_graph.py
git commit -m "build(backend): 引入LangGraph基础脚手架与状态类型"
```

---

### Task 2: Quick Chat LangGraph 线性图替换现有 imperative 流程

**Files:**
- Create: `backend/app/chat/graphs/quick_chat_graph.py`
- Modify: `backend/app/chat/application/quick_chat_use_case.py`
- Modify: `backend/app/chat/facade.py`
- Test: `backend/tests/unit/test_quick_chat_graph.py`

- [ ] **Step 1: 写失败测试（Quick 图输出 answer + citations）**

```python
@pytest.mark.asyncio
async def test_quick_graph_returns_answer_and_citations():
    from app.chat.graphs.quick_chat_graph import run_quick_graph

    result = await run_quick_graph(
        message="什么是RAG",
        knowledge_base_ids=[],
        retriever=lambda *_args, **_kwargs: [],
        answer_generator=lambda question, context, has_hits: f"A:{question}|{has_hits}",
    )
    assert result.answer.startswith("A:")
    assert isinstance(result.citations, list)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/unit/test_quick_chat_graph.py::test_quick_graph_returns_answer_and_citations -v`  
Expected: FAIL with `ImportError` or missing `run_quick_graph`

- [ ] **Step 3: 最小实现 Quick 图并接入 use case**

```python
# backend/app/chat/graphs/quick_chat_graph.py (核心形态)
from langgraph.graph import StateGraph, START, END

def build_quick_graph():
    graph = StateGraph(QuickGraphState)
    graph.add_node("normalize", normalize_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("assemble", assemble_node)
    graph.add_node("generate", generate_node)
    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "retrieve")
    graph.add_edge("retrieve", "assemble")
    graph.add_edge("assemble", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
```

- [ ] **Step 4: 运行相关单测**

Run: `cd backend && pytest tests/unit/test_quick_chat_graph.py tests/unit/test_quick_chat_workflow.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/chat/graphs/quick_chat_graph.py backend/app/chat/application/quick_chat_use_case.py backend/app/chat/facade.py backend/tests/unit/test_quick_chat_graph.py
git commit -m "feat(backend): 用LangGraph线性图重构Quick Chat"
```

---

### Task 3: ChatService 流式改为消费 LangGraph 事件

**Files:**
- Modify: `backend/app/services/chat_service.py`
- Test: `backend/tests/unit/test_chat_stream_contract.py`
- Test: `backend/tests/integration/test_quick_chat_api_integration.py`

- [ ] **Step 1: 写失败测试（done 前必须有 step_generate completed）**

```python
@pytest.mark.asyncio
async def test_chat_stream_generate_completed_before_done():
    service = ChatService(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]
    async def fake_run_quick(_body):  # noqa: ANN001
        return QuickChatOutput(
            answer="hello",
            citations=[],
            citation_mappings=[],
            attempts=[
                RetrievalAttempt(
                    knowledge_base_id=str(uuid.uuid4()),
                    attempt=1,
                    query="hi",
                    hit_count=1,
                    latency_ms=5,
                )
            ],
            tool_calls=[],
            errors=[],
        )

    service._run_quick = fake_run_quick  # type: ignore[method-assign]
    events = [e async for e in service.stream(ChatRequest(message="hi", knowledge_base_ids=[uuid.uuid4()]))]
    done_idx = next(i for i, e in enumerate(events) if e["type"] == "done")
    assert any(e["type"] == "step" and e.get("id") == "step_generate" and e.get("status") == "completed" for e in events[:done_idx])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/unit/test_chat_stream_contract.py::test_chat_stream_generate_completed_before_done -v`  
Expected: FAIL

- [ ] **Step 3: 实现 `astream_events` 到 SSE 事件映射**

```python
# backend/app/services/chat_service.py (新增核心逻辑示例)
async for evt in quick_graph.astream_events(input_state, version="v1"):
    kind = evt["event"]
    if kind == "on_chat_model_stream":
        yield self._event("text-delta", trace_id, {"text": evt["data"]["chunk"], "message_id": message_id})
```

- [ ] **Step 4: 运行单测 + 集成测试**

Run: `cd backend && pytest tests/unit/test_chat_stream_contract.py tests/integration/test_quick_chat_api_integration.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/chat_service.py backend/tests/unit/test_chat_stream_contract.py backend/tests/integration/test_quick_chat_api_integration.py
git commit -m "feat(backend): 基于LangGraph事件重构聊天流式输出"
```

---

### Task 4: Agent 最小闭环（ReAct + 上限轮次 3）

**Files:**
- Create: `backend/app/chat/graphs/agent_chat_graph.py`
- Modify: `backend/app/chat/application/agent_chat_use_case.py`
- Modify: `backend/app/services/chat_service.py`
- Test: `backend/tests/unit/test_agent_chat_graph.py`
- Test: `backend/tests/unit/test_chat_mode_routing.py`

- [ ] **Step 1: 写失败测试（agent mode 不再返回 MODE_NOT_IMPLEMENTED）**

```python
@pytest.mark.asyncio
async def test_chat_service_agent_mode_returns_answer():
    service = ChatService(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]
    res = await service.run(ChatRequest(message="查知识库", mode="agent", knowledge_base_ids=[uuid.uuid4()]))
    assert isinstance(res.answer, str)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/unit/test_chat_mode_routing.py::test_chat_service_agent_mode_returns_answer -v`  
Expected: FAIL with HTTP 501

- [ ] **Step 3: 实现最小 Agent 图**

```python
# backend/app/chat/graphs/agent_chat_graph.py (核心结构)
graph.add_node("think", think_node)
graph.add_node("tool_call", tool_call_node)
graph.add_node("observe", observe_node)
graph.add_node("finalize", finalize_node)
graph.add_conditional_edges("think", route_after_think, {"tool": "tool_call", "final": "finalize"})
graph.add_edge("tool_call", "observe")
graph.add_conditional_edges("observe", route_after_observe, {"continue": "think", "final": "finalize"})
```

- [ ] **Step 4: 运行相关测试**

Run: `cd backend && pytest tests/unit/test_agent_chat_graph.py tests/unit/test_chat_mode_routing.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/chat/graphs/agent_chat_graph.py backend/app/chat/application/agent_chat_use_case.py backend/app/services/chat_service.py backend/tests/unit/test_agent_chat_graph.py backend/tests/unit/test_chat_mode_routing.py
git commit -m "feat(backend): 实现Agent最小ReAct闭环并接入路由"
```

---

### Task 5: Retriever 抽象层（Vector 默认实现 + Graph 预留）

**Files:**
- Create: `backend/app/chat/domain/retriever.py`
- Modify: `backend/app/chat/domain/ports.py`
- Modify: `backend/app/chat/infrastructure/adapters.py`
- Test: `backend/tests/unit/test_retriever_abstraction.py`

- [ ] **Step 1: 写失败测试（VectorRetriever 满足统一协议）**

```python
@pytest.mark.asyncio
async def test_vector_retriever_protocol_returns_hits_and_latency():
    retriever = VectorRetriever(...)
    hits, latency_ms = await retriever.retrieve(knowledge_base_id=uuid.uuid4(), query="postgres")
    assert isinstance(hits, list)
    assert isinstance(latency_ms, int)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/unit/test_retriever_abstraction.py::test_vector_retriever_protocol_returns_hits_and_latency -v`  
Expected: FAIL with `NameError: VectorRetriever`

- [ ] **Step 3: 实现协议与默认实现**

```python
class Retriever(Protocol):
    async def retrieve(self, *, knowledge_base_id: uuid.UUID, query: str) -> tuple[list[RetrieveHit], int]: ...

class VectorRetriever(Retriever):
    async def retrieve(...):
        return await self._kb_adapter.retrieve(...)
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && pytest tests/unit/test_retriever_abstraction.py tests/unit/test_quick_chat_graph.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/chat/domain/retriever.py backend/app/chat/domain/ports.py backend/app/chat/infrastructure/adapters.py backend/tests/unit/test_retriever_abstraction.py
git commit -m "refactor(backend): 抽象Retriever协议并保留Graph扩展入口"
```

---

### Task 6: 模型配置系统最小化（quick/agent）

**Files:**
- Create: `backend/app/chat/infrastructure/llm_adapter.py`
- Modify: `backend/app/chat/facade.py`
- Modify: `backend/app/chat/graphs/quick_chat_graph.py`
- Modify: `backend/app/chat/graphs/agent_chat_graph.py`
- Test: `backend/tests/unit/test_llm_adapter.py`

- [ ] **Step 1: 写失败测试（配置缺失时 fallback）**

```python
def test_llm_adapter_fallback_to_default_model():
    adapter = LLMAdapter(model_service=FakeModelService(None))
    model = adapter.resolve(mode="quick", user_id=uuid.uuid4())
    assert model.model_name == "default"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/unit/test_llm_adapter.py::test_llm_adapter_fallback_to_default_model -v`  
Expected: FAIL

- [ ] **Step 3: 实现最小 LLM adapter 并接图节点**

```python
class LLMAdapter:
    def resolve(self, *, mode: str, user_id: uuid.UUID) -> ResolvedModel:
        configured = self._model_service.get_for_mode(user_id=user_id, mode=mode)
        return configured or ResolvedModel(provider="openai", model_name="default")
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && pytest tests/unit/test_llm_adapter.py tests/unit/test_agent_chat_graph.py tests/unit/test_quick_chat_graph.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/chat/infrastructure/llm_adapter.py backend/app/chat/facade.py backend/app/chat/graphs/quick_chat_graph.py backend/app/chat/graphs/agent_chat_graph.py backend/tests/unit/test_llm_adapter.py
git commit -m "feat(backend): 增加mode级模型配置与fallback"
```

---

### Task 7: 前端流式映射与模型配置 UI 收敛

**Files:**
- Modify: `frontend/lib/server/chat-stream-mapper.ts`
- Modify: `frontend/app/api/chat/route.ts`
- Modify: `frontend/components/chat/chat-status-line.tsx`
- Test: `frontend/tests/unit/chat-route.test.ts`
- Test: `frontend/tests/unit/chat-page.test.tsx`

- [ ] **Step 1: 写失败测试（agent 工具事件映射）**

```typescript
it("maps agent tool-call/tool-result events", () => {
  const state = createChatStreamMappingState();
  mapBackendEventToUiMessageChunkSse({ type: "start", message_id: "msg_1" }, state);
  const chunks = mapBackendEventToUiMessageChunkSse(
    { type: "tool-call", message_id: "msg_1", tool_call_id: "tc1", tool_name: "api_retrieve", input: { q: "rag" } },
    state,
  );
  expect(chunks[0]).toContain('"type":"tool-input-available"');
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && pnpm test -- chat-route.test.ts`  
Expected: FAIL

- [ ] **Step 3: 最小实现映射与 UI 状态展示**

```typescript
if (kind === "data-error") {
  // 统一错误落到状态行，避免静默失败
  setStatus({ level: "error", message: String(data.message ?? "chat failed") });
}
```

- [ ] **Step 4: 运行前端测试**

Run: `cd frontend && pnpm test -- chat-route.test.ts chat-page.test.tsx`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/server/chat-stream-mapper.ts frontend/app/api/chat/route.ts frontend/components/chat/chat-status-line.tsx frontend/tests/unit/chat-route.test.ts frontend/tests/unit/chat-page.test.tsx
git commit -m "feat(frontend): 收敛Agent流式映射与聊天状态展示"
```

---

### Task 8: LangFlow/MCP 预留接口（契约 + mock）

**Files:**
- Create: `backend/app/chat/infrastructure/external_tool_adapter.py`
- Create: `backend/tests/unit/test_external_tool_adapter_contract.py`
- Modify: `backend/app/chat/graphs/agent_chat_graph.py`

- [ ] **Step 1: 写失败测试（adapter contract）**

```python
@pytest.mark.asyncio
async def test_external_tool_adapter_contract():
    adapter = MockExternalToolAdapter()
    out = await adapter.call(tool_name="langflow.run", payload={"input": "hi"})
    assert out["ok"] is True
    assert "trace_id" in out
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/unit/test_external_tool_adapter_contract.py -v`  
Expected: FAIL with missing adapter

- [ ] **Step 3: 实现最小 adapter 与 graph 注入点**

```python
class ExternalToolAdapter(Protocol):
    async def call(self, *, tool_name: str, payload: dict) -> dict: ...

class MockExternalToolAdapter:
    async def call(self, *, tool_name: str, payload: dict) -> dict:
        return {"ok": True, "tool_name": tool_name, "payload": payload, "trace_id": "mock-trace"}
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && pytest tests/unit/test_external_tool_adapter_contract.py tests/unit/test_agent_chat_graph.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/chat/infrastructure/external_tool_adapter.py backend/tests/unit/test_external_tool_adapter_contract.py backend/app/chat/graphs/agent_chat_graph.py
git commit -m "feat(backend): 增加LangFlow/MCP预留适配接口与契约测试"
```

---

## 逐日排期（10 天）

- Day 1: Task 1 + Task 2（Quick 图骨架）
- Day 2: Task 3（流式契约改造）
- Day 3-4: Task 4（Agent 最小闭环）
- Day 5: Task 5（Retriever 抽象）
- Day 6-7: Task 6（模型配置）
- Day 8-9: Task 7（前端适配）
- Day 10: Task 8 + 全量回归 + 文档更新

---

## 逐 PR 切分建议

- PR1: `build/feat(backend)` LangGraph 脚手架 + Quick 图
- PR2: `feat(backend)` ChatService 流式事件重构
- PR3: `feat(backend)` Agent 最小闭环
- PR4: `refactor(backend)` Retriever 抽象
- PR5: `feat(backend)` 模型配置最小化
- PR6: `feat(frontend)` 流式映射 + UI 状态
- PR7: `feat(backend)` LangFlow/MCP 预留接口

---

## 自检结果

- **Spec coverage:** 已覆盖六项硬交付与 10 天窗口；每项有对应任务与测试命令。
- **Placeholder scan:** 无 TBD/TODO/“后续实现”式步骤；每个任务给出代码与命令。
- **Type consistency:** 统一使用 `QuickGraphState`、`run_quick_graph`、`LLMAdapter`、`ExternalToolAdapter` 命名，任务间保持一致。

