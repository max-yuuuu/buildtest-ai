import uuid

import pytest

from app.chat.infrastructure.model_config_source import DbModelConfigSource
from app.models.knowledge_base import KnowledgeBase
from app.models.model import Model
from app.models.model_config import AgentModelConfig, KnowledgeBaseModelConfig
from app.models.provider import Provider
from app.models.user import User
from app.models.vector_db_config import VectorDbConfig


pytestmark = pytest.mark.asyncio


async def _seed_base_graph(session):
    user = User(external_id=f"github:{uuid.uuid4()}", email="u@example.com", name="u")
    session.add(user)
    await session.flush()

    vector_db = VectorDbConfig(
        user_id=user.id,
        name="vdb",
        db_type="postgres_pgvector",
        connection_string="postgresql://x:y@127.0.0.1:9/db",
        connection_string_mask="postgresql://***",
        api_key_encrypted="secret",
        api_key_mask="***",
        is_active=False,
    )
    session.add(vector_db)
    await session.flush()

    provider = Provider(
        user_id=user.id,
        name="p",
        provider_type="openai",
        api_key_encrypted="sk-test",
        api_key_mask="sk-****",
        is_active=True,
    )
    session.add(provider)
    await session.flush()
    return user, vector_db, provider


async def test_db_model_config_source_prefers_kb_llm_for_quick(session):
    user, vector_db, provider = await _seed_base_graph(session)
    embedding_model = Model(
        provider_id=provider.id,
        model_id="text-embedding-3-small",
        model_type="embedding",
        vector_dimension=1536,
    )
    fallback_llm = Model(provider_id=provider.id, model_id="gpt-4o-mini", model_type="llm")
    kb_llm = Model(provider_id=provider.id, model_id="gpt-4o", model_type="llm")
    session.add_all([embedding_model, fallback_llm, kb_llm])
    await session.flush()

    kb = KnowledgeBase(
        user_id=user.id,
        name="kb",
        vector_db_config_id=vector_db.id,
        collection_name="kb_1",
        embedding_model_id=embedding_model.id,
        embedding_dimension=1536,
        retrieval_config={},
    )
    session.add(kb)
    await session.flush()

    session.add(
        KnowledgeBaseModelConfig(
            knowledge_base_id=kb.id,
            purpose="llm",
            model_id=kb_llm.id,
        )
    )
    await session.commit()

    source = DbModelConfigSource(session=session, user_id=user.id)
    resolved = await source.get_llm_model_for_mode(
        user_id=user.id,
        mode="quick",
        knowledge_base_ids=[kb.id],
    )
    assert resolved is not None
    assert resolved.provider == "openai"
    assert resolved.model_name == "gpt-4o"


async def test_db_model_config_source_uses_agent_config_then_fallback(session):
    user, _vector_db, provider = await _seed_base_graph(session)
    fallback_llm = Model(provider_id=provider.id, model_id="gpt-4o-mini", model_type="llm")
    agent_llm = Model(provider_id=provider.id, model_id="claude-3-7", model_type="llm")
    session.add_all([fallback_llm, agent_llm])
    await session.flush()

    session.add(AgentModelConfig(user_id=user.id, agent_id="smart_agent", model_id=agent_llm.id))
    await session.commit()

    source = DbModelConfigSource(session=session, user_id=user.id)
    resolved_agent = await source.get_llm_model_for_mode(user_id=user.id, mode="agent")
    assert resolved_agent is not None
    assert resolved_agent.model_name == "claude-3-7"

    # quick without kb config falls back to first active llm.
    resolved_quick = await source.get_llm_model_for_mode(user_id=user.id, mode="quick")
    assert resolved_quick is not None
    assert resolved_quick.model_name == "gpt-4o-mini"
