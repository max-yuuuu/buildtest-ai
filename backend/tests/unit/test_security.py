import pytest

from app.core.security import EncryptedString, decrypt, encrypt


@pytest.mark.asyncio
async def test_encrypt_decrypt_roundtrip():
    plain = "sk-test-secret-123"
    token = encrypt(plain)
    assert token != plain
    assert decrypt(token) == plain


@pytest.mark.asyncio
async def test_decrypt_invalid_raises():
    with pytest.raises(ValueError):
        decrypt("not-a-valid-token")


def test_encrypted_string_bind_and_result():
    t = EncryptedString()
    token = t.process_bind_param("hello", dialect=None)
    assert token != "hello"
    assert t.process_result_value(token, dialect=None) == "hello"
    assert t.process_bind_param(None, dialect=None) is None
    assert t.process_result_value(None, dialect=None) is None
