from __future__ import annotations

from typing import Any, TypedDict


class QuickGraphState(TypedDict):
    message: str
    knowledge_base_ids: list[str]
    attempts: list[dict[str, Any]]
    hits: list[dict[str, Any]]
    events: list[dict[str, Any]]
