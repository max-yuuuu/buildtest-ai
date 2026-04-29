from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.chat.domain.models import QuickChatResult, RetrievalAttempt, ToolCallRecord
from app.chat.domain.ports import AnswerGeneratorPort, KnowledgeRetrieverPort, ToolInvokerPort
from app.chat.infrastructure.external_tool_adapter import ExternalToolAdapter
from app.schemas.knowledge_base import RetrieveHit


class _AgentState(TypedDict):
    message: str
    knowledge_base_ids: list[uuid.UUID]
    normalized_query: str
    iter_count: int
    max_iters: int
    hits: list[RetrieveHit]
    attempts: list[RetrievalAttempt]
    tool_calls: list[ToolCallRecord]
    errors: list[dict[str, Any]]
    context: str
    citations: list[dict[str, Any]]
    citation_mappings: list[dict[str, Any]]
    answer: str


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _assemble_context(hits: list[RetrieveHit]) -> tuple[str, list[dict], list[dict]]:
    context_blocks: list[str] = []
    citations: list[dict] = []
    citation_mappings: list[dict] = []
    for i, hit in enumerate(hits, start=1):
        context_blocks.append(f"[{i}] {hit.text}")
        citation_id = f"c{i}"
        citations.append(
            {
                "citation_id": citation_id,
                "document_id": str(hit.document_id),
                "chunk_index": hit.chunk_index,
                "score": hit.score,
                "source": hit.source or {},
            }
        )
        citation_mappings.append(
            {
                "citation_id": citation_id,
                "knowledge_base_id": str(hit.knowledge_base_id) if hit.knowledge_base_id else None,
                "document_id": str(hit.document_id),
                "chunk_index": hit.chunk_index,
                "score": hit.score,
            }
        )
    return "\n".join(context_blocks), citations, citation_mappings


def _initial_state(*, message: str, knowledge_base_ids: list[uuid.UUID], max_iters: int) -> _AgentState:
    return {
        "message": message,
        "knowledge_base_ids": knowledge_base_ids,
        "normalized_query": "",
        "iter_count": 0,
        "max_iters": max_iters,
        "hits": [],
        "attempts": [],
        "tool_calls": [],
        "errors": [],
        "context": "",
        "citations": [],
        "citation_mappings": [],
        "answer": "",
    }


def _state_to_result(state: dict[str, Any]) -> QuickChatResult:
    return QuickChatResult(
        answer=state["answer"],
        citations=state["citations"],
        citation_mappings=state["citation_mappings"],
        attempts=state["attempts"],
        tool_calls=state["tool_calls"],
        errors=state["errors"],
    )


def _build_agent_graph(
    *,
    retriever: KnowledgeRetrieverPort,
    tool_invoker: ToolInvokerPort,
    answer_generator: AnswerGeneratorPort,
    external_tool_adapter: ExternalToolAdapter | None = None,
):
    async def normalize_node(state: _AgentState) -> dict[str, Any]:
        return {"normalized_query": _normalize_query(state["message"])}

    async def think_node(state: _AgentState) -> dict[str, Any]:
        # MVP: decision is deterministic (no LLM reasoning yet).
        # - If we already have hits, finalize.
        # - If we exhausted iterations, finalize.
        # - Otherwise, call retrieve tool.
        return {}

    def route_after_think(state: _AgentState) -> str:
        if state["hits"]:
            return "finalize"
        if state["iter_count"] >= state["max_iters"]:
            return "finalize"
        return "tool_call"

    async def tool_call_node(state: _AgentState) -> dict[str, Any]:
        all_hits: list[RetrieveHit] = []
        attempts: list[RetrievalAttempt] = []
        tool_calls: list[ToolCallRecord] = []
        errors: list[dict[str, Any]] = []

        query = state["normalized_query"]
        for kb_id in state["knowledge_base_ids"]:
            try:
                tool_call = await tool_invoker.invoke_retrieve_tool(
                    mode="agent",
                    knowledge_base_id=kb_id,
                    query=query,
                )
                hits, latency_ms = await retriever.retrieve(knowledge_base_id=kb_id, query=query)
                attempts.append(
                    RetrievalAttempt(
                        knowledge_base_id=str(kb_id),
                        attempt=state["iter_count"] + 1,
                        query=query,
                        hit_count=len(hits),
                        latency_ms=latency_ms,
                    )
                )
                tool_calls.append(tool_call)
                all_hits.extend(hits)
                if external_tool_adapter is not None:
                    await external_tool_adapter.call(
                        tool_name="langflow.run",
                        payload={"query": query, "knowledge_base_id": str(kb_id)},
                    )
            except Exception as exc:
                errors.append(
                    {
                        "knowledge_base_id": str(kb_id),
                        "code": "RETRIEVE_FAILED",
                        "message": str(exc),
                    }
                )

        new_hits = sorted(all_hits, key=lambda hit: hit.score, reverse=True)[:5]
        return {
            "iter_count": state["iter_count"] + 1,
            "hits": new_hits,
            "attempts": state["attempts"] + attempts,
            "tool_calls": state["tool_calls"] + tool_calls,
            "errors": state["errors"] + errors,
        }

    async def finalize_node(state: _AgentState) -> dict[str, Any]:
        context, citations, mappings = _assemble_context(state["hits"])
        answer = answer_generator.generate(
            question=state["message"],
            context=context,
            has_hits=len(state["hits"]) > 0,
        )
        return {"context": context, "citations": citations, "citation_mappings": mappings, "answer": answer}

    graph = StateGraph(_AgentState)
    graph.add_node("normalize", normalize_node)
    graph.add_node("think", think_node)
    graph.add_node("tool_call", tool_call_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "think")
    graph.add_conditional_edges("think", route_after_think, {"tool_call": "tool_call", "finalize": "finalize"})
    graph.add_edge("tool_call", "think")
    graph.add_edge("finalize", END)
    return graph.compile()


async def run_agent_graph(
    *,
    message: str,
    knowledge_base_ids: list[uuid.UUID],
    retriever: KnowledgeRetrieverPort,
    tool_invoker: ToolInvokerPort,
    answer_generator: AnswerGeneratorPort,
    external_tool_adapter: ExternalToolAdapter | None = None,
    max_iters: int = 3,
) -> QuickChatResult:
    graph = _build_agent_graph(
        retriever=retriever,
        tool_invoker=tool_invoker,
        answer_generator=answer_generator,
        external_tool_adapter=external_tool_adapter,
    )
    state = await graph.ainvoke(_initial_state(message=message, knowledge_base_ids=knowledge_base_ids, max_iters=max_iters))
    return _state_to_result(state)


async def astream_agent_graph(
    *,
    message: str,
    knowledge_base_ids: list[uuid.UUID],
    retriever: KnowledgeRetrieverPort,
    tool_invoker: ToolInvokerPort,
    answer_generator: AnswerGeneratorPort,
    external_tool_adapter: ExternalToolAdapter | None = None,
    max_iters: int = 3,
) -> AsyncIterator[dict[str, Any]]:
    graph = _build_agent_graph(
        retriever=retriever,
        tool_invoker=tool_invoker,
        answer_generator=answer_generator,
        external_tool_adapter=external_tool_adapter,
    )
    output_state: dict[str, Any] | None = None
    step_nodes = {"think", "tool_call", "finalize"}

    async for evt in graph.astream_events(
        _initial_state(message=message, knowledge_base_ids=knowledge_base_ids, max_iters=max_iters),
        version="v1",
    ):
        event_name = evt.get("event")
        node_name = evt.get("name")
        if event_name == "on_chain_start" and node_name in step_nodes:
            yield {"type": "step", "name": node_name, "status": "running"}
        elif event_name == "on_chain_end" and node_name in step_nodes:
            yield {"type": "step", "name": node_name, "status": "completed"}

        data = evt.get("data")
        if (
            event_name == "on_chain_end"
            and isinstance(data, dict)
            and isinstance(data.get("output"), dict)
            and {"answer", "citations", "citation_mappings", "attempts", "tool_calls", "errors"}.issubset(
                data["output"].keys()
            )
        ):
            output_state = data["output"]

    if output_state is None:
        output_state = await graph.ainvoke(_initial_state(message=message, knowledge_base_ids=knowledge_base_ids, max_iters=max_iters))
    yield {"type": "result", "result": _state_to_result(output_state)}
