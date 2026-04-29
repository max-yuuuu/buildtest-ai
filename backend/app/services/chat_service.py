import uuid
from datetime import UTC, datetime
from typing import AsyncIterator

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import ChatFacade
from app.chat.domain import ModeNotImplementedError
from app.chat.domain.models import RetrievalAttempt, ToolCallRecord
from app.chat.graphs.quick_chat_graph import astream_quick_graph
from app.chat.infrastructure.adapters import (
    KnowledgeBaseRetrieverAdapter,
    QuickModeToolInvokerAdapter,
    TemplateAnswerGeneratorAdapter,
)
from app.chat.infrastructure.llm_adapter import LLMAdapter, ResolvedModel
from app.chat.infrastructure.model_config_source import DbModelConfigSource
from app.chat.application.quick_chat_use_case import rewrite_query_once
from app.schemas.knowledge_base import RetrieveHit
from app.schemas.chat import ChatAcceptedResponse, ChatRequest
from app.services.chat_tool_registry import ToolRegistry
from app.services.knowledge_base_service import KnowledgeBaseService


class ChatService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def run(self, body: ChatRequest) -> ChatAcceptedResponse:
        result = await self._run_by_mode(body)
        return ChatAcceptedResponse(
            mode=body.mode,
            answer=result.answer,
            citations=result.citations,
            citation_mappings=result.citation_mappings,
            attempts=[
                {
                    "knowledge_base_id": a.knowledge_base_id,
                    "attempt": a.attempt,
                    "query": a.query,
                    "hit_count": a.hit_count,
                    "latency_ms": a.latency_ms,
                }
                for a in result.attempts
            ],
        )

    async def stream(self, body: ChatRequest) -> AsyncIterator[dict]:
        if body.mode == "data":
            trace_id = f"trc_{uuid.uuid4().hex[:12]}"
            yield self._event(
                "error",
                trace_id,
                {
                    "code": "MODE_NOT_IMPLEMENTED",
                    "message": f"chat mode `{body.mode}` is not implemented in MVP",
                    "retryable": False,
                },
            )
            return

        trace_id = f"trc_{uuid.uuid4().hex[:12]}"
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(UTC)
        selected_model = await self._resolve_model_for_request(body)

        yield self._event(
            "start",
            trace_id,
            {
                "run_id": run_id,
                "message_id": message_id,
                "model": {
                    "provider": selected_model.provider,
                    "model_name": selected_model.model_name,
                },
            },
        )
        try:
            stream_fn = (
                self._stream_agent_graph_events if body.mode == "agent" else self._stream_quick_graph_events
            )
            async for graph_evt in stream_fn(body):
                if graph_evt["type"] == "step":
                    yield self._event(
                        "step",
                        trace_id,
                        {
                            "id": f"step_{graph_evt['name']}",
                            "name": graph_evt["name"],
                            "status": graph_evt["status"],
                            "message_id": message_id,
                        },
                    )
                    continue
                result = graph_evt["result"]
                break
            else:
                raise RuntimeError("graph did not return result")
        except HTTPException as exc:
            detail = exc.detail
            if isinstance(detail, dict):
                code = detail.get("code", f"HTTP_{exc.status_code}")
                message = detail.get("message", str(detail))
            else:
                code = f"HTTP_{exc.status_code}"
                message = str(detail)
            yield self._event(
                "error",
                trace_id,
                {"code": code, "message": message, "retryable": False},
            )
            yield self._event("done", trace_id, {"message_id": message_id, "latency_ms": 0})
            return
        except Exception as exc:
            yield self._event(
                "error",
                trace_id,
                {"code": "CHAT_INTERNAL_ERROR", "message": str(exc), "retryable": False},
            )
            yield self._event("done", trace_id, {"message_id": message_id, "latency_ms": 0})
            return

        for tool_call in result.tool_calls:
            yield self._event(
                "tool-call",
                trace_id,
                {
                    "message_id": message_id,
                    "tool_call_id": tool_call.trace_meta.get("tool_call_id"),
                    "tool_name": tool_call.tool_id,
                    "input": tool_call.input,
                },
            )
            yield self._event(
                "tool-result",
                trace_id,
                {
                    "message_id": message_id,
                    "tool_call_id": tool_call.trace_meta.get("tool_call_id"),
                    "tool_name": tool_call.tool_id,
                    "output": tool_call.result,
                },
            )

        for kb_error in result.errors:
            yield self._event("error", trace_id, {"message_id": message_id, **kb_error})
        for token in self._iter_tokens(result.answer):
            yield self._event("text-delta", trace_id, {"text": token, "message_id": message_id})

        for citation in result.citations:
            source = citation.get("source")
            title = source.section if isinstance(source, object) and hasattr(source, "section") else None
            yield self._event(
                "citation",
                trace_id,
                {
                    "id": citation.get("citation_id"),
                    "message_id": message_id,
                    "knowledge_base_id": self._citation_kb_id(citation, result.citation_mappings),
                    "doc_id": citation.get("document_id"),
                    "chunk_id": citation.get("chunk_index"),
                    "title": title,
                    "snippet": "",
                    "score": citation.get("score"),
                },
            )

        elapsed_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        yield self._event(
            "done",
            trace_id,
            {
                "message_id": message_id,
                "latency_ms": elapsed_ms,
                "attempts": [
                    {
                        "knowledge_base_id": a.knowledge_base_id,
                        "attempt": a.attempt,
                        "query": a.query,
                        "hit_count": a.hit_count,
                        "latency_ms": a.latency_ms,
                    }
                    for a in result.attempts
                ],
                "citation_mappings": result.citation_mappings,
            },
        )

    async def _run_quick(self, body: ChatRequest):
        if body.mode != "quick":
            raise HTTPException(
                status_code=500,
                detail={"code": "CHAT_MODE_MISMATCH", "message": "expected quick mode"},
            )
        kb_service = KnowledgeBaseService(self._session, self._user_id)
        registry = ToolRegistry()
        registry.register("api_retrieve", "api", self._api_retrieve_tool)
        registry.set_mode_allowlist("quick", {"api_retrieve"})
        facade = ChatFacade(kb_service=kb_service, tool_registry=registry)
        return await facade.run_quick(knowledge_base_ids=body.knowledge_base_ids, message=body.message)

    async def _stream_quick_graph_events(self, body: ChatRequest) -> AsyncIterator[dict]:
        kb_service = KnowledgeBaseService(self._session, self._user_id)
        registry = ToolRegistry()
        registry.register("api_retrieve", "api", self._api_retrieve_tool)
        registry.set_mode_allowlist("quick", {"api_retrieve"})

        retriever = KnowledgeBaseRetrieverAdapter(kb_service)
        tool_invoker = QuickModeToolInvokerAdapter(registry)
        answer_generator = TemplateAnswerGeneratorAdapter()

        async def retrieve_attempts(
            knowledge_base_id: uuid.UUID,
            normalized_query: str,
        ) -> tuple[list[RetrieveHit], list[RetrievalAttempt], list[ToolCallRecord]]:
            first_hits, first_attempt, first_tool = await self._retrieve_once_for_stream(
                retriever=retriever,
                tool_invoker=tool_invoker,
                knowledge_base_id=knowledge_base_id,
                query=normalized_query,
                attempt=1,
            )
            if first_hits:
                return first_hits, [first_attempt], [first_tool]

            rewritten = rewrite_query_once(normalized_query)
            second_hits, second_attempt, second_tool = await self._retrieve_once_for_stream(
                retriever=retriever,
                tool_invoker=tool_invoker,
                knowledge_base_id=knowledge_base_id,
                query=rewritten,
                attempt=2,
            )
            return second_hits, [first_attempt, second_attempt], [first_tool, second_tool]

        async for graph_evt in astream_quick_graph(
            message=body.message,
            knowledge_base_ids=body.knowledge_base_ids,
            retriever=lambda _kb_id, _query: [],
            answer_generator=lambda question, context, has_hits: answer_generator.generate(
                question=question,
                context=context,
                has_hits=has_hits,
            ),
            retrieve_attempts=retrieve_attempts,
        ):
            yield graph_evt

    async def _stream_agent_graph_events(self, body: ChatRequest) -> AsyncIterator[dict]:
        kb_service = KnowledgeBaseService(self._session, self._user_id)
        registry = ToolRegistry()
        registry.register("api_retrieve", "api", self._api_retrieve_tool)
        registry.set_mode_allowlist("quick", {"api_retrieve"})
        registry.set_mode_allowlist("agent", {"api_retrieve"})

        facade = ChatFacade(kb_service=kb_service, tool_registry=registry)
        # agent 目前使用同一套模板生成器与检索策略（LangGraph 控制循环）
        from app.chat.graphs.agent_chat_graph import astream_agent_graph  # local import to avoid cycles
        from app.chat.infrastructure.adapters import (
            KnowledgeBaseRetrieverAdapter,
            QuickModeToolInvokerAdapter,
            TemplateAnswerGeneratorAdapter,
        )

        retriever = KnowledgeBaseRetrieverAdapter(kb_service)
        tool_invoker = QuickModeToolInvokerAdapter(registry)
        answer_generator = TemplateAnswerGeneratorAdapter()

        async for graph_evt in astream_agent_graph(
            message=body.message,
            knowledge_base_ids=body.knowledge_base_ids,
            retriever=retriever,
            tool_invoker=tool_invoker,
            answer_generator=answer_generator,
            max_iters=3,
        ):
            yield graph_evt

    async def _retrieve_once_for_stream(
        self,
        *,
        retriever: KnowledgeBaseRetrieverAdapter,
        tool_invoker: QuickModeToolInvokerAdapter,
        knowledge_base_id: uuid.UUID,
        query: str,
        attempt: int,
    ) -> tuple[list[RetrieveHit], RetrievalAttempt, ToolCallRecord]:
        tool_call = await tool_invoker.invoke_retrieve_tool(
            mode="quick",
            knowledge_base_id=knowledge_base_id,
            query=query,
        )
        hits, latency_ms = await retriever.retrieve(knowledge_base_id=knowledge_base_id, query=query)
        attempt_record = RetrievalAttempt(
            knowledge_base_id=str(knowledge_base_id),
            attempt=attempt,
            query=query,
            hit_count=len(hits),
            latency_ms=latency_ms,
        )
        return hits, attempt_record, tool_call

    async def _run_by_mode(self, body: ChatRequest):
        _ = await self._resolve_model_for_request(body)
        kb_service = KnowledgeBaseService(self._session, self._user_id)
        registry = ToolRegistry()
        registry.register("api_retrieve", "api", self._api_retrieve_tool)
        registry.set_mode_allowlist("quick", {"api_retrieve"})
        facade = ChatFacade(kb_service=kb_service, tool_registry=registry)

        try:
            if body.mode == "quick":
                return await facade.run_quick(
                    knowledge_base_ids=body.knowledge_base_ids, message=body.message
                )
            if body.mode == "agent":
                return await facade.run_agent(
                    knowledge_base_ids=body.knowledge_base_ids, message=body.message
                )
            if body.mode == "data":
                return await facade.run_data(
                    knowledge_base_ids=body.knowledge_base_ids, message=body.message
                )
        except ModeNotImplementedError as exc:
            raise HTTPException(
                status_code=501,
                detail={"code": exc.code, "message": exc.message},
            ) from exc

        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_MODE", "message": f"invalid chat mode `{body.mode}`"},
        )

    async def _resolve_model_for_request(self, body: ChatRequest) -> ResolvedModel:
        # unit tests stub ChatService with session=None; keep deterministic default in that case.
        if self._session is None:
            return ResolvedModel(provider="openai", model_name="default")
        source = DbModelConfigSource(session=self._session, user_id=self._user_id)
        adapter = LLMAdapter(config_source=source)
        return await adapter.resolve(
            mode=body.mode,
            user_id=self._user_id,
            knowledge_base_ids=body.knowledge_base_ids,
        )

    async def _api_retrieve_tool(self, payload: dict) -> dict:
        return {
            "ok": True,
            "query": payload.get("query"),
            "knowledge_base_id": payload.get("knowledge_base_id"),
        }

    @staticmethod
    def _event(event_type: str, trace_id: str, payload: dict) -> dict:
        return {
            "type": event_type,
            "ts": datetime.now(UTC).isoformat(),
            "trace_id": trace_id,
            **payload,
        }

    @staticmethod
    def _iter_tokens(text: str) -> list[str]:
        if not text:
            return []
        return [f"{part} " for part in text.split()]

    @staticmethod
    def _citation_kb_id(citation: dict, citation_mappings: list[dict]) -> str | None:
        citation_id = citation.get("citation_id")
        for mapping in citation_mappings:
            if mapping.get("citation_id") == citation_id:
                return mapping.get("knowledge_base_id")
        return None
