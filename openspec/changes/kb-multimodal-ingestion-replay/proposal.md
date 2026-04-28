## Why

当前知识库入库链路以“抽取纯文本 + 向量化”为主，无法覆盖图片/扫描件/复杂版式 PDF/Office 中的关键信息，也无法在检索命中后提供可视化证据回放（用户难以验证召回与纠错）。随着使用场景扩展到多语言与多模态文档，需要一条“结构化解析 → 多模态块 → 可回放证据 → 向量入库”的统一管线。

## What Changes

- 新增多模态文档入库：解析输出 `text/image/table/equation` 等块级结构，并对扫描 PDF 与图片进行多语言 OCR。
- 新增“可视化回放”所需的派生资源生产与引用：渲染 `page_image`、生成 `crop_image`，并在每个分块的 `source_metadata` 中记录 `page + bbox + asset refs`，前端可在分块详情页回放定位与高亮。
- 模型调用统一纳入 Provider 体系：OCR / VLM(可选) / 表格理解(可选) 等能力以可登记、可替换的方式接入；embedding 仍沿用现有机制。
- 明确本次变更只覆盖“入库与回放契约”与最小可用实现；混合检索、rerank、评测闭环增强等列为 Future（本次 tasks 不处理）。

## Capabilities

### New Capabilities

- `multimodal-document-ingestion`: 面向知识库入库的多模态解析与块级抽取能力（含 OCR、多模态块标准契约、派生资源生成）。
- `document-replay-assets`: 为知识库分块提供可视化回放所需的页面渲染图与块裁剪图的生产、存储与鉴权访问能力。
- `provider-capabilities-extensions`: 在现有 Provider/Model 体系上扩展能力类型（至少 OCR；VLM/表格理解/公式理解为可选），支持登记与调用并可追溯。

### Modified Capabilities

- `async-document-ingestion`: 入库产物从“纯文本 chunks”扩展为“多模态 chunks + 回放元数据”，并在 chunk inspection 中可查看回放相关字段。
- `retrieval-lineage-contract`: `source` 字段从页码/section 扩展为可回放的 `page/bbox/page_image/crop_image/block_type` 等结构，确保检索命中可追溯到可视化证据。

## Impact

- **Backend**
  - 知识库入库任务：`KnowledgeBaseService._ingest_document` 需要替换/扩展解析器输出（从 `extract_segments` → 结构化 blocks）并生成派生资源；OCR 与可选 VLM/表格理解需走 Provider 调度。
  - 数据与契约：`KbVectorChunk.source_metadata` 结构升级；新增用于资源访问的 API（受鉴权、租户隔离）。
  - 依赖与运行环境：引入解析器/渲染/OCR 相关依赖与系统包（如 libreoffice 已存在；OCR 与 PDF 渲染可能引入额外系统依赖）。
- **Frontend**
  - 分块详情页增加“回放面板”（page image + bbox overlay + crop preview），并展示多模态块类型与增强字段。
- **Infra/Deploy**
  - `upload_dir` 下新增派生资源目录结构与清理策略；未来可演进到对象存储与签名 URL（不在本次范围）。

