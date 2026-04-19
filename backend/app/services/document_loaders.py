"""按扩展名抽取纯文本（与 build-test-ai.md 附录 A.2 Wave A/B 对齐）。"""

from __future__ import annotations

import io


def extract_text(*, file_name: str, data: bytes) -> str:
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext in ("txt", "md"):
        return data.decode("utf-8", errors="replace")
    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        parts: list[str] = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        return "\n".join(parts)
    if ext == "docx":
        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text)
    raise ValueError(f"暂不支持的文件类型: .{ext or '?'}")
