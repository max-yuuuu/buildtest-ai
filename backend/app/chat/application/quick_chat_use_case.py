from __future__ import annotations

import re
import uuid

from app.schemas.knowledge_base import RetrieveHit

from app.chat.domain.models import QuickChatResult, RetrievalAttempt
from app.chat.domain.ports import AnswerGeneratorPort, KnowledgeRetrieverPort, ToolInvokerPort


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def rewrite_query_once(query: str) -> str:
    return f"{query} related information"


class RunQuickChatUseCase:
    def __init__(
        self,
        *,
        retriever: KnowledgeRetrieverPort,
        tool_invoker: ToolInvokerPort,
        answer_generator: AnswerGeneratorPort,
        mode: str = "quick",
    ) -> None:
        self._retriever = retriever
        self._tool_invoker = tool_invoker
        self._answer_generator = answer_generator
        self._mode = mode

    async def execute(self, *, knowledge_base_ids: list[uuid.UUID], message: str) -> QuickChatResult:
        normalized = normalize_query(message)
        all_hits: list[RetrieveHit] = []
        all_attempts: list[RetrievalAttempt] = []
        all_tool_calls: list[object] = []
        errors: list[dict] = []

        for knowledge_base_id in knowledge_base_ids:
            try:
                hits, attempts, tool_calls = await self._retrieve_attempts(
                    knowledge_base_id=knowledge_base_id,
                    normalized_query=normalized,
                )
                all_hits.extend(hits)
                all_attempts.extend(attempts)
                all_tool_calls.extend(tool_calls)
            except Exception as exc:
                errors.append(
                    {
                        "knowledge_base_id": str(knowledge_base_id),
                        "code": "RETRIEVE_FAILED",
                        "message": str(exc),
                    }
                )

        hits = sorted(all_hits, key=lambda hit: hit.score, reverse=True)[:5]
        context, citations, citation_mappings = self._assemble_context(hits)
        answer = self._answer_generator.generate(question=message, context=context, has_hits=len(hits) > 0)
        return QuickChatResult(
            answer=answer,
            citations=citations,
            citation_mappings=citation_mappings,
            attempts=all_attempts,
            tool_calls=all_tool_calls,
            errors=errors,
        )

    async def _retrieve_attempts(
        self, *, knowledge_base_id: uuid.UUID, normalized_query: str
    ) -> tuple[list[RetrieveHit], list[RetrievalAttempt], list[object]]:
        first_hits, first_attempt, first_tool = await self._retrieve_once(
            knowledge_base_id=knowledge_base_id,
            query=normalized_query,
            attempt=1,
        )
        if first_hits:
            return first_hits, [first_attempt], [first_tool]

        rewritten = rewrite_query_once(normalized_query)
        second_hits, second_attempt, second_tool = await self._retrieve_once(
            knowledge_base_id=knowledge_base_id,
            query=rewritten,
            attempt=2,
        )
        return second_hits, [first_attempt, second_attempt], [first_tool, second_tool]

    async def _retrieve_once(
        self, *, knowledge_base_id: uuid.UUID, query: str, attempt: int
    ) -> tuple[list[RetrieveHit], RetrievalAttempt, object]:
        tool_call = await self._tool_invoker.invoke_retrieve_tool(
            mode=self._mode, knowledge_base_id=knowledge_base_id, query=query
        )
        hits, latency_ms = await self._retriever.retrieve(knowledge_base_id=knowledge_base_id, query=query)
        attempt_record = RetrievalAttempt(
            knowledge_base_id=str(knowledge_base_id),
            attempt=attempt,
            query=query,
            hit_count=len(hits),
            latency_ms=latency_ms,
        )
        return hits, attempt_record, tool_call

    @staticmethod
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
