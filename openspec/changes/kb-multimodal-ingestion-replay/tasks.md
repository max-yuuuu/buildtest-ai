## 1. Contracts & wiring（先把“能串起来”锁死）

- [ ] 1.1 定义并落地 `source_metadata` 多模态回放契约（block_type/page/bbox_norm/page_image_path/crop_image_path/modality/generator 等），确保 chunks API 与 retrieve API 透传一致
- [ ] 1.2 为派生资源规划 `upload_dir` 目录结构与命名规范（pages/、crops/、中间缓存等），并定义文档删除/重建时的清理策略
- [ ] 1.3 在入库流程中引入“结构化 blocks → chunks”的中间表示（替换/扩展现有 `extract_segments`），并确保空文本/扫描件不再直接失败（走 OCR fallback）
- [ ] 1.4 明确“输入归一化”策略：Office/图片/纯文本 → 统一到 pages（可渲染）与 blocks（可定位），并将归一化产物与原文的血缘写入 `source_metadata.origin`
- [ ] 1.5 将多模态入库的开关与参数纳入 KB 配置（例如在 `retrieval_config` 或新字段中记录 ocr_model_id / enable_vlm / languages），并在 job 执行时记录“有效配置快照”
- [ ] 1.6 为 blocks 与 chunks 引入稳定标识：`block_id`（解析器输出）、`asset_id`（page/crop 资源），以及 chunk 与 block 的映射规则，便于回放与 debug

## 2. Multimodal parsing & assets generation（解析与回放资源）

- [ ] 2.1 集成版面解析器：输出 blocks（text/image/table/equation）并携带 page + bbox（归一化坐标），支持 PDF/Office/图片输入的统一路径
- [ ] 2.2 实现 page 渲染：为每页生成稳定 `page_image`（用于回放叠框），并能从 bbox 裁剪生成 `crop_image`
- [ ] 2.3 为非文本块生成 chunk 文本模板（OCR text + 可选 caption/table_md/latex），并将回放字段写入 `source_metadata`
- [ ] 2.4 Office 处理链路落地：`.doc/.docx/.pptx/.xlsx` 等输入的归一化（优先 libreoffice 转 PDF 或按类型解析），并保证最终仍能产生 page_image 与 bbox
- [ ] 2.5 解析与渲染缓存：基于文件哈希 + 配置快照生成缓存键，避免重试/重建时重复渲染与重复 OCR
- [ ] 2.6 block 粒度与模板策略确定：text 块是否二次切分、table/equation 是否单块、caption/table_md/latex 的模板字段与展示策略（与回放 UI 对齐）
- [ ] 2.7 上下文窗口策略：为 image/table/equation 块抽取“周边文本上下文”（按同页/邻页可配置），写入 `source_metadata.context` 或模板字段，提升检索可读性
- [ ] 2.8 解析模式与路由：对 PDF 支持 `auto/txt/ocr`（或等价策略），并在 job 配置快照中记录实际采用的模式与原因（如“无文本层→OCR fallback”）

## 3. OCR capability（PaddleOCR，自托管，多语言）

- [ ] 3.1 引入 PaddleOCR 自托管推理（容器依赖/模型文件/多语言参数），支持 block crop OCR 与 page-level OCR fallback
- [ ] 3.2 将 OCR 调用纳入 Provider 体系：扩展 model capability（至少 `ocr`），并在入库时通过注册表路由到对应 provider/model
- [ ] 3.3 将 OCR lineage 写入 `source_metadata.generator` 与 `source_metadata.modality`，确保可追溯（哪种模型、哪条路径产出）
- [ ] 3.4 OCR 结构化输出：尽可能保留行/词级 bbox 与置信度（用于回放与质量门禁），并确定存入 `source_metadata` 的压缩/截断策略（避免过大）
- [ ] 3.5 语言选择策略：支持用户显式配置语言集合（KB 级默认），并可选支持自动语言检测/回退规则（未配置时的默认行为需明确）

## 4. Backend APIs（资产访问与租户隔离）

- [ ] 4.1 新增受鉴权的“回放资源读取”接口（按 user_id/kb_id/doc_id 强隔离），支持读取 page_image/crop_image
- [ ] 4.2 扩展分块检视返回：多模态 chunk 在 `source` 中返回回放定位与资源引用字段
- [ ] 4.3 端到端失败语义：解析/OCR/渲染失败时写入 job/document error_message，并可重试；确保不会泄漏跨租户资源路径
- [ ] 4.4 血缘与可回放一致性：检索命中（retrieve hits）与分块检视（chunks）对同一 chunk 的 `source_metadata` 结构一致；必要时补充“chunk_id/asset_id”稳定标识
- [ ] 4.5 安全与限流：回放资源接口加下载大小限制、路径白名单/防穿越校验、以及必要的 rate limit（避免被当作文件下载通道滥用）

## 5. Frontend replay（可视化回放）

- [ ] 5.1 在文档 chunks 详情页增加回放面板：展示 page image + bbox overlay + crop preview，并显示 block_type/modality/generator
- [ ] 5.2 打通资源拉取链路：通过 BFF 访问后端回放资源接口，处理鉴权与错误态
- [ ] 5.3 回放交互细节：缩放/滚动时 bbox 对齐、点击 chunk 自动滚动到页位置、空资源/失败资源的 fallback 展示
- [ ] 5.4 多模态内容展示：在 chunk 详情中展示 OCR 文本、可选 caption、table_md/latex 等字段（若存在），并明确来源（modality/generator）

## 6. Tests & hardening（质量门禁）

- [ ] 6.1 单元测试：`source_metadata` 契约生成、bbox 归一化/裁剪边界、模板化 chunk 文本
- [ ] 6.2 集成测试：上传包含图片/扫描页的样例文档 → 异步入库完成 → chunks 可回放字段齐全 → retrieve 命中带回放字段
- [ ] 6.3 多语言 OCR 样例回归：至少覆盖中英混排样例，验证 OCR 输出不为空且可检索
- [ ] 6.4 回放资源清理回归：删除文档/重建文档后派生资源不残留（或可被覆盖），不会跨租户读取
- [ ] 6.5 性能冒烟：对典型 PDF（含表格/图片）验证入库耗时在可接受范围，并在超时阈值下能触发通知与可重试

## 99. Future（记录但本次 change 不做，不产出可追踪 tasks）

以下为“下一阶段可选能力”，在本次 change 中仅记录，不纳入实现任务与验收范围：

- Hybrid 检索（BM25 + 向量）与 RRF 融合
- Cross-encoder rerank（含可配置策略与评测对比）
- Query rewrite / intent routing（按问题类型选择检索策略）
- 多模态向量（如 CLIP/视觉 embedding）与图片专用索引
- 表格专用索引与结构化存储（table schema、可下载 csv、表格级检索优化）
- 公式理解增强（latex 识别、渲染、检索与解释的专项评测）
- 对象存储（S3/MinIO）与签名 URL、资源生命周期与成本治理
- Ingestion 质量门禁与观测（OCR 置信度、空块率、异常块密度、抽样人工复核工作流）
- 评测中心对多模态证据的指标扩展与 Bad Case 聚类/回流

