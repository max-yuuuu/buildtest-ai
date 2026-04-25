## Why

当前知识库链路以同步 Naive RAG 为主，上传文档时在请求线程内完成抽取、切块、向量化与写入，导致稳定性、可观测性和扩展能力受限。随着后续需要支持 self-rag、agentic-rag 等模式，必须先把知识库沉淀为“异步可追溯的数据底座 + 可插拔检索策略层”。

## What Changes

- 将文档入库改为异步任务化：`POST /knowledge-bases/{id}/documents` 仅负责落盘、创建文档记录并投递任务。
- 引入文档入库任务状态模型与查询机制，支持 queued/processing/completed/failed 生命周期与失败重试。
- 升级检索响应契约，返回命中血缘字段与策略快照，满足评测链路追溯需求。
- 将 PostgreSQL 路径从“JSON 向量 + Python 内存相似度”升级为原生 pgvector 检索与索引。
- 新增检索策略抽象与注册机制，先上线 `naive` 策略，预留 multi-query/hyde/self-rag/agentic-rag 扩展点。

## Capabilities

### New Capabilities

- `async-document-ingestion`: 文档上传异步化、任务状态跟踪、失败重试与前端状态订阅。
- `retrieval-lineage-contract`: 检索响应输出命中血缘、策略标识和参数快照，支撑评测可回放。
- `pgvector-native-retrieval`: PostgreSQL 路径使用 pgvector 原生检索与索引能力。
- `retrieval-strategy-framework`: 检索策略插件化抽象与策略注册，默认提供 `naive` 策略。

### Modified Capabilities

- （无）

## Impact

- 后端：`knowledge_base_service`、`vector_connector`、Celery tasks、document/job repository、schema 与 API 路由。
- 数据库：新增入库任务表；调整 `kb_vector_chunks` 的向量存储与索引策略（Alembic 迁移）。
- 前端：知识库详情页上传交互改为队列语义，文档状态轮询或 SSE 订阅。
- 评测：后续 `evaluation_jobs/evaluation_results` 可引用检索策略与血缘字段做版本对比。
