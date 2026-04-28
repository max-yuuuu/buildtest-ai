from __future__ import annotations

import re
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model
from app.models.provider import Provider
from app.repositories.model import ModelRepository
from app.repositories.provider import ProviderRepository
from app.schemas.model import AvailableModel, ModelCreate, ModelRead, ModelUpdate
from app.services import embedding_client, provider_probe


class ModelService:
    EMBEDDING_BATCH_SIZE_DEFAULT = 10

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.repo = ModelRepository(session, user_id)
        self.provider_repo = ProviderRepository(session, user_id)

    @staticmethod
    def _to_read(m: Model) -> ModelRead:
        return ModelRead(
            id=m.id,
            provider_id=m.provider_id,
            model_id=m.model_id,
            model_type=m.model_type,  # type: ignore[arg-type]
            context_window=m.context_window,
            vector_dimension=m.vector_dimension,
            embedding_batch_size=m.embedding_batch_size,
            created_at=m.created_at,
        )

    async def _ensure_provider(self, provider_id: uuid.UUID) -> Provider:
        """provider 不属于当前用户或已软删 → 404(不泄漏是否存在)。"""
        p = await self.provider_repo.get(provider_id)
        if p is None:
            raise HTTPException(status_code=404, detail="provider not found")
        return p

    async def list(self, provider_id: uuid.UUID) -> list[ModelRead]:
        await self._ensure_provider(provider_id)
        items = await self.repo.list_by_provider(provider_id)
        return [self._to_read(m) for m in items]

    async def get(self, provider_id: uuid.UUID, model_pk: uuid.UUID) -> ModelRead:
        await self._ensure_provider(provider_id)
        m = await self.repo.get(model_pk)
        if m is None or m.provider_id != provider_id:
            raise HTTPException(status_code=404, detail="model not found")
        return self._to_read(m)

    async def create(self, provider_id: uuid.UUID, data: ModelCreate) -> ModelRead:
        provider = await self._ensure_provider(provider_id)
        existing = await self.repo.get_by_model_id(provider_id, data.model_id)
        if existing is not None:
            raise HTTPException(status_code=409, detail="model already registered")
        vector_dimension = data.vector_dimension
        if data.model_type == "embedding" and vector_dimension is None:
            vector_dimension = await self.probe_embedding_dimension(
                provider_id, data.model_id, provider
            )
        m = Model(
            provider_id=provider_id,
            model_id=data.model_id,
            model_type=data.model_type,
            context_window=data.context_window,
            vector_dimension=vector_dimension,
            embedding_batch_size=(data.embedding_batch_size if data.model_type == "embedding" else None),
        )
        if m.model_type == "embedding" and m.embedding_batch_size is None:
            m.embedding_batch_size = self.EMBEDDING_BATCH_SIZE_DEFAULT
        try:
            await self.repo.create(m)
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="model already registered") from e
        await self.session.refresh(m)
        return self._to_read(m)

    async def update(
        self, provider_id: uuid.UUID, model_pk: uuid.UUID, data: ModelUpdate
    ) -> ModelRead:
        provider = await self._ensure_provider(provider_id)
        m = await self.repo.get(model_pk)
        if m is None or m.provider_id != provider_id:
            raise HTTPException(status_code=404, detail="model not found")
        if data.model_type is not None:
            m.model_type = data.model_type
        if data.context_window is not None:
            m.context_window = data.context_window
        if data.vector_dimension is not None:
            m.vector_dimension = data.vector_dimension
        if data.embedding_batch_size is not None:
            m.embedding_batch_size = data.embedding_batch_size
        if m.model_type == "embedding" and m.vector_dimension is None:
            m.vector_dimension = await self.probe_embedding_dimension(
                provider_id, m.model_id, provider
            )
            if m.embedding_batch_size is None:
                m.embedding_batch_size = self.EMBEDDING_BATCH_SIZE_DEFAULT
        if m.model_type == "ocr":
            m.vector_dimension = None
        # batch_size 仅 embedding 模型有意义;改为非 embedding 时顺带清空,避免字段语义漂移
        if m.model_type != "embedding" and m.embedding_batch_size is not None:
            m.embedding_batch_size = None
        await self.session.commit()
        await self.session.refresh(m)
        return self._to_read(m)

    async def delete(self, provider_id: uuid.UUID, model_pk: uuid.UUID) -> None:
        await self._ensure_provider(provider_id)
        m = await self.repo.get(model_pk)
        if m is None or m.provider_id != provider_id:
            raise HTTPException(status_code=404, detail="model not found")
        kb_labels = await self.repo.list_knowledge_base_labels_using_embedding_model(model_pk)
        if kb_labels:
            listed = "、".join(kb_labels)
            raise HTTPException(
                status_code=409,
                detail=(
                    f"该嵌入模型仍被以下知识库使用：{listed}。"
                    "请在未删除的知识库中更换嵌入模型；"
                    "若仅见「已删除仍占引用」，请重建并重启后端以执行迁移（释放软删行的外键）"
                ),
            )
        try:
            await self.repo.delete(m)
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            kb_labels = await self.repo.list_knowledge_base_labels_using_embedding_model(model_pk)
            if kb_labels:
                listed = "、".join(kb_labels)
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"该嵌入模型仍被以下知识库使用：{listed}。"
                        "请在未删除的知识库中更换嵌入模型；"
                        "若仅见「已删除仍占引用」，请重建并重启后端以执行迁移（释放软删行的外键）"
                    ),
                ) from e
            raise HTTPException(
                status_code=409,
                detail="该嵌入模型仍被其他数据引用，无法取消登记",
            ) from e

    async def list_available(self, provider_id: uuid.UUID) -> list[AvailableModel]:
        p = await self._ensure_provider(provider_id)
        registered = {m.model_id for m in await self.repo.list_by_provider(provider_id)}
        try:
            upstream = await provider_probe.list_models(
                p.provider_type, p.api_key_encrypted, p.base_url
            )
        except provider_probe.ProbeError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

        # 百炼(qwen)的 OpenAI 兼容 /models 端点不列 embedding,手动补齐常见型号,
        # 让前端可以直接点「登记」而不必走「手动添加」。
        if p.provider_type == "qwen":
            for extra in ("text-embedding-v4", "text-embedding-v3"):
                if extra not in upstream:
                    upstream.append(extra)

        # 上游可能返回重复 model_id,去重后返回
        seen = set()
        deduped = []
        for mid in upstream:
            if mid not in seen:
                seen.add(mid)
                deduped.append(mid)

        return [
            AvailableModel(
                model_id=mid,
                suggested_type=_infer_model_type(mid),
                is_registered=mid in registered,
            )
            for mid in deduped
        ]

    async def probe_embedding_dimension(
        self,
        provider_id: uuid.UUID,
        model_id: str,
        provider: Provider | None = None,
    ) -> int:
        p = provider or await self._ensure_provider(provider_id)
        if not p.is_active:
            raise HTTPException(status_code=409, detail="provider 未启用，无法探测 embedding 维度")
        try:
            vectors = await embedding_client.embed_texts(
                provider_type=p.provider_type,
                api_key=p.api_key_encrypted,
                base_url=p.base_url,
                model_id=model_id,
                texts=["dimension_probe"],
            )
        except embedding_client.EmbeddingError as e:
            msg = str(e)
            lower = msg.lower()
            is_quota_or_billing = (
                "allocationquota" in lower
                or "freetieronly" in lower
                or "free tier" in lower
                or "quota" in lower
                or "insufficient_quota" in lower
            )

            # Try to extract concise upstream info from the SDK error string, to avoid
            # dumping a huge JSON blob into the user-facing message.
            extracted_code: str | None = None
            extracted_message: str | None = None
            m_code = re.search(r"'code'\s*:\s*'([^']+)'", msg)
            if m_code:
                extracted_code = m_code.group(1)
            m_message = re.search(r"'message'\s*:\s*'([^']+)'", msg)
            if m_message:
                extracted_message = m_message.group(1)

            effective_base_url = p.base_url or "https://api.openai.com/v1"
            if is_quota_or_billing:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "embedding_dimension_probe_failed",
                        "message": "无法自动探测向量维度：上游 embedding 接口因额度/计费限制拒绝请求",
                        "suggestions": [
                            "在百炼控制台关闭“仅使用免费额度(Free tier only)”或充值/更换有额度的模型",
                            "在平台登记模型时手动填写 vector_dimension（可跳过自动探测）",
                        ],
                        "debug": {
                            "provider_type": p.provider_type,
                            "base_url": effective_base_url,
                            "model_id": model_id,
                            "upstream_code": extracted_code,
                            "upstream_message": extracted_message,
                            "raw_error": msg[:1200],
                        },
                    },
                ) from e

            raise HTTPException(
                status_code=502,
                detail={
                    "code": "embedding_dimension_probe_failed",
                    "message": "无法自动探测向量维度：embedding 接口调用失败",
                    "debug": {
                        "provider_type": p.provider_type,
                        "base_url": effective_base_url,
                        "model_id": model_id,
                        "raw_error": msg[:1200],
                    },
                },
            ) from e
        if not vectors or not vectors[0]:
            raise HTTPException(
                status_code=502,
                detail="探测 embedding 维度失败: 上游未返回有效向量",
            )
        return len(vectors[0])


def _infer_model_type(model_id: str) -> str:
    """按 model_id 前缀/子串推断类型。保守策略:只识别明确含 embedding 的,其余默认 llm。"""
    lower = model_id.lower()
    if "ocr" in lower:
        return "ocr"
    # Treat "embed" as a token (e.g. nomic-embed-text:latest). Keep conservative to
    # avoid matching unrelated words like "embedded".
    if "embedding" in lower or re.search(r"(^|[-_/])embed(ding)?($|[-_:/])", lower) is not None:
        return "embedding"
    return "llm"
