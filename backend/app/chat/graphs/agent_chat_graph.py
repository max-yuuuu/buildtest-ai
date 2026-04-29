from __future__ import annotations

import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.chat.domain.models import QuickChatResult, ToolCallRecord


class _AgentState(TypedDict):
    message: str
    knowledge_base_ids: list[uuid.UUID]
    iteration: int
    max_iterations: int
    need_tool: bool
    observation: str
    done: bool
    answer: str
    tool_calls: list[ToolCallRecord]
    errors: list[dict[str, Any]]


def _should_use_tool(message: str, iteration: int) -> bool:
    if iteration > 1:
        return False
    intent_tokens = ("检索", "查", "搜索", "retrieve")
    return any(token in message for token in intent_tokens)


async def run_agent_graph(
    *,
    message: str,
    knowledge_base_ids: list[uuid.UUID],
    max_iterations: int = 3,
) -> QuickChatResult:
    def init_node(state: _AgentState) -> dict[str, Any]:
        _ = state
        return {"iteration": 0, "done": False, "need_tool": False, "observation": "", "tool_calls": [], "errors": []}

    def think_node(state: _AgentState) -> dict[str, Any]:
        next_iteration = state["iteration"] + 1
        need_tool = _should_use_tool(state["message"], next_iteration)
        return {"iteration": next_iteration, "need_tool": need_tool}

    def tool_call_node(state: _AgentState) -> dict[str, Any]:
        tool_call = ToolCallRecord(
            tool_id="api_retrieve",
            category="api",
            input={"message": state["message"], "knowledge_base_ids": [str(k) for k in state["knowledge_base_ids"]]},
            result={"ok": True, "summary": "mocked retrieval result"},
            latency_ms=1,
            trace_meta={"tool_call_id": f"tool_{uuid.uuid4().hex[:12]}"},
        )
        return {"tool_calls": [*state["tool_calls"], tool_call], "observation": "工具检索完成"}

    def observe_node(state: _AgentState) -> dict[str, Any]:
        done = state["iteration"] >= state["max_iterations"] or len(state["tool_calls"]) > 0
        return {"done": done}

    def finalize_node(state: _AgentState) -> dict[str, Any]:
        if state["tool_calls"]:
            answer = f"基于工具结果回复：{state['message']}"
        else:
            answer = f"直接回复：{state['message']}"
        return {"answer": answer}

    def route_after_think(state: _AgentState) -> str:
        return "tool_call" if state["need_tool"] else "finalize"

    def route_after_observe(state: _AgentState) -> str:
        return "finalize" if state["done"] else "think"

    graph = StateGraph(_AgentState)
    graph.add_node("init", init_node)
    graph.add_node("think", think_node)
    graph.add_node("tool_call", tool_call_node)
    graph.add_node("observe", observe_node)
    graph.add_node("finalize", finalize_node)
    graph.add_edge(START, "init")
    graph.add_edge("init", "think")
    graph.add_conditional_edges("think", route_after_think, {"tool_call": "tool_call", "finalize": "finalize"})
    graph.add_edge("tool_call", "observe")
    graph.add_conditional_edges("observe", route_after_observe, {"think": "think", "finalize": "finalize"})
    graph.add_edge("finalize", END)
    compiled = graph.compile()

    output = await compiled.ainvoke(
        {
            "message": message,
            "knowledge_base_ids": knowledge_base_ids,
            "iteration": 0,
            "max_iterations": max_iterations,
            "need_tool": False,
            "observation": "",
            "done": False,
            "answer": "",
            "tool_calls": [],
            "errors": [],
        }
    )
    return QuickChatResult(
        answer=output["answer"],
        citations=[],
        citation_mappings=[],
        attempts=[],
        tool_calls=output["tool_calls"],
        errors=output["errors"],
    )
