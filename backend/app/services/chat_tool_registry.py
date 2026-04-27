from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from fastapi import HTTPException

ToolCategory = Literal["api", "mcp", "skill", "cli"]
ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class ToolCallResult:
    tool_id: str
    category: ToolCategory
    input: dict[str, Any]
    result: dict[str, Any]
    latency_ms: int
    trace_meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class _ToolDef:
    tool_id: str
    category: ToolCategory
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, _ToolDef] = {}
        self._mode_allowlist: dict[str, set[str]] = {}

    def register(self, tool_id: str, category: ToolCategory, handler: ToolHandler) -> None:
        self._tools[tool_id] = _ToolDef(tool_id=tool_id, category=category, handler=handler)

    def set_mode_allowlist(self, mode: str, tool_ids: set[str]) -> None:
        self._mode_allowlist[mode] = set(tool_ids)

    async def call(self, *, mode: str, tool_id: str, payload: dict[str, Any]) -> ToolCallResult:
        allowlist = self._mode_allowlist.get(mode)
        if allowlist is not None and tool_id not in allowlist:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "TOOL_NOT_ALLOWED",
                    "message": f"tool `{tool_id}` is not allowlisted for mode `{mode}`",
                },
            )

        tool = self._tools.get(tool_id)
        if tool is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "TOOL_NOT_FOUND", "message": f"tool `{tool_id}` is not registered"},
            )

        started_at = time.perf_counter()
        result = await tool.handler(payload)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return ToolCallResult(
            tool_id=tool.tool_id,
            category=tool.category,
            input=payload,
            result=result,
            latency_ms=latency_ms,
            trace_meta={"mode": mode},
        )
