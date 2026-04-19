import pytest

from app.services.document_loaders import extract_text


def test_extract_txt():
    t = extract_text(file_name="a.txt", data=b"hello \xe4\xb8\xad\xe6\x96\x87")
    assert "hello" in t


def test_extract_md():
    t = extract_text(file_name="x.md", data=b"# t\nbody")
    assert "body" in t


def test_extract_unknown():
    with pytest.raises(ValueError, match="不支持"):
        extract_text(file_name="a.xyz", data=b"x")
