import base64

from app.api.v1.deps import _decode_x_user_name


def _bff_encode(name: str) -> str:
    """与 frontend route 中算法一致，用于断言解码。"""
    raw = base64.urlsafe_b64encode(name.encode("utf-8")).decode("ascii").rstrip("=")
    return f"b64.{raw}"


def test_decode_plain_ascii_unchanged() -> None:
    assert _decode_x_user_name("Test User") == "Test User"
    assert _decode_x_user_name("A") == "A"


def test_decode_none_and_empty() -> None:
    assert _decode_x_user_name(None) is None
    assert _decode_x_user_name("") is None


def test_decode_b64_utf8_roundtrip() -> None:
    for name in ("", "Alice", "张三", "Müller", "emoji🔑"):
        assert _decode_x_user_name(_bff_encode(name)) == name


def test_decode_b64_empty_payload() -> None:
    assert _decode_x_user_name("b64.") == ""
