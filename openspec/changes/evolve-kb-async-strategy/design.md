## Context

当前知识库能力可用，但文档上传仍在请求线程内完成抽取、切块、向量化和写入，导致长文档入库时接口响应不稳定，且状态可观测性不足。与此同时，后续要扩展 self-rag、agentic-rag 等高级模式，若继续把检索逻辑耦合在单一 service 中，会导致知识库底座与策略逻辑互相污染，影响评测可追溯性与演进速度。

该变更跨越后端 API、异步任务、向量检索实现、响应契约和前端交互，且涉及数据库迁移与兼容，因此需要统一设计。

## Goals / Non-Goals

**Goals:**
- 将文档入库链路改为异步执行，API 仅接单并返回可追踪标识。
- 建立可观测的文档入库状态模型，并支持失败重试。
- 将检索响应升级为“可追溯契约”，输出命中血缘与策略快照。
- 将 PostgreSQL 路径升级为原生 pgvector 检索与索引。
- 抽象检索策略框架，先迁移 `naive` 策略并保持行为等价。

**Non-Goals:**
- 本次不实现 multi-query、hyde、hybrid、rerank、self-rag、agentic-rag 的完整策略逻辑。
- 本次不实现复杂工作流编排 UI，仅提供后端可扩展接口和最小前端状态展示。
- 本次不引入新的向量数据库类型，仍聚焦 `postgres_pgvector` 与 `qdrant`。

## Decisions

### 1) 文档上传改为“接单 + 异步处理”
- 决策：`POST /knowledge-bases/{id}/documents` 只完成文件落盘、`document.status=queued`、创建 `ingestion_job`、投递 Celery 任务并返回 `document_id`。
- 原因：避免长耗时操作阻塞 API 线程，提升稳定性并允许队列化扩展。
- 备选：保留同步上传并增加超时与前端提示。未采用，因为根因未解决。

### 2) 引入 `ingestion_jobs` 作为异步事实源
- 决策：新增 `ingestion_jobs` 表记录每次处理生命周期（状态、进度、错误、重试、时间戳）。
- 原因：仅靠 `documents.status` 无法承载重试与运行过程追踪，且不利于后续审计与指标统计。
- 备选：仅扩展 `documents` 字段。未采用，因为会混淆文档实体与任务实体职责。

### 3) 检索响应契约升级为“命中 + 请求快照”
- 决策：`retrieve` 返回命中血缘字段（kb/document/chunk/source/score），并回传 `strategy_id` 与 `retrieval_params` 快照。
- 原因：评测链路需要可回放和可对比的检索上下文来源，支持后续结果归因。
- 备选：保持轻量响应，只返回 text+score。未采用，因为无法满足评测追溯目标。

### 4) PostgreSQL 检索改为原生 pgvector
- 决策：`kb_vector_chunks` 使用 pgvector 类型和索引（按实际版本选择 ivfflat 或 hnsw），检索下推到 SQL。
- 原因：当前 Python 内存相似度路径性能和一致性不足，且无法利用数据库侧索引能力。
- 备选：维持现状，仅做缓存优化。未采用，因为仍受全表扫描与内存计算限制。

### 5) 建立检索策略接口与注册机制
- 决策：引入 `RetrievalStrategy` 抽象（query 预处理、召回、结果后处理、trace 输出），通过 `strategy_id` 选择实现；首个实现为 `naive.v1`。
- 原因：把“知识库底座”与“模式逻辑”解耦，支持后续策略增量接入而不破坏主链路。
- 备选：继续在 `knowledge_base_service.retrieve` 中分支判断。未采用，因为复杂度会随模式数量线性爆炸。

## Risks / Trade-offs

- [风险] 异步化后状态不一致（例如任务失败但文档停留 processing）  
  -> Mitigation: 任务入口/出口统一状态机、异常兜底写回、增加幂等更新条件。

- [风险] pgvector 迁移期间检索兼容性风险  
  -> Mitigation: 先双写或灰度切换，提供回滚 migration 与 connector fallback。

- [风险] 检索响应字段扩展影响前端与调用方兼容  
  -> Mitigation: 保留现有字段并新增扩展字段，前端按向后兼容方式消费。

- [风险] 策略框架过早抽象导致实现负担  
  -> Mitigation: 只实现最小接口与 `naive.v1`，高级策略延后按里程碑落地。

- [风险] 队列拥塞导致入库延迟上升  
  -> Mitigation: 增加队列监控、并发配置、重试退避和任务超时。
