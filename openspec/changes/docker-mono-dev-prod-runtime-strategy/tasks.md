## 1. Compose 分层编排落地

- [x] 1.1 拆分并创建 `compose.base.yml`，承载 frontend/backend/worker 与 postgres/redis/qdrant 的共享定义
- [x] 1.2 创建 `compose.dev.yml`，覆盖开发态命令、源码挂载与热更新配置
- [x] 1.3 创建 `compose.prod.yml`，覆盖生产态命令、重启策略、安全选项与资源限制
- [x] 1.4 对齐并瘦身 `compose.infra.yml`（仅保留基础设施服务）
- [x] 1.5 为 dev/prod/infra 组合提供可复用 compose 启动命令并通过 `docker compose config --quiet` 校验

## 2. 前后端镜像 multi-stage 改造

- [x] 2.1 改造 `frontend/Dockerfile` 为 `dev/builder/runner` 多阶段并启用 standalone 运行产物复制
- [x] 2.2 改造 `backend/Dockerfile` 为 `dev/builder/runner` 多阶段并明确生产态禁用 reload
- [x] 2.3 调整 worker 服务复用 backend runner 镜像，仅覆盖 celery 启动命令
- [x] 2.4 补充 `.dockerignore`（根目录及必要子目录）以降低构建上下文体积并提升缓存命中

## 3. 环境变量与启动入口治理

- [x] 3.1 定义并补齐 `env/common.env`、`env/dev.host.env`、`env/dev.docker.env`、`env/prod.env` 示例模板
- [x] 3.2 更新 `scripts/dev` 以支持按运行模式自动加载 env 分层并输出关键地址变量
- [x] 3.3 更新 `Makefile` 高频命令（dev 全容器、infra-only、prod 组合、print-env、doctor）
- [x] 3.4 增加地址解析约束校验（连接发起方决定 host）并在错误配置时给出明确提示

## 4. 向量库切换守卫与可用性验证

- [x] 4.1 在运行检查流程中实现基础设施探活（Postgres/Redis/Qdrant）
- [x] 4.2 在应用层接入 active vector config 连通性探测（`postgres_pgvector` 与 `qdrant`）
- [x] 4.3 在向量库 active 配置切换后执行 post-switch 验证，失败时阻断“ready”状态声明
- [x] 4.4 编写覆盖 `postgres_pgvector ↔ qdrant` 切换的验证脚本或测试用例

## 5. 文档、回归与发布准备

- [x] 5.1 更新 `docs/启动文档/启动指南.md` 的四种启动矩阵与命令示例
- [x] 5.2 更新 `docs/troubleshooting.md` 中常见网络地址与依赖连通性故障排查
- [x] 5.3 执行端到端回归：开发模式、生产模式、混合模式的基础链路（登录、文档入库、检索）
- [x] 5.4 形成发布前检查清单与回滚步骤，确保旧编排入口可临时回退
