import uuid
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user_id, get_session
from app.schemas.chat import ChatAcceptedResponse, ChatRequest
from app.services.chat_service import ChatService

router = APIRouter()


def _svc(_: AsyncSession, __: uuid.UUID) -> ChatService:
    return ChatService(_, __)


@router.post("", response_model=ChatAcceptedResponse)
async def chat(
    body: ChatRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ChatAcceptedResponse:
    return await _svc(session, user_id).run(body)


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    service = _svc(session, user_id)

    async def event_gen():
        async for event in service.stream(body):
            yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
