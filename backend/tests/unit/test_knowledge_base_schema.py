import uuid

import pytest
from pydantic import ValidationError

from app.schemas.knowledge_base import KnowledgeBaseCreate


def test_kb_create_overlap_invalid():
    with pytest.raises(ValidationError):
        KnowledgeBaseCreate(
            name="n",
            vector_db_config_id=uuid.uuid4(),
            embedding_model_id=uuid.uuid4(),
            chunk_size=100,
            chunk_overlap=100,
        )


def test_kb_create_ok():
    k = KnowledgeBaseCreate(
        name="n",
        vector_db_config_id=uuid.uuid4(),
        embedding_model_id=uuid.uuid4(),
        chunk_size=200,
        chunk_overlap=50,
    )
    assert k.chunk_overlap == 50
