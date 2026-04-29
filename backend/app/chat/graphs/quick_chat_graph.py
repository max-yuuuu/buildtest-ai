from __future__ import annotations

import inspect
import re
import uuid
from collections.abc import AsyncIterator
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.chat.domain.models import QuickChatResult, RetrievalAttempt, ToolCallRecord
from app.schemas.knowledge_base import RetrieveHit


class _QuickRunState(TypedDict):
    message: str
    knowledge_base_ids: list[uuid.UUID]
    normalized_query: str
    hits: list[RetrieveHit]
    attempts: list[RetrievalAttempt]
    tool_calls: list[ToolCallRecord]
    errors: list[dict[str, Any]]
    context: str
    citations: list[dict[str, Any]]
    citation_mappings: list[dict[str, Any]]
    answer: str


RetrieveFn = Callable[[uuid.UUID, str], list[RetrieveHit] | Awaitable[list[RetrieveHit]]]
RetrieveAttemptsFn = Callable[
    [uuid.UUID, str],
    Awaitable[tuple[list[RetrieveHit], list[RetrievalAttempt], list[ToolCallRecord]]],
]
AnswerFn = Callable[[str, str, bool], str]


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _maybe_await(value: Any) -> Awaitable[Any]:
    if inspect.isawaitable(value):
        return value
    async def _wrapped() -> Any:
        return value
    return _wrapped()


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


async def run_quick_graph(
    *,
    message: str,
    knowledge_base_ids: list[uuid.UUID],
    retriever: RetrieveFn,
    answer_generator: AnswerFn,
    retrieve_attempts: RetrieveAttemptsFn | None = None,
) -> QuickChatResult:
    graph = _build_quick_graph(retriever=retriever, answer_generator=answer_generator, retrieve_attempts=retrieve_attempts)
    output = await graph.ainvoke(_initial_state(message=message, knowledge_base_ids=knowledge_base_ids))
    return _state_to_result(output)


async def astream_quick_graph(
    *,
    message: str,
    knowledge_base_ids: list[uuid.UUID],
    retriever: RetrieveFn,
    answer_generator: AnswerFn,
    retrieve_attempts: RetrieveAttemptsFn | None = None,
) -> AsyncIterator[dict[str, Any]]:
    graph = _build_quick_graph(retriever=retriever, answer_generator=answer_generator, retrieve_attempts=retrieve_attempts)
    output_state: dict[str, Any] | None = None
    step_nodes = {"retrieve", "generate"}

    async for evt in graph.astream_events(
        _initial_state(message=message, knowledge_base_ids=knowledge_base_ids),
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
            and "answer" in data["output"]
        ):
            output_state = data["output"]

    if output_state is None:
        output_state = await graph.ainvoke(_initial_state(message=message, knowledge_base_ids=knowledge_base_ids))
    yield {"type": "result", "result": _state_to_result(output_state)}


def _initial_state(*, message: str, knowledge_base_ids: list[uuid.UUID]) -> _QuickRunState:
    return {
        "message": message,
        "knowledge_base_ids": knowledge_base_ids,
        "hits": [],
        "attempts": [],
        "tool_calls": [],
        "errors": [],
        "normalized_query": "",
        "context": "",
        "citations": [],
        "citation_mappings": [],
        "answer": "",
    }


def _state_to_result(output: dict[str, Any]) -> QuickChatResult:
    return QuickChatResult(
        answer=output["answer"],
        citations=output["citations"],
        citation_mappings=output["citation_mappings"],
        attempts=output["attempts"],
        tool_calls=output["tool_calls"],
        errors=output["errors"],
    )


def _build_quick_graph(
    *,
    retriever: RetrieveFn,
    answer_generator: AnswerFn,
    retrieve_attempts: RetrieveAttemptsFn | None = None,
):
    async def normalize_node(state: _QuickRunState) -> dict[str, Any]:
        return {"normalized_query": _normalize_query(state["message"])}

    async def retrieve_node(state: _QuickRunState) -> dict[str, Any]:
        all_hits: list[RetrieveHit] = []
        all_attempts: list[RetrievalAttempt] = []
        all_tool_calls: list[ToolCallRecord] = []
        errors: list[dict[str, Any]] = []
        query = state["normalized_query"]

        for kb_id in state["knowledge_base_ids"]:
            try:
                if retrieve_attempts is not None:
                    hits, attempts, tool_calls = await retrieve_attempts(kb_id, query)
                    all_hits.extend(hits)
                    all_attempts.extend(attempts)
                    all_tool_calls.extend(tool_calls)
                else:
                    hits = await _maybe_await(retriever(kb_id, query))
                    all_hits.extend(hits)
            except Exception as exc:
                errors.append(
                    {
                        "knowledge_base_id": str(kb_id),
                        "code": "RETRIEVE_FAILED",
                        "message": str(exc),
                    }
                )

        return {
            "hits": sorted(all_hits, key=lambda hit: hit.score, reverse=True)[:5],
            "attempts": all_attempts,
            "tool_calls": all_tool_calls,
            "errors": errors,
        }

    async def assemble_node(state: _QuickRunState) -> dict[str, Any]:
        context, citations, mappings = _assemble_context(state["hits"])
        return {"context": context, "citations": citations, "citation_mappings": mappings}

    async def generate_node(state: _QuickRunState) -> dict[str, Any]:
        answer = answer_generator(
            state["message"],
            state["context"],
            len(state["hits"]) > 0,
        )
        return {"answer": answer}

    graph = StateGraph(_QuickRunState)
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
