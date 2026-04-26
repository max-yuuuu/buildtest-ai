from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def check_chunk_metadata_columns(engine: AsyncEngine) -> bool:
    """Check if kb_vector_chunks has new metadata columns.

    Returns True when both columns exist; False when schema is outdated or
    cannot be checked safely.
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'kb_vector_chunks'
                      AND column_name IN ('token_length', 'source_metadata')
                    """
                )
            )
            cols = {row[0] for row in result.fetchall()}
            ready = {"token_length", "source_metadata"}.issubset(cols)
            if not ready:
                logger.warning(
                    "Detected outdated schema for kb_vector_chunks. "
                    "Please run `alembic upgrade head`."
                )
            return ready
    except Exception as exc:  # noqa: BLE001
        # SQLite tests and some environments may not expose information_schema.
        logger.info("Skip chunk metadata schema check: %s", exc)
        return False
