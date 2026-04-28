## Context

当前知识库入库链路为：上传原文 → 抽取纯文本（按后缀）→ 递归切块 → embedding → 写入向量库，并在 `KbVectorChunk.source_metadata` 中保存少量来源信息（如页码与段落标题）。该链路对图片/扫描件/复杂版式 PDF/Office 的信息覆盖不足，且检索命中缺乏“可视化证据回放”，影响可信度与调试效率。

本变更目标是引入一条面向多模态文档的结构化入库管线：输出 `text/image/table/equation` 块级结构，结合多语言 OCR，并生成可回放资源（页渲染图与块裁剪图），最终以统一的 `source_metadata` 契约贯穿入库、检索与分块检视。

约束：
- 系统已具备异步入库（Celery）、分块检视 API、向量库抽象与 Provider/Model 登记机制。
- 模型侧必须统一走 Provider 体系；embedding 维度锁定与多租户隔离保持不变。
- 回放选择 `page_image + crop_image + bbox`（避免 PDF 渲染差异带来的坐标漂移）。

## Goals / Non-Goals

**Goals:**
- 多模态入库：支持将文档解析为 `text/image/table/equation` 等 blocks，并为扫描 PDF/图片提供多语言 OCR。
- 统一块契约：为每个向量 chunk 持久化可追溯的 `source_metadata`（至少包含 `page`、`bbox`、`block_type`、以及回放资源引用）。
- 可视化回放：产出 `page_image` 与 `crop_image` 派生资源，并通过受鉴权的方式供前端回放与高亮。
- Provider 统一：将 OCR（至少）以可登记能力纳入 Provider/Model 体系；VLM/表格理解/公式理解可选但需预留能力位与追溯字段。

**Non-Goals:**
- 不在本次实现混合检索（BM25 + 向量）、cross-encoder rerank、query rewrite、图谱索引等检索侧增强。
- 不在本次实现对象存储（S3/MinIO）与签名 URL（仍用现有 `upload_dir` 本地存储；未来演进列入 Future）。
- 不在本次实现评测中心对多模态证据的专项指标与工作流（仅保证 lineage 契约能支撑后续接入）。

## Decisions

- **结构化解析优先（对标 raganything 路线）**
  - 决策：入库解析不再仅抽取纯文本，而以“版面解析器”产出 blocks（含页码与 bbox），并可选择 `auto/txt/ocr` 等模式。
  - 备选：PyMuPDF/pdfplumber + OCR 拼接纯文本（实现轻，但对表格/公式/图注等结构信息丢失严重，且无法稳定产生 table/equation 块）。

- **回放以 page image 为主，bbox 统一归一化坐标**
  - 决策：回放基于 `page_image`（统一渲染输出）叠加归一化 bbox（0..1），避免不同 PDF 渲染器导致的坐标/字体差异。
  - 备选：直接在 PDF 上做高亮（跨浏览器/字体渲染不稳定，且对 Office/图片输入不统一）。

- **OCR 引擎选 PaddleOCR（自托管，多语言）**
  - 决策：OCR 作为必选链路（图片/扫描 PDF fallback），优先块级 OCR（对 image/table/equation crop）并保留可回放定位信息；页级 OCR 用于文本层缺失时兜底。
  - 备选：EasyOCR/Tesseract/云 OCR（依赖与成本、隐私与准确率取舍不同；本次按自托管开源路线）。

- **多模态增强（VLM/表格/公式）可插拔，不强绑**
  - 决策：将 VLM caption、表格结构化/摘要、公式识别/解释作为可选增强阶段；通过 Provider 登记并记录 `modality`/`generator` 元数据，便于后续评测对比是否值得默认启用。

- **统一 `source_metadata` 契约（兼容 retrieval-lineage-contract）**
  - 决策：扩展 `KbVectorChunk.source_metadata` 结构，最小字段集：
    - `block_type`: text|image|table|equation
    - `page`: int
    - `bbox_norm`: {x0,y0,x1,y1}（0..1）
    - `page_image_path`: string
    - `crop_image_path`: string|null
    - `origin`: {file_name, file_type, storage_path}（可选）
    - `modality`: ocr_text|vision_caption|table_to_md|...
  - 该契约必须被：分块检视 API（chunks）、检索 API（retrieve hits.source）一致透传。

- **资源访问方式：受鉴权的后端路由（Phase 1/2 兼容）**
  - 决策：在后端提供一个 tenant-isolated 的“派生资源读取”接口，前端通过现有 BFF 透传获取；资源仍落在 `upload_dir` 下，与原文同生命周期管理。
  - 备选：对象存储 + 签名 URL（后续演进）。

## Risks / Trade-offs

- **[解析器依赖与部署复杂度上升]** → 固化 docker 镜像依赖清单；解析器与 OCR 以独立模块/服务形式隔离，避免侵入业务核心；提供 healthcheck 与降级策略（仅文本层抽取）。
- **[大文件/复杂 PDF 耗时与成本]** → 异步队列并发受控；对页渲染/OCR 做分段与缓存；为超时提供明确 job 状态与可重试能力。
- **[回放资源占用磁盘增长]** → 目录结构标准化；按文档删除级联清理；未来引入对象存储与生命周期策略。
- **[VLM 引入幻觉/不稳定]** → 默认关闭或按类型启用；输出标注来源与置信信息；纳入评测后再决定默认策略。

