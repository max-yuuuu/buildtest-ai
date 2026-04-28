## Why

当前仓库虽已具备 Docker 与本地混合启动能力，但开发与生产编排仍混杂在同一配置语义中，导致环境切换成本高、配置漂移风险高、上线一致性难以保证。需要建立一套面向 monorepo 的分层容器方案，使本地开发效率与生产可部署性同时成立。

## What Changes

- 建立 `base + dev + prod + infra` 的 Docker Compose 分层策略，明确各文件职责与组合方式。
- 为 `frontend` 与 `backend` 统一升级为 multi-stage Dockerfile，分别提供 `dev` 与 `runner`（生产）构建目标。
- 固化环境变量分层治理：密钥与地址分离，按“连接发起方”选择 `localhost` 或容器服务名。
- 建立向量库切换的运行保障路径（Phase 1 范围：`postgres_pgvector` 与 `qdrant`），覆盖容器健康与应用连通性探测。
- 标准化本地开发与生产启动矩阵、配置校验与故障排查流程，减少团队协作中的运行差异。

## Capabilities

### New Capabilities
- `docker-runtime-strategy`: 定义 monorepo 下开发与生产统一的容器编排分层、镜像构建目标与运行模式矩阵。
- `vector-runtime-switch-guard`: 定义向量库在模式切换与激活切换后的可用性保障与探测流程（限定 `postgres_pgvector` 与 `qdrant`）。

### Modified Capabilities
- `async-document-ingestion`: 补充文档入库链路在新容器运行矩阵下的依赖可用性与启动前置约束。

## Impact

- Affected code:
  - `docker-compose.yml`（拆分与重组）
  - 新增 `compose.base.yml`、`compose.dev.yml`、`compose.prod.yml`（或等效命名）
  - `backend/Dockerfile`
  - `frontend/Dockerfile`
  - `scripts/dev`、`Makefile`
  - `docs/启动文档/启动指南.md` 与相关运维文档
- APIs: 无新增业务 API；可能新增/强化运行健康检查使用规范（如 `/healthz`、`/readyz`）。
- Dependencies/Systems:
  - Docker Compose 分层合并机制
  - Next.js standalone 产物运行模式
  - FastAPI/Celery 在 dev/prod 的命令与镜像目标差异
  - Postgres、Redis、Qdrant 基础设施连通性保障
