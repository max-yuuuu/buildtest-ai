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

### 6) 增加文档分块只读查看能力（MVP）
- 决策：在文档 `completed` 后提供“分块查看”只读能力，返回 chunk 统计信息与分页明细（`chunk_index`、文本预览、长度、来源元数据）。
- 原因：异步化后需要可观测调试入口，帮助定位切块质量与检索效果问题，同时增强评测链路可追溯性。
- 边界：本次不支持在线编辑 chunk、不支持重新切块、不引入复杂筛选与标注工作流。
- 备选：仅展示文档状态，不提供 chunk 明细。未采用，因为排障与评测归因成本过高。

## API Contract Draft (MVP)

### 1) 获取文档分块明细
- **Method/Path**: `GET /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/chunks`
- **Auth**: 必须登录，且 `kb_id/document_id` 均属于当前 `user_id`
- **Query 参数**:
  - `page` (int, optional, default=1, min=1)
  - `page_size` (int, optional, default=20, min=1, max=100)
  - `include_text` (bool, optional, default=true) — 是否返回 `preview_text`
- **行为约束**:
  - 仅当 `document.status=completed` 返回 chunk 数据
  - `queued/processing/failed` 返回业务错误（文档未就绪）

**200 Response (草案)**
```json
{
  "document": {
    "id": "uuid",
    "knowledge_base_id": "uuid",
    "name": "product-spec.pdf",
    "status": "completed",
    "ingestion_job_id": "uuid",
    "completed_at": "2026-04-26T07:00:00Z"
  },
  "chunk_summary": {
    "total_chunks": 128,
    "avg_char_length": 640,
    "min_char_length": 180,
    "max_char_length": 1200
  },
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 128,
    "total_pages": 7
  },
  "items": [
    {
      "id": "uuid",
      "chunk_index": 0,
      "char_length": 712,
      "token_length": 186,
      "preview_text": "....",
      "source": {
        "page": 1,
        "section": "1. 项目概述"
      },
      "created_at": "2026-04-26T06:59:12Z"
    }
  ]
}
```

### 2) 错误响应草案
- **404 Not Found**: `kb_id/document_id` 不存在，或不属于当前用户（对外统一 Not Found，避免资源枚举）
- **409 Conflict**: 文档存在但状态非 `completed`，返回 `code=document_not_ready`
- **422 Unprocessable Entity**: 分页参数非法

**409 Response (草案)**
```json
{
  "code": "document_not_ready",
  "message": "Document is not ready for chunk inspection",
  "detail": {
    "document_id": "uuid",
    "status": "processing"
  }
}
```

### 3) 字段约定（MVP）
- `preview_text`: 默认最多返回前 `N` 个字符（建议 300-500），避免大响应与前端渲染抖动
- `token_length`: 若当前切块流程未持久化 token 数，可先返回 `null`（后续补齐）
- `source`: 来源元数据对象，允许向后扩展（如 `file_path`、`heading_path`），前端按可选字段渲染
- 排序默认按 `chunk_index ASC`，保证阅读顺序稳定

## Frontend Mapping Draft (MVP)

### 1) 文档列表页交互映射
| UI 元素 | 字段来源 | 展示规则 |
|---|---|---|
| 查看分块按钮 | `document.status` | 仅 `completed` 可点击；其他状态置灰并提示“文档处理中，暂不可查看” |
| 入库状态标签 | `document.status` | `queued/processing/completed/failed` 显示统一状态色；文案与上传队列状态一致 |
| 最近完成时间 | `document.completed_at` | 无值时显示 `-` |

### 2) 分块详情页头部映射
| UI 字段 | API 字段 | 空值兜底 |
|---|---|---|
| 文档名称 | `document.name` | `未命名文档` |
| 文档状态 | `document.status` | 不兜底（缺失视为异常） |
| Ingestion Job | `document.ingestion_job_id` | `-` |
| 完成时间 | `document.completed_at` | `-` |
| Chunk 总数 | `chunk_summary.total_chunks` | `0` |
| 平均长度 | `chunk_summary.avg_char_length` | `-` |
| 最短/最长长度 | `chunk_summary.min_char_length` / `chunk_summary.max_char_length` | `-` |

### 3) 分块表格列映射
| 表格列名 | API 字段 | 渲染规则 |
|---|---|---|
| Chunk # | `items[].chunk_index` | 按升序显示，默认不可编辑 |
| 预览文本 | `items[].preview_text` | 为空显示 `（无预览）`；超长省略，支持展开查看完整片段 |
| 字符长度 | `items[].char_length` | 数值显示；无值显示 `-` |
| Token 长度 | `items[].token_length` | `null` 显示 `-`（MVP 允许） |
| 页码 | `items[].source.page` | 无值显示 `-` |
| 章节 | `items[].source.section` | 无值显示 `-` |
| 创建时间 | `items[].created_at` | 格式化为本地时间，无值显示 `-` |

### 4) 分页与筛选（MVP）
- 分页组件绑定 `pagination.page/page_size/total/total_pages`
- 默认 `page_size=20`，支持用户切换 `20/50/100`
- 本次不做服务端高级筛选，仅保留分页；后续可增 `keyword/page-range`

### 5) 错误态与空态文案草案
- `409 document_not_ready`: 展示“文档尚未完成处理，请稍后再试”，并提供“返回文档列表”
- `404`: 展示“文档不存在或无权限访问”
- 空列表（`total_chunks=0`）: 展示“暂无可展示分块数据”，不视为系统错误
- 请求失败重试：提供“重试加载”按钮；避免自动无限重试

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
