# BuildTest AI 收敛版总需求重构（LangGraph 1.x）

日期：2026-04-29  
状态：Proposed  
范围策略：保留原 Phase 1-5 与六项硬交付，压缩到 10 天内可交付 MVP

---

## 1. 铁则与边界

### 1.1 不可变铁则

1. **收敛 MVP**：功能项不删，但实现深度最小化（可用、可测、可演示）。
2. **LangGraph 1.x 最新稳定版**：统一以 LangGraph 状态图编排后端工作流（当前基线建议 `1.0.8`）。

### 1.2 本期必须保留的六项交付

1. Quick Chat 生产可用（检索 + 生成 + 引用 + 流式）
2. Agent 最小闭环（ReAct + 工具调用 + 轮次上限）
3. Retriever 抽象层（为 GraphRetriever 预留）
4. 模型配置系统（provider/model 配置与兜底）
5. 前端模型配置与聊天页适配 UI
6. LangFlow/MCP 接入预留接口（本期可不打通）

### 1.3 明确不做（降级为 TODO）

- 多轮会话持久化（chat_sessions/chat_messages）
- 复杂 rerank（多模型精排）
- 多模态深检索（图片/表格深入链路）
- 子 Agent 细粒度模型编排

---

## 2. 10 天执行蓝图（保留 Phase 1-5）

### Phase 1（2 天）：Quick Chat 上线版

目标：`retrieve -> generate -> citation -> stream` 全链路稳定。  
动作：
- Quick Chat 改造为 LangGraph 线性图
- 接入真实 LLM adapter（替换模板拼接）
- 后端 SSE 事件标准化，BFF 映射到前端 AI SDK 流
- 引用链路统一（chunk/source 可追溯）

验收：
- 单轮问答可稳定输出
- 流式 token 与 citation 一致
- 失败返回结构化错误码与 message

### Phase 2（1.5 天）：Retriever 抽象收敛

目标：检索统一入口，不产生双实现分叉。  
动作：
- 定义 `Retriever` 协议（query、filters、k、trace metadata）
- 落地 `VectorRetriever` 默认实现
- 保留 `GraphRetriever` 接口占位（仅契约 + mock）

验收：
- Quick/Agent 同一 retriever 接口
- 行为与现有向量检索一致（回归通过）

### Phase 3（2.5 天）：Agent 最小闭环

目标：可运行的最小 ReAct。  
动作：
- LangGraph 循环：`think -> tool_call -> observe -> decide`
- 轮次硬上限 3
- 仅保留 1-2 个高价值工具（检索、知识总结）
- 支持流式输出中间状态（思考/工具/最终回答）

验收：
- 无工具直答路径可用
- 调工具后答复路径可用
- 超轮次可优雅中止并返回可解释结果

### Phase 4（2 天）：模型配置系统最小化

目标：模型可配、失败可回退。  
动作：
- 统一 provider + model config 读取逻辑
- 支持 mode 级（quick/agent）模型选择
- 明确兜底策略（配置缺失、模型不可用、provider 错误）

验收：
- UI 改配置无需改代码
- 错配有可观测错误与 fallback 行为

### Phase 5（2 天）：前端适配 + LangFlow/MCP 预留

目标：用户可配置可体验，平台可扩展。  
动作：
- 前端增加模型配置入口并与聊天态联动
- 聊天页补齐模式切换、错误提示、引用展示一致性
- LangFlow/MCP 提供 adapter boundary + contract test（不做真实联调）

验收：
- 前端配置后可立即生效
- 预留接口通过契约测试，可后续接实装

---

## 3. 架构收敛（LangGraph 1.x 统一主干）

### 3.1 统一分层

- **Frontend（Next.js）**：只负责交互与渲染，不直接调用 FastAPI。
- **BFF（Next.js API Route）**：协议映射与鉴权透传，保持薄层。
- **Backend（FastAPI + LangGraph）**：业务编排中心。
- **Domain Services**：retrieval、model adapter、tool registry、trace/log。

### 3.2 图设计约束

- Quick 图为线性图：`normalize -> retrieve -> assemble -> generate -> finalize`
- Agent 图为循环图：`init -> think -> [tool_call -> observe]* -> final`
- State 使用显式 schema（TypedDict/Pydantic 任选其一但保持一致）
- 节点保持纯业务逻辑，副作用统一通过事件/回调边界处理

### 3.3 流式与可观测性约束

- 统一基于 LangGraph 流式事件（`astream_events`）输出
- 后端事件模型固定：`token`、`citation`、`tool_call`、`tool_result`、`final`、`error`
- BFF 仅做 event mapping，不改业务语义
- 每次请求携带 trace_id，贯穿 retriever、llm、tool 调用

### 3.4 LangFlow/MCP 预留策略

- 定义 `ExternalToolAdapter` 抽象，不在本期绑定具体平台实现
- 本期只提供：
  - 接口契约
  - mock provider
  - 契约测试
- 后续接入 LangFlow/MCP 时不改主图，仅替换 adapter 实现

---

## 4. 测试、验收与实施门禁

### 4.1 最小测试矩阵

- **后端单测**：
  - Quick 图主路径
  - Agent 图主路径（含工具分支）
  - Retriever 协议兼容性
  - Model config fallback
- **后端集成**：
  - `/chat` 非流式正确响应
  - `/chat/stream` 流式事件顺序与字段完整
- **前端单测**：
  - 流式消息渲染
  - 引用卡片渲染
  - 模型配置保存/加载

### 4.2 每 Phase 完成定义（DoD）

每个阶段必须同时满足：
1. 有可演示场景（demo prompt + 预期结果）
2. 有自动化测试覆盖核心路径
3. 有回归清单（不破坏既有聊天能力）

### 4.3 风险与缓解

- **依赖风险（LangGraph 1.x API 变化）**：锁定小版本 + 统一封装入口
- **流式不一致风险**：定义单一事件契约并做契约测试
- **配置复杂度上升**：mode 级配置优先，禁止本期过细粒度扩展
- **范围失控风险**：严格执行“不做清单”，新增能力进入下一期 backlog

### 4.4 实施建议

- Day 1 即打通 Quick 最小链路，优先拿到可见结果
- Agent 与 Retriever 复用 Quick 的骨架能力，避免并行重复建设
- 每天固定回归 `chat + stream + citation` 三件套

---

## 5. 最终执行口径

在保持原 Phase 1-5 结构与六项硬交付不变前提下，本方案通过：
- 统一 LangGraph 1.x 编排主干
- 严格 MVP 深度控制
- 明确“不做清单”与契约边界

将原“全量扩展式总需求”重构为“10 天内可交付、可验证、可迭代”的收敛版总需求。
