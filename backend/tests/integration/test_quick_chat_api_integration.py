import json
import uuid

import pytest

from app.schemas.knowledge_base import RetrieveHit, RetrieveResponse

pytestmark = pytest.mark.asyncio


def _payload() -> dict:
    return {
        "mode": "quick",
        "message": "hello",
        "knowledge_base_id": str(uuid.uuid4()),
    }


async def test_quick_chat_hit_first_attempt(client, user_headers, monkeypatch):
    async def fake_retrieve(self, kb_id, body):  # noqa: ANN001
        _ = (self, kb_id)
        return RetrieveResponse(
            strategy_id="naive.v1",
            retrieval_params={},
            hits=[
                RetrieveHit(
                    knowledge_base_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    chunk_index=0,
                    text=f"ctx-{body.query}",
                    score=0.91,
                    source={"section": "S1"},
                )
            ],
        )

    monkeypatch.setattr("app.services.knowledge_base_service.KnowledgeBaseService.retrieve", fake_retrieve)
    res = await client.post("/api/v1/chat", json=_payload(), headers=user_headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body["attempts"]) == 1
    assert body["attempts"][0]["hit_count"] == 1
    assert len(body["citation_mappings"]) == 1


async def test_quick_chat_retry_then_hit(client, user_headers, monkeypatch):
    async def fake_retrieve(self, kb_id, body):  # noqa: ANN001
        _ = (self, kb_id)
        if body.query.endswith("related information"):
            return RetrieveResponse(
                strategy_id="naive.v1",
                retrieval_params={},
                hits=[
                    RetrieveHit(
                        knowledge_base_id=uuid.uuid4(),
                        document_id=uuid.uuid4(),
                        chunk_index=1,
                        text="ctx-rewrite",
                        score=0.88,
                        source={},
                    )
                ],
            )
        return RetrieveResponse(strategy_id="naive.v1", retrieval_params={}, hits=[])

    monkeypatch.setattr("app.services.knowledge_base_service.KnowledgeBaseService.retrieve", fake_retrieve)
    res = await client.post("/api/v1/chat", json=_payload(), headers=user_headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body["attempts"]) == 2
    assert body["attempts"][0]["hit_count"] == 0
    assert body["attempts"][1]["hit_count"] == 1
    assert body["attempts"][0]["query"] != body["attempts"][1]["query"]


async def test_quick_chat_retry_still_empty(client, user_headers, monkeypatch):
    async def fake_retrieve(self, kb_id, body):  # noqa: ANN001
        _ = (self, kb_id, body)
        return RetrieveResponse(strategy_id="naive.v1", retrieval_params={}, hits=[])

    monkeypatch.setattr("app.services.knowledge_base_service.KnowledgeBaseService.retrieve", fake_retrieve)
    res = await client.post("/api/v1/chat", json=_payload(), headers=user_headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body["attempts"]) == 2
    assert "可能不准确" in body["answer"]
    assert body["citation_mappings"] == []


async def test_quick_chat_stream_tool_exception(client, user_headers, monkeypatch):
    async def fake_tool(self, payload):  # noqa: ANN001
        _ = (self, payload)
        raise RuntimeError("tool exploded")

    monkeypatch.setattr("app.services.chat_service.ChatService._api_retrieve_tool", fake_tool)
    res = await client.post("/api/v1/chat/stream", json=_payload(), headers=user_headers)
    assert res.status_code == 200
    chunks = [block for block in res.text.split("\n\n") if block.strip()]
    events: list[dict] = []
    for block in chunks:
        data_line = next((line for line in block.split("\n") if line.startswith("data: ")), None)
        if data_line is None:
            continue
        events.append(json.loads(data_line[6:]))

    assert any(evt["type"] == "error" for evt in events)
    assert not any(evt["type"] == "done" for evt in events)
