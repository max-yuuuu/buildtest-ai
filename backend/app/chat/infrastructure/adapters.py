from __future__ import annotations

import time
import uuid

from app.chat.domain.models import ToolCallRecord
from app.chat.domain.ports import AnswerGeneratorPort, KnowledgeRetrieverPort, ToolInvokerPort
from app.schemas.knowledge_base import RetrieveRequest
from app.services.chat_tool_registry import ToolRegistry
from app.services.knowledge_base_service import KnowledgeBaseService


class KnowledgeBaseRetrieverAdapter(KnowledgeRetrieverPort):
    def __init__(self, kb_service: KnowledgeBaseService) -> None:
        self._kb_service = kb_service

    async def retrieve(
        self, *, knowledge_base_id: uuid.UUID, query: str
    ) -> tuple[list, int]:
        started_at = time.perf_counter()
        resp = await self._kb_service.retrieve(knowledge_base_id, RetrieveRequest(query=query))
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return resp.hits, latency_ms


class QuickModeToolInvokerAdapter(ToolInvokerPort):
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry

    async def invoke_retrieve_tool(
        self, *, mode: str, knowledge_base_id: uuid.UUID, query: str
    ) -> ToolCallRecord:
        payload = {"knowledge_base_id": str(knowledge_base_id), "query": query}
        tool_call = await self._tool_registry.call(mode=mode, tool_id="api_retrieve", payload=payload)
        return ToolCallRecord(
            tool_id=tool_call.tool_id,
            category=tool_call.category,
            input=tool_call.input,
            result=tool_call.result,
            latency_ms=tool_call.latency_ms,
            trace_meta={
                **tool_call.trace_meta,
                "tool_call_id": f"tool_{uuid.uuid4().hex[:12]}",
            },
        )


class TemplateAnswerGeneratorAdapter(AnswerGeneratorPort):
    def generate(self, *, question: str, context: str, has_hits: bool) -> str:
        if not has_hits:
            return "未检索到知识库上下文，以下回答可能不准确。" f"问题：{question}"
        return f"基于检索结果回答：{question}\n\n{context}"
