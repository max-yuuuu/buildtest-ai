## Context

知识库文档入库已经切为异步任务，但用户在上传大文件后离开页面时缺少可靠反馈通道。当前头部小铃铛仅有视觉红点，没有通知来源、数据契约和可达上下文，无法承担“任务完成/失败提醒”的产品职责。

本变更目标是将小铃铛升级为“入库任务通知中心（MVP）”，优先解决用户离开页面后的状态感知和回流问题；同时隐藏当前静态模型连通性展示，减少头部噪音。

## Goals / Non-Goals

**Goals:**
- 提供用户级通知中心，聚焦文档入库任务结果提醒（成功/失败/长时处理）。
- 在头部展示未读状态，并支持通知列表查看与已读管理。
- 通知项可直接跳转到对应知识库与文档上下文，减少二次定位成本。
- MVP 使用轮询策略，保证实现复杂度可控并快速上线。

**Non-Goals:**
- 本次不实现通用消息中心（覆盖评测、系统公告、协作提醒等）。
- 本次不引入 WebSocket/SSE 实时推送（仅预留扩展点）。
- 本次不实现复杂通知筛选、分组、归档与用户自定义订阅规则。

## Decisions

### 1) 通知中心聚焦异步入库事件
- 决策：仅接入 `ingestion_job` 生命周期事件，首期包含 `completed`、`failed`、`timeout/stalled`。
- 原因：和当前最紧迫用户痛点（大文件处理等待）直接对应，避免范围膨胀。
- 备选：一次性接入所有异步事件。未采用，因为会增加 schema 与前端交互复杂度。

### 2) 小铃铛保留并升级为可操作面板
- 决策：小铃铛点击后展开通知面板，显示最近通知列表与状态。
- 原因：符合用户已有心智（右上角通知入口），改动成本低。
- 备选：将通知放到知识库页内。未采用，因为用户离开知识库页后仍需要全局提醒。

### 3) 读状态采用“显式已读接口 + 点击单条已读”
- 决策：后端提供按 `notification_ids` 标记已读能力；前端在“点击通知项”时触发已读。
- 原因：兼顾一致性与实现灵活度，避免仅靠本地态导致多端不一致。
- 备选：纯前端本地已读。未采用，因为刷新与多端下状态不稳定。

### 4) MVP 采用短周期轮询
- 决策：前端按固定间隔（建议 15-30s）拉取未读计数与最近通知。
- 原因：快速可落地，依赖少，便于排障。
- 备选：SSE/WebSocket。未采用，因为当前阶段引入长连接运维与前后端复杂度较高。

### 5) 隐藏静态模型连通性展示
- 决策：移除/隐藏当前硬编码“GPT-4o 就绪”状态块。
- 原因：当前信息不具备真实性与可操作性，且占用头部认知带宽。
- 备选：保留但弱化样式。未采用，因为仍无法提供有效决策价值。

### 6) 接口分页采用 `page/page_size`（MVP）
- 决策：通知列表接口首期使用 `page/page_size` 分页。
- 原因：实现成本更低、前后端调试直观，满足当前规模需求。
- 备选：cursor 分页。未采用，因为首期无需处理超大滚动流。

### 7) timeout 阈值改为可配置项
- 决策：引入配置项 `KB_INGESTION_NOTIFICATION_TIMEOUT_SECONDS`（默认 600 秒）。
- 原因：不同环境处理能力差异大，固定阈值不利于灰度调优。
- 备选：硬编码固定值。未采用，因为后续调参需要改代码发布。

### 8) 通知跳转按结果分流
- 决策：`completed` 通知跳转文档分块页；`failed/timeout` 跳转知识库详情页并定位对应文档。
- 原因：让用户落地后能立即执行下一步动作（验收或排障）。
- 备选：统一跳知识库首页。未采用，因为成功场景还需二次点击进入分块详情。

## Data Model Draft (MVP)

### Notification 实体（建议）

- `id`: UUID
- `user_id`: UUID（租户隔离主键之一）
- `event_type`: enum（`ingestion_completed` | `ingestion_failed` | `ingestion_timeout`）
- `level`: enum（`success` | `warning` | `error`）
- `title`: string（短标题）
- `message`: string（可读文案，包含文档名）
- `is_read`: boolean（默认 false）
- `resource_type`: string（固定 `knowledge_base_document`）
- `resource_id`: UUID（document_id）
- `knowledge_base_id`: UUID（用于快捷跳转和查询）
- `ingestion_job_id`: UUID（可诊断链路）
- `action_url`: string（前端可直达路径）
- `dedupe_key`: string（用于幂等防重）
- `created_at`: datetime
- `read_at`: datetime | null

### 索引建议

- `(user_id, is_read, created_at DESC)`：未读计数与列表查询
- `(user_id, created_at DESC)`：按时间倒序分页
- `unique(dedupe_key)`：防重复通知

## API Contract Draft (MVP)

### 1) 获取通知列表
- **Method/Path**: `GET /api/v1/notifications`
- **Query**:
  - `page` (default=1, min=1)
  - `page_size` (default=20, max=50)
  - `unread_only` (optional, default=false)
- **Behavior**:
  - 仅返回当前 `user_id` 通知
  - 默认按 `created_at DESC`

### 2) 获取未读数量
- **Method/Path**: `GET /api/v1/notifications/unread-count`
- **Response**: `{ "unread_count": number }`

### 3) 标记已读
- **Method/Path**: `POST /api/v1/notifications/mark-read`
- **Body**: `{ "notification_ids": ["uuid", "..."] }`
- **Behavior**:
  - 仅更新当前用户通知
  - 幂等：重复请求不报错

### 4) 错误语义
- `401/403`：未登录或无权限
- `404`：通知不存在或不属于当前用户（按项目约定可统一 404）
- `422`：参数非法

## Event Mapping Draft

### Ingestion 状态 -> 通知事件

| Ingestion 状态变化 | 通知类型 | level | 默认文案 |
|---|---|---|---|
| `processing -> completed` | `ingestion_completed` | success | `《{document_name}》处理完成，可开始检索` |
| `processing -> failed` | `ingestion_failed` | error | `《{document_name}》处理失败，点击查看原因` |
| `processing` 超阈值（`KB_INGESTION_NOTIFICATION_TIMEOUT_SECONDS`） | `ingestion_timeout` | warning | `《{document_name}》处理耗时较长，仍在进行中` |

### 幂等规则

- 基于 `dedupe_key = "{event_type}:{ingestion_job_id}:{status_version_or_window}"` 去重。
- 对 timeout 通知按时间窗口抑制重复（每 job 每 30 分钟最多 1 条）。

## Frontend Interaction Draft

### Header 区域调整
- 保留：页面标题、全局搜索、小铃铛、主题切换。
- 隐藏：模型连通性展示块。

### 铃铛交互
1. 页面加载后轮询 `unread-count`，控制红点或数字徽标。
2. 点击铃铛打开通知面板，拉取最近通知列表。
3. 点击通知项后：
   - 先标记该条为已读（可异步，不阻塞跳转）
   - `completed` 跳转文档分块页；`failed/timeout` 跳转知识库详情并定位该文档
4. 空态展示“暂无通知”；错误态展示“加载失败，点击重试”。

### 轮询策略
- 前台页面：每 15-30s 轮询
- 标签页不可见时降频（例如 60s）或暂停
- 回到前台时立即刷新一次

## Risks / Trade-offs

- [风险] 高频轮询带来额外请求开销  
  -> Mitigation: 小 payload（未读计数独立接口）、页面不可见降频、后续升级 SSE。

- [风险] 重复通知导致用户疲劳  
  -> Mitigation: 引入 dedupe_key 和 timeout 窗口去重。

- [风险] 通知文案不清晰，用户无法采取动作  
  -> Mitigation: 文案必须包含“对象 + 结果 + 下一步”；点击统一可达资源上下文。

- [风险] 读状态不一致（多标签页）  
  -> Mitigation: 读状态以服务端为准，轮询回收本地差异。

## Rollout Notes (MVP)

1. 先上线后端通知接口与入库事件发布，不改前端入口样式行为。
2. 再上线前端铃铛面板与已读策略，同时隐藏模型连通性块。
3. 灰度观察未读积压、失败通知率、点击跳转率，评估是否进入 SSE 阶段。
