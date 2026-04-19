from app.schemas.vector_db import mask_api_key_optional, mask_connection_string


def test_mask_connection_string_url():
    m = mask_connection_string("postgresql://user:secret@db.example.com:5432/mydb")
    assert "db.example.com" in m
    assert "***" in m
    assert "secret" not in m


def test_mask_connection_string_short():
    assert mask_connection_string("short") == "***"


def test_mask_api_key_optional_none():
    assert mask_api_key_optional(None) is None


def test_mask_api_key_optional_value():
    assert mask_api_key_optional("sk-abcdefgh12345678").startswith("sk-a")
    assert mask_api_key_optional("sk-abcdefgh12345678").endswith("5678")
