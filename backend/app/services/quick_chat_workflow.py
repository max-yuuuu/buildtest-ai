from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field

from app.schemas.knowledge_base import RetrieveHit, RetrieveRequest
from app.services.chat_tool_registry import ToolCallResult, ToolRegistry
from app.services.knowledge_base_service import KnowledgeBaseService


def normalize_query_node(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def rewrite_query_once(query: str) -> str:
    # MVP lightweight rewrite: avoid complex semantic transforms.
    return f"{query} related information"


@dataclass(slots=True)
class RetrievalAttempt:
    attempt: int
    query: str
    hit_count: int
    latency_ms: int


@dataclass(slots=True)
class QuickChatOutput:
    answer: str
    citations: list[dict]
    citation_mappings: list[dict]
    attempts: list[RetrievalAttempt]
    tool_call: ToolCallResult


@dataclass(slots=True)
class QuickChatWorkflow:
    kb_service: KnowledgeBaseService
    tool_registry: ToolRegistry
    mode: str = "quick"

    async def run(self, *, knowledge_base_id: uuid.UUID, message: str) -> QuickChatOutput:
        normalized = normalize_query_node(message)
        first_hits, first_attempt, first_tool_call = await self._retrieve(
            knowledge_base_id=knowledge_base_id,
            query=normalized,
            attempt=1,
        )

        hits = first_hits
        attempts = [first_attempt]
        tool_call = first_tool_call
        if len(hits) == 0:
            rewritten = rewrite_query_once(normalized)
            second_hits, second_attempt, second_tool_call = await self._retrieve(
                knowledge_base_id=knowledge_base_id,
                query=rewritten,
                attempt=2,
            )
            attempts.append(second_attempt)
            hits = second_hits
            tool_call = second_tool_call

        context, citations, citation_mappings = self._assemble_context_node(hits)
        answer = self._generate_answer_node(
            question=message,
            context=context,
            has_hits=len(hits) > 0,
        )
        return QuickChatOutput(
            answer=answer,
            citations=citations,
            citation_mappings=citation_mappings,
            attempts=attempts,
            tool_call=tool_call,
        )

    async def _retrieve(
        self, *, knowledge_base_id: uuid.UUID, query: str, attempt: int
    ) -> tuple[list[RetrieveHit], RetrievalAttempt, ToolCallResult]:
        payload = {"knowledge_base_id": str(knowledge_base_id), "query": query}
        tool_call = await self.tool_registry.call(mode=self.mode, tool_id="api_retrieve", payload=payload)

        started_at = time.perf_counter()
        resp = await self.kb_service.retrieve(knowledge_base_id, RetrieveRequest(query=query))
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return (
            resp.hits,
            RetrievalAttempt(
                attempt=attempt,
                query=query,
                hit_count=len(resp.hits),
                latency_ms=latency_ms,
            ),
            tool_call,
        )

    def _assemble_context_node(self, hits: list[RetrieveHit]) -> tuple[str, list[dict], list[dict]]:
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

    def _generate_answer_node(self, *, question: str, context: str, has_hits: bool) -> str:
        if not has_hits:
            return (
                "未检索到知识库上下文，以下回答可能不准确。"
                f"问题：{question}"
            )
        return f"基于检索结果回答：{question}\n\n{context}"
