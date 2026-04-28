## Context

当前项目在单仓下同时维护 `frontend`（Next.js）与 `backend`（FastAPI + Celery），并依赖 Postgres、Redis、Qdrant 运行 RAG 相关链路。现有编排可运行但开发模式与生产模式混放，导致以下问题：

- 配置语义耦合：同一 compose 文件同时承载热更新与部署语义。
- 地址切换风险：`localhost` 与容器服务名切换依赖手工记忆。
- 镜像职责不清：当前 Dockerfile 偏开发态，生产镜像可维护性与安全性不足。
- 向量库切换可用性缺少统一守卫：`postgres_pgvector` 与 `qdrant` 切换后缺少标准探测闭环。

约束与背景：

- 产品单一事实源要求向量库通过 `vector_db_configs` 可配置，不可硬编码单一厂商。
- 本次范围限定仅保障 `postgres_pgvector` 与 `qdrant` 两种运行形态。
- 目标为 Compose 先落地，且后续可平滑迁移到 Kubernetes。

## Goals / Non-Goals

**Goals:**

- 建立 `base + dev + prod + infra` 的分层编排，消除环境职责混淆。
- 前后端镜像统一升级为 multi-stage，分别支持开发与生产目标。
- 建立环境变量分层治理，确保宿主机与容器混合启动下地址解析可预测。
- 定义向量库切换后的可用性守卫（基础设施探活 + 应用侧连接探测）。
- 固化启动矩阵、校验命令与故障排查路径，提升团队协作一致性。

**Non-Goals:**

- 不新增业务功能与业务 API。
- 不扩展至 `milvus/weaviate/pinecone/chroma` 本地可运行编排。
- 不在本次变更中引入 Kubernetes 部署清单。

## Decisions

### Decision 1: Compose 分层为 base/dev/prod/infra

- 采用 `compose.base.yml` 承载共享服务定义；
- `compose.dev.yml` 承载热更新与源码挂载；
- `compose.prod.yml` 承载生产运行策略（重启策略、安全限制、资源约束）；
- `compose.infra.yml` 保持仅基础设施，服务于“应用本地跑，依赖容器化”模式。

**Why this over single-file profiles**

- 多文件分层比单文件 profile 在审计、差异追踪、上线评审中更清晰；
- 避免 profile 组合导致的隐式覆盖风险；
- 与当前仓库已有 `docker-compose.infra.yml` 与本地混合开发习惯一致。

### Decision 2: Dockerfile 统一 multi-stage，显式 dev/runner 目标

- `frontend`：采用 Next standalone 产物作为 runner 输入；
- `backend`：拆分 dev 与 runner，runner 禁止 `--reload`；
- `worker`：复用 backend runner 镜像，仅切换启动命令。

**Why this over single-stage images**

- 显著降低生产镜像体积与攻击面；
- 开发与生产职责分离，避免将热更新逻辑带入部署环境；
- 提高构建缓存命中与 CI 可重复性。

### Decision 3: 环境变量按“密钥/地址”与“运行位置”双维分层

- `.env` 仅存密钥；
- 地址类变量分为 host 与 docker 两组，按启动位置加载；
- 统一由 `scripts/dev` 与 Make 入口装配，减少手工导出环境变量。

**Why this over single .env**

- 降低密钥泄漏与误提交风险；
- 避免切换模式时手改 `.env` 引入不可追踪错误；
- 便于 CI 与本地复用同一装配逻辑。

### Decision 4: 向量库切换守卫采用“双层探测”

- 第一层：容器健康（postgres/redis/qdrant）；
- 第二层：应用连通性（基于当前 active vector config 的连接测试）。

**Why this over container health only**

- 容器健康并不代表业务配置正确；
- 可提前发现 `connection_string`/网络路径不一致问题，避免运行时失败。

## Risks / Trade-offs

- **[风险] Compose 文件数量增加，学习成本上升** → **Mitigation**：提供固定启动矩阵与 Make 别名，统一入口。
- **[风险] 本地/容器混合模式仍存在 host 解析差异** → **Mitigation**：文档明确“连接发起方决定 host”，并以 `doctor` 命令强制验收。
- **[风险] Next standalone 对静态资源拷贝步骤敏感** → **Mitigation**：在 Dockerfile 中固定拷贝 `.next/standalone`、`.next/static`、`public` 并加入启动检查。
- **[风险] 生产运行参数（workers/资源限制）初值不匹配负载** → **Mitigation**：先给保守默认值，并在发布后以指标回调优。

## Migration Plan

1. 增加 compose 分层文件与 Dockerfile 多阶段目标，保持旧入口可临时并存。
2. 更新 `scripts/dev` 与 Make 命令映射，接入新文件组合。
3. 在本地验证四种启动矩阵（全 docker、前本后容器、后本前容器、全本地应用+infra docker）。
4. 执行向量库切换回归（`postgres_pgvector` ↔ `qdrant`），验证 ingest/retrieve 基础链路。
5. 更新启动文档与 troubleshooting，移除旧编排入口。
6. 回滚策略：保留上一个 compose 入口标签，可通过切回旧 compose 组合快速恢复。

## Open Questions

- 生产阶段 backend 采用单进程 `uvicorn` 还是 `gunicorn + uvicorn worker`，需结合部署平台并发模型最终锁定。
- 是否在本次同步引入 `docker compose config --quiet` 的 CI 门禁，如引入需评估现有流水线耗时。
