"""按扩展名抽取纯文本（与 build-test-ai.md 附录 A.2 Wave A/B 对齐）。"""

from __future__ import annotations

import io
import subprocess
import tempfile
import zipfile
from pathlib import Path


def _extract_doc_via_libreoffice(data: bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.doc"
        src.write_bytes(data)
        try:
            subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to",
                    "txt:Text (encoded):UTF8",
                    "--outdir",
                    tmp,
                    str(src),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except FileNotFoundError as e:
            raise RuntimeError("未检测到 libreoffice(soffice),镜像需安装 libreoffice-writer") from e
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="replace")[:500] if e.stderr else ""
            raise RuntimeError(f"libreoffice 转换失败: {stderr}") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("libreoffice 转换超时(60s)") from e
        out = Path(tmp) / "in.txt"
        if not out.is_file():
            raise RuntimeError("libreoffice 未生成输出文件，可能源文件已损坏")
        return out.read_text(encoding="utf-8", errors="replace")


def extract_text(*, file_name: str, data: bytes) -> str:
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext in ("txt", "md"):
        return data.decode("utf-8", errors="replace")
    if ext == "pdf":
        import pdfplumber

        parts: list[str] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
        return "\n".join(parts)
    if ext == "docx":
        from docx import Document

        try:
            doc = Document(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise ValueError(
                "文件不是合法的 .docx(可能是 .doc 旧格式或文件已损坏)，"
                "请在 Word 中另存为 .docx 后重试"
            ) from e
        return "\n".join(p.text for p in doc.paragraphs if p.text)
    if ext == "doc":
        return _extract_doc_via_libreoffice(data)
    raise ValueError(f"暂不支持的文件类型: .{ext or '?'}")
