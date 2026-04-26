from app.services.embedding_client import _normalize_openai_compatible_base_url


def test_normalize_base_url_defaults_to_openai_v1():
    assert _normalize_openai_compatible_base_url(None) == "https://api.openai.com/v1"


def test_normalize_base_url_strips_embeddings_endpoint():
    assert (
        _normalize_openai_compatible_base_url("https://openrouter.ai/api/v1/embeddings")
        == "https://openrouter.ai/api/v1"
    )
