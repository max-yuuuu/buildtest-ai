"""按扩展名抽取纯文本（与 build-test-ai.md 附录 A.2 Wave A/B 对齐）。"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractedSegment:
    text: str
    page: int | None = None


def detect_input_kind(file_name: str) -> str:
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext in ("txt", "md"):
        return "text"
    if ext == "pdf":
        return "pdf"
    if ext in ("doc", "docx"):
        return "office"
    return "unknown"


def infer_normalization_mode(file_name: str) -> str:
    kind = detect_input_kind(file_name)
    if kind == "text":
        return "text_to_blocks"
    if kind == "pdf":
        return "pdf_to_pages_blocks"
    if kind == "office":
        return "office_to_text"
    return "unknown"


def infer_section_title(text: str) -> str | None:
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip() or None
        if re.match(r"^(\d+(\.\d+)*|[一二三四五六七八九十]+)[\.\、\s]", line):
            return line
    return None


def _extract_doc_via_libreoffice(data: bytes) -> str:
    soffice_cmd = (
        shutil.which("soffice")
        or shutil.which("libreoffice")
        or "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    )
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.doc"
        src.write_bytes(data)
        try:
            subprocess.run(
                [
                    soffice_cmd,
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
            raise RuntimeError(
                "未检测到 libreoffice(soffice)。"
                "若运行在 Docker 容器内，请安装 libreoffice-writer；"
                "若运行在宿主机，请先安装 LibreOffice 并确保 soffice 在 PATH 中。"
            ) from e
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


def extract_segments(*, file_name: str, data: bytes) -> list[ExtractedSegment]:
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext == "pdf":
        import pdfplumber

        segments: list[ExtractedSegment] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                t = page.extract_text()
                if t and t.strip():
                    segments.append(ExtractedSegment(text=t, page=idx))
        return segments
    text = extract_text(file_name=file_name, data=data)
    if not text.strip():
        return []
    return [ExtractedSegment(text=text, page=None)]
