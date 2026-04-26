import io
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _provider_id(client, headers):
    r = await client.post(
        "/api/v1/providers",
        json={"name": "kbp", "provider_type": "openai", "api_key": "sk-abcdefgh12345678"},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


async def _embedding_model_id(client, headers, pid):
    r = await client.post(
        f"/api/v1/providers/{pid}/models",
        json={
            "model_id": "text-embedding-3-small",
            "model_type": "embedding",
            "vector_dimension": 4,
        },
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


async def _vector_db_id(client, headers):
    r = await client.post(
        "/api/v1/vector-dbs",
        json={
            "name": "pg-local",
            "db_type": "postgres_pgvector",
            "connection_string": "postgresql://x:y@127.0.0.1:9/db",
            "is_active": True,
        },
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


@pytest.fixture
def fake_embed(monkeypatch):
    async def _embed(*, provider_type, api_key, base_url, model_id, texts):
        _ = (provider_type, api_key, base_url, model_id)
        return [[0.5, 0.5, 0.5, 0.5] for _ in texts]

    monkeypatch.setattr(
        "app.services.knowledge_base_service.embedding_client.embed_texts",
        _embed,
    )


async def test_kb_crud_and_upload_retrieve(client, user_headers, fake_embed, monkeypatch):
    import pathlib
    from types import SimpleNamespace

    root = "/tmp/buildtest-uploads-test"
    pathlib.Path(root).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "app.services.knowledge_base_service.settings",
        SimpleNamespace(upload_dir=root, upload_max_size_mb=50),
    )

    pid = await _provider_id(client, user_headers)
    mid = await _embedding_model_id(client, user_headers, pid)
    vid = await _vector_db_id(client, user_headers)

    r = await client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "测试库",
            "vector_db_config_id": vid,
            "embedding_model_id": mid,
            "chunk_size": 200,
            "chunk_overlap": 20,
        },
        headers=user_headers,
    )
    assert r.status_code == 201
    kb = r.json()
    kb_id = kb["id"]
    assert kb["embedding_dimension"] == 4
    assert kb["document_count"] == 0
    assert kb["collection_name"].startswith("kb_")

    r = await client.get("/api/v1/knowledge-bases", headers=user_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = await client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=user_headers)
    assert r.status_code == 200

    files = {
        "file": ("note.txt", io.BytesIO(b"hello world " * 30), "text/plain"),
    }
    r = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=user_headers,
        files=files,
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["status"] in ("completed", "processing", "failed")
    if doc["status"] == "completed":
        assert doc["chunk_count"] >= 1

    r = await client.get(f"/api/v1/knowledge-bases/{kb_id}/documents", headers=user_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/retrieve",
        headers=user_headers,
        json={"query": "hello"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "hits" in body
    assert isinstance(body["hits"], list)

    r = await client.put(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"name": "改名"},
        headers=user_headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "改名"

    r = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/rebuild",
        headers=user_headers,
        json={"document_id": doc["id"]},
    )
    assert r.status_code == 204

    r = await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc['id']}",
        headers=user_headers,
    )
    assert r.status_code == 204

    r = await client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=user_headers)
    assert r.status_code == 204


async def test_kb_create_rejects_bad_chunk_overlap(client, user_headers):
    pid = await _provider_id(client, user_headers)
    mid = await _embedding_model_id(client, user_headers, pid)
    vid = await _vector_db_id(client, user_headers)
    r = await client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "x",
            "vector_db_config_id": vid,
            "embedding_model_id": mid,
            "chunk_size": 100,
            "chunk_overlap": 100,
        },
        headers=user_headers,
    )
    assert r.status_code == 422


async def test_kb_not_found(client, user_headers):
    rid = str(uuid.uuid4())
    r = await client.get(f"/api/v1/knowledge-bases/{rid}", headers=user_headers)
    assert r.status_code == 404


async def test_document_chunks_endpoint_contract(
    client, user_headers, fake_embed, monkeypatch, session
):
    import pathlib
    from types import SimpleNamespace

    from sqlalchemy import select

    from app.models.document import Document
    from app.models.kb_vector_chunk import KbVectorChunk

    root = "/tmp/buildtest-uploads-test-chunks"
    pathlib.Path(root).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "app.services.knowledge_base_service.settings",
        SimpleNamespace(upload_dir=root, upload_max_size_mb=50),
    )
    monkeypatch.setattr(
        "app.tasks.ingestion.process_document_ingestion_task.delay",
        lambda *args, **kwargs: None,
    )

    pid = await _provider_id(client, user_headers)
    mid = await _embedding_model_id(client, user_headers, pid)
    vid = await _vector_db_id(client, user_headers)

    kb_res = await client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "chunk-inspect",
            "vector_db_config_id": vid,
            "embedding_model_id": mid,
        },
        headers=user_headers,
    )
    assert kb_res.status_code == 201
    kb_id = kb_res.json()["id"]

    upload_res = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=user_headers,
        files={"file": ("note.txt", io.BytesIO(b"hello chunk view"), "text/plain")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # non-completed document should return 409 document_not_ready
    not_ready = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/chunks",
        headers=user_headers,
    )
    assert not_ready.status_code == 409
    assert not_ready.json()["detail"]["code"] == "document_not_ready"

    # patch document/chunks as completed then verify page/section/token fields
    doc_uuid = uuid.UUID(doc_id)
    doc_row = (await session.execute(select(Document).where(Document.id == doc_uuid))).scalar_one()
    doc_row.status = "completed"
    session.add(
        KbVectorChunk(
            knowledge_base_id=uuid.UUID(kb_id),
            document_id=doc_uuid,
            chunk_index=0,
            content_hash="h" * 64,
            text="1. 项目概述\n这是第一段",
            embedding=[0.1, 0.2, 0.3, 0.4],
            token_length=8,
            source_metadata={"page": 1, "section": "1. 项目概述"},
        )
    )
    await session.commit()

    ready = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/chunks",
        headers=user_headers,
    )
    assert ready.status_code == 200
    body = ready.json()
    assert body["items"][0]["token_length"] == 8
    assert body["items"][0]["source"]["page"] == 1
    assert body["items"][0]["source"]["section"] == "1. 项目概述"

    # invalid pagination should return 422
    bad_page = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/chunks?page=0",
        headers=user_headers,
    )
    assert bad_page.status_code == 422

    # cross-tenant access should return 404
    another_user_headers = {
        "X-User-Id": f"github:{uuid.uuid4()}",
        "X-User-Email": "other@example.com",
        "X-User-Name": "Other User",
    }
    forbidden = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/chunks",
        headers=another_user_headers,
    )
    assert forbidden.status_code == 404
