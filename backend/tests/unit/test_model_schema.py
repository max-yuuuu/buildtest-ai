import pytest
from pydantic import ValidationError

from app.schemas.model import ModelCreate, ModelUpdate


def test_llm_model_accepts_no_vector_dim():
    m = ModelCreate(model_id="gpt-4o", model_type="llm", context_window=128000)
    assert m.model_type == "llm"
    assert m.vector_dimension is None


def test_ocr_model_accepts_no_vector_dim():
    m = ModelCreate(model_id="paddleocr-ppocrv5", model_type="ocr")
    assert m.model_type == "ocr"
    assert m.vector_dimension is None


def test_embedding_model_allows_auto_probe_without_vector_dim():
    m = ModelCreate(model_id="text-embedding-3-small", model_type="embedding")
    assert m.model_type == "embedding"
    assert m.vector_dimension is None


def test_embedding_model_ok_with_vector_dim():
    m = ModelCreate(
        model_id="text-embedding-3-small", model_type="embedding", vector_dimension=1536
    )
    assert m.vector_dimension == 1536


def test_unknown_model_type_rejected():
    with pytest.raises(ValidationError):
        ModelCreate(model_id="x", model_type="rerank")  # type: ignore[arg-type]


def test_model_update_partial():
    u = ModelUpdate(context_window=200000)
    assert u.context_window == 200000
    assert u.model_type is None


def test_non_positive_context_window_rejected():
    with pytest.raises(ValidationError):
        ModelCreate(model_id="x", model_type="llm", context_window=0)


def test_embedding_model_accepts_batch_size():
    m = ModelCreate(
        model_id="text-embedding-v4",
        model_type="embedding",
        vector_dimension=1024,
        embedding_batch_size=10,
    )
    assert m.embedding_batch_size == 10


def test_llm_model_rejects_batch_size():
    with pytest.raises(ValidationError) as exc:
        ModelCreate(
            model_id="gpt-4o", model_type="llm", context_window=128000, embedding_batch_size=10
        )
    assert "embedding_batch_size" in str(exc.value)


def test_batch_size_must_be_positive():
    with pytest.raises(ValidationError):
        ModelCreate(
            model_id="text-embedding-v4",
            model_type="embedding",
            vector_dimension=1024,
            embedding_batch_size=0,
        )


def test_batch_size_upper_bound():
    # 2048 是 OpenAI 官方上限,超出此值无合法 provider 支持
    with pytest.raises(ValidationError):
        ModelCreate(
            model_id="text-embedding-v4",
            model_type="embedding",
            vector_dimension=1024,
            embedding_batch_size=5000,
        )
