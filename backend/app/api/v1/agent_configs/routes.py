import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user_id, get_session
from app.schemas.model_config import AgentModelConfigRead, AgentModelConfigUpsert
from app.services.model_config_service import ModelConfigService

router = APIRouter()


@router.get("", response_model=list[AgentModelConfigRead])
async def list_agent_configs(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[AgentModelConfigRead]:
    return await ModelConfigService(session, user_id).list_agent_configs()


@router.put("/{agent_id}", response_model=AgentModelConfigRead)
async def upsert_agent_config(
    agent_id: str,
    payload: AgentModelConfigUpsert,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> AgentModelConfigRead:
    return await ModelConfigService(session, user_id).upsert_agent_config(agent_id, payload)
