## Context

当前仓库已经完成文档解析、切分、向量入库等 ingestion 能力，但 query-time 读取流程尚未形成一个可稳定交付的产品链路。前端计划使用 `@ai-sdk/react` 渲染 SSE 流，后端以 Python `LangChain + LangGraph` 为主，且后续会扩展到智能体 chat、数据定制 chat 与多类工具（`api/mcp/skill/cli`）接入。  
本次变更目标是先交付 Quick Chat MVP：以最小链路跑通“检索-生成-引用-流式输出”，并在接口层预留多模式扩展，不提前引入复杂多工具推理。

约束：

- 保持单一事实源与可追溯：回答必须可映射到检索命中。
- MVP 先做单策略向量检索，不引入 hybrid/rerank。
- 保持后端单状态机，前端仅负责展示与交互。

## Goals / Non-Goals

**Goals:**

- 建立 Quick Chat 的 LangGraph 最小工作流与统一流式事件契约。
- 引入统一 Tool Registry 契约，并在 quick 模式仅启用 `api_retrieve` 被动工具。
- 提供 `mode=quick|agent|data` 统一入口，MVP 仅放开 quick。
- 明确检索空结果策略：一次 query rewrite 重试，失败后降级无上下文回答并明确提示。
- 与 `docs/active/ai-sdk-stream-mapping.md` 保持严格对齐，避免前后端流协议漂移。

**Non-Goals:**

- 不实现 agent/data 模式完整链路。
- 不实现多工具自动规划、LangFlow 深度编排与人机中断恢复。
- 不实现多模态检索、VLM 增强、hybrid/rerank。

## Decisions

### Decision 1: Quick Chat 使用单图串行 LangGraph

- 选择：`Normalize -> ToolCall(api_retrieve) -> AssembleContext -> Generate(stream) -> EmitCitations -> Finalize`，附 `Error` 分支。
- 原因：最小状态空间，便于调试、追踪和评测。
- 备选：
  - 双层 chain + orchestrator：状态分散，观测复杂；
  - 一开始统一三模式大图：MVP 复杂度过高。

### Decision 2: Quick 模式仅启用被动工具 `api_retrieve`

- 选择：所有工具走统一 Tool Registry 契约，但 quick 白名单仅 `api_retrieve`。
- 原因：既保留统一扩展面，又避免过早引入工具编排复杂度。
- 备选：Quick 完全不用工具层（直接 service 调用）会导致后续 agent/data 模式重构成本高。

### Decision 3: 检索空结果采用“单次重试 + 降级”

- 选择：空结果时进行一次轻量 query rewrite 并重检；仍空则生成无上下文回答并明确风险提示。
- 原因：在不显著增加复杂度前提下提升命中率与用户体验。
- 备选：
  - 直接失败：交互割裂；
  - 无限重试：不可控，影响时延与稳定性。

### Decision 4: 流式契约与 AI SDK 显示层解耦

- 选择：后端统一发 `start/token/citation/step/error/done`，BFF 做协议映射，前端渲染 `text` 与 `data-*`。
- 原因：保持 Python 主导工作流不变，同时兼容 AI SDK UI。
- 备选：前端直接消费后端自定义 SSE（会增加前端状态解析复杂度）。

## Risks / Trade-offs

- [风险] rewrite 质量不稳定导致误召回  
  -> Mitigation: 仅重试一次；记录重试前后 query 和 hit_count 供评测与回归。

- [风险] Tool Registry 提前引入抽象复杂度  
  -> Mitigation: v1 仅保留最小接口与一个实现，不做插件系统高级功能。

- [风险] 前后端流协议漂移  
  -> Mitigation: 将 `ai-sdk-stream-mapping.md` 作为契约基线，增加契约测试。

- [风险] agent/data 占位接口引发误用  
  -> Mitigation: 统一返回明确错误码 `MODE_NOT_IMPLEMENTED` 与可读提示。

## Migration Plan

1. 增加 chat mode 路由层与请求校验（仅 quick 可用）。  
2. 落地 Quick Chat LangGraph 节点与 `api_retrieve` 工具实现。  
3. 按流契约输出 SSE，并在 BFF 完成 AI SDK 映射。  
4. 增加最小评测与回归测试（有命中、重试后命中、重试后仍空、错误链路）。  
5. 渐进灰度到默认 quick chat 接口。

Rollback:

- 保留旧 chat 路径开关，若新链路异常则切回旧路径。
- 回滚仅影响 query-time 流程，不影响 ingestion 数据结构。

## Open Questions

- rewrite 使用规则模板还是小模型（成本/效果权衡）？
- quick 模式首次默认 `top_k` 与 `similarity_threshold` 的最终数值是否随 KB 配置动态继承？
- citation 在 UI 侧默认展示策略（内联/侧栏）是否需要产品统一规范？
