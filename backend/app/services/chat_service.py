import uuid
from datetime import UTC, datetime
from typing import AsyncIterator

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import ChatFacade
from app.chat.domain import ModeNotImplementedError
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
                    "attempt": a.attempt,
                    "query": a.query,
                    "hit_count": a.hit_count,
                    "latency_ms": a.latency_ms,
                }
                for a in result.attempts
            ],
        )

    async def stream(self, body: ChatRequest) -> AsyncIterator[dict]:
        if body.mode in {"agent", "data"}:
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
        started_at = datetime.now(UTC)

        yield self._event("start", trace_id, {"run_id": run_id})
        yield self._event(
            "step",
            trace_id,
            {"id": "step_retrieve", "name": "retrieve", "status": "running"},
        )

        try:
            result = await self._run_quick(body)
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
            return
        except Exception as exc:
            yield self._event(
                "error",
                trace_id,
                {"code": "CHAT_INTERNAL_ERROR", "message": str(exc), "retryable": False},
            )
            return

        yield self._event(
            "step",
            trace_id,
            {
                "id": "step_retrieve",
                "name": "retrieve",
                "status": "completed",
                "attempts": [
                    {
                        "attempt": a.attempt,
                        "query": a.query,
                        "hit_count": a.hit_count,
                        "latency_ms": a.latency_ms,
                    }
                    for a in result.attempts
                ],
            },
        )
        yield self._event(
            "step",
            trace_id,
            {"id": "step_generate", "name": "generate", "status": "running"},
        )

        for token in self._iter_tokens(result.answer):
            yield self._event("token", trace_id, {"text": token})

        for citation in result.citations:
            yield self._event(
                "citation",
                trace_id,
                {
                    "id": citation.get("citation_id"),
                    "doc_id": citation.get("document_id"),
                    "chunk_id": citation.get("chunk_index"),
                    "title": citation.get("source", {}).get("section"),
                    "snippet": "",
                    "score": citation.get("score"),
                },
            )

        yield self._event(
            "step",
            trace_id,
            {"id": "step_generate", "name": "generate", "status": "completed"},
        )
        elapsed_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        yield self._event(
            "done",
            trace_id,
            {
                "latency_ms": elapsed_ms,
                "attempts": [
                    {
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
        return await facade.run_quick(knowledge_base_id=body.knowledge_base_id, message=body.message)

    async def _run_by_mode(self, body: ChatRequest):
        kb_service = KnowledgeBaseService(self._session, self._user_id)
        registry = ToolRegistry()
        registry.register("api_retrieve", "api", self._api_retrieve_tool)
        registry.set_mode_allowlist("quick", {"api_retrieve"})
        facade = ChatFacade(kb_service=kb_service, tool_registry=registry)

        try:
            if body.mode == "quick":
                return await facade.run_quick(
                    knowledge_base_id=body.knowledge_base_id, message=body.message
                )
            if body.mode == "agent":
                return await facade.run_agent(
                    knowledge_base_id=body.knowledge_base_id, message=body.message
                )
            if body.mode == "data":
                return await facade.run_data(
                    knowledge_base_id=body.knowledge_base_id, message=body.message
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

    async def _api_retrieve_tool(self, payload: dict) -> dict:
        return {"ok": True, "query": payload.get("query"), "kb_id": payload.get("knowledge_base_id")}

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
