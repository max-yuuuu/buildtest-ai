from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.services.vector_connector import SearchHit, VectorDbConnector


@dataclass(frozen=True)
class RetrievalExecutionSnapshot:
    strategy_id: str
    retrieval_params: dict


class RetrievalStrategy(Protocol):
    strategy_id: str

    async def retrieve(
        self,
        *,
        connector: VectorDbConnector,
        collection: str,
        knowledge_base_id: uuid.UUID,
        query_vector: list[float],
        top_k: int,
        similarity_threshold: float | None,
    ) -> list[SearchHit]: ...


class NaiveV1RetrievalStrategy:
    strategy_id = "naive.v1"

    async def retrieve(
        self,
        *,
        connector: VectorDbConnector,
        collection: str,
        knowledge_base_id: uuid.UUID,
        query_vector: list[float],
        top_k: int,
        similarity_threshold: float | None,
    ) -> list[SearchHit]:
        return await connector.search(
            collection=collection,
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=similarity_threshold,
        )


_STRATEGIES: dict[str, RetrievalStrategy] = {
    NaiveV1RetrievalStrategy.strategy_id: NaiveV1RetrievalStrategy()
}


def list_retrieval_strategies() -> list[str]:
    return sorted(_STRATEGIES.keys())


def get_retrieval_strategy(strategy_id: str) -> RetrievalStrategy:
    strategy = _STRATEGIES.get(strategy_id)
    if strategy is None:
        supported = ", ".join(list_retrieval_strategies())
        raise ValueError(f"unsupported strategy_id: {strategy_id}; supported: {supported}")
    return strategy
