from app.schemas.provider import mask_api_key


def test_mask_long_key():
    assert mask_api_key("sk-1234567890abcdef") == "sk-1...cdef"


def test_mask_short_key():
    assert mask_api_key("short") == "***"
    assert mask_api_key("12345678") == "***"
