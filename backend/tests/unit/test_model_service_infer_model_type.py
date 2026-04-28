from app.services.model_service import _infer_model_type


def test_infer_model_type_embedding_by_embed_token():
    assert _infer_model_type("nomic-embed-text:latest") == "embedding"


def test_infer_model_type_embedding_by_embedding_substring():
    assert _infer_model_type("text-embedding-v3") == "embedding"


def test_infer_model_type_llm_by_default():
    assert _infer_model_type("gpt-4.1-mini") == "llm"
