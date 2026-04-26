# 发布与回滚方案（evolve-kb-async-strategy）

## 发布顺序

1. **数据库迁移**
   - 执行 `alembic upgrade head`，确保包含 `0010_kb_chunks_pgvector_native`。
   - 验证 `kb_vector_chunks.embedding` 已为 `vector` 类型，且 `ix_kb_vector_chunks_embedding_ivfflat` 已创建。
2. **后端发布**
   - 发布包含异步入库、策略框架、检索响应扩展的新后端版本。
   - 保持 API 向后兼容：已有客户端可忽略新增字段。
3. **前端发布**
   - 发布知识库详情页与分块查看页改造版本。
   - 验证“已入队/处理中/失败重试”与检索新字段展示。
4. **Celery Worker 发布**
   - 与后端同版本发布，确保 `process_document_ingestion_task` 与新状态机一致。

## 灰度开关建议

- `KB_RETRIEVAL_STRATEGY_DEFAULT`（默认 `naive.v1`）
  - 允许后续切换默认策略，当前仍走 `naive.v1`。
- `KB_ENABLE_PGVECTOR_SQL_SEARCH`（默认开启）
  - 紧急情况下可降级到内存检索兜底路径（仅限非 PostgreSQL 测试/应急）。

## 发布后验证清单

1. 上传文档后接口返回 `queued`，并能查询到 ingestion job。
2. Worker 成功消费后，文档状态变为 `completed`，`chunk_count > 0`。
3. 试检索响应包含：
   - `strategy_id`
   - `retrieval_params`
   - hit 级别 `knowledge_base_id/document_id/chunk_index/source/score/text`
4. 文档分块查看接口在非 `completed` 状态返回 `409 document_not_ready`。
5. 检索日志与入库日志可看到耗时与关键指标字段。

## 回滚路径

1. **应用层回滚**
   - 先回滚后端与 worker 到上一稳定版本。
   - 前端可延后回滚（新增字段为可选展示，兼容旧后端时需避免依赖新字段）。
2. **数据库层回滚**
   - 若必须回滚 schema，执行 `alembic downgrade 0009_kb_chunk_metadata`。
   - 该步骤会将 `embedding` 从 `vector` 转回 `jsonb` 并删除向量索引。
3. **故障隔离**
   - 当仅检索性能异常时，优先保留异步入库能力，隔离检索路径问题。
   - 当队列积压异常时，优先扩容 worker 或临时限流上传入口。

## 风险与应对

- **风险：向量维度不一致导致检索/入库失败**
  - 应对：保留 422 明确报错，快速定位具体 `kb` 与模型维度配置。
- **风险：迁移后检索计划不走索引**
  - 应对：检查 `ANALYZE` 与 ivfflat 参数（`lists`），必要时重建索引。
- **风险：队列积压导致用户感知延迟**
  - 应对：监控 `queued` 持续时长，触发自动扩容或降级策略。
