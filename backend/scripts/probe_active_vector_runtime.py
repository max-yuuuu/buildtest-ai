from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.vector_db_config import VectorDbConfig
from app.services.vector_db_probe import probe


async def main() -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            select(VectorDbConfig)
            .where(
                VectorDbConfig.is_active.is_(True),
                VectorDbConfig.deleted_at.is_(None),
            )
            .order_by(VectorDbConfig.updated_at.desc(), VectorDbConfig.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            print("WARN: no active vector db config found, skip active probe")
            return 0

        tested = await probe(row.db_type, row.connection_string, row.api_key_encrypted)
        if not tested.ok:
            print(f"ERROR: active vector probe failed ({row.db_type}): {tested.message}")
            return 1

        print(
            f"OK: active vector probe passed ({row.db_type}), latency={tested.latency_ms}ms"
        )
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
