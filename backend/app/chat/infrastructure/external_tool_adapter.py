from __future__ import annotations

import uuid
from typing import Any, Protocol


class ExternalToolAdapter(Protocol):
    async def call(self, *, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class MockExternalToolAdapter:
    async def call(self, *, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "tool_name": tool_name,
            "payload": payload,
            "trace_id": f"mock-{uuid.uuid4().hex[:12]}",
        }

