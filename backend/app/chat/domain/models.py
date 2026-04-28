from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RetrievalAttempt:
    attempt: int
    query: str
    hit_count: int
    latency_ms: int


@dataclass(slots=True)
class ToolCallRecord:
    tool_id: str
    category: str
    input: dict[str, Any]
    result: dict[str, Any]
    latency_ms: int
    trace_meta: dict[str, Any]


@dataclass(slots=True)
class QuickChatResult:
    answer: str
    citations: list[dict[str, Any]]
    citation_mappings: list[dict[str, Any]]
    attempts: list[RetrievalAttempt]
    tool_call: ToolCallRecord | None = None
