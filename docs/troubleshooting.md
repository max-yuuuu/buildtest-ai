# Troubleshooting

记录开发过程中遇到的常见问题与解决方法。新增条目请保留「现象 / 原因 / 解决」三段式。

---

## 1. 登录后调用接口报 `relation "xxx" does not exist`

**现象**

登录成功,但前端调用 `/api/backend/*`(例如创建 provider)返回 500,后端日志:

```
sqlalchemy.exc.ProgrammingError: ... <class 'asyncpg.exceptions.UndefinedTableError'>:
relation "users" does not exist
```

**原因**

Postgres 容器是空库,Alembic 迁移没有跑过。SQLAlchemy 模型定义存在,但数据库里没有对应的表。

**解决**

在 backend 容器里执行迁移（开发分层 compose）:

```bash
docker compose -f compose.base.yml -f compose.dev.yml exec backend alembic upgrade head
```

之后修改模型时:

```bash
docker compose -f compose.base.yml -f compose.dev.yml exec backend alembic revision --autogenerate -m "描述"
docker compose -f compose.base.yml -f compose.dev.yml exec backend alembic upgrade head
```

> 注意:若 backend 镜像使用仓库内 `docker-entrypoint.sh`,容器启动时会先执行 `alembic upgrade head`。若未使用该入口或未重建镜像,仍需手动执行上述命令。

---

## 2. 向量库「测试连接」报未安装 pgvector

**现象**

`POST /vector-dbs/{id}/test` 返回 `ok: false`,`message` 含「未安装 pgvector 扩展」。

**原因**

Postgres 镜像不含 `vector` 扩展,或库从未执行过 `CREATE EXTENSION vector`。`docker-entrypoint-initdb.d` 里的脚本**仅在数据卷首次初始化**时执行;已有旧 volume 时不会自动补装。

**解决**

1. 确认 `compose.base.yml` 或 `compose.infra.yml` 中 `postgres` 使用 `pgvector/pgvector:pg16` 并已 pull / 重建容器。
2. **已有数据卷**时在 Postgres 容器内执行一次:

```bash
docker compose -f compose.infra.yml exec postgres psql -U buildtest -d buildtest -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

然后在前端对该向量库配置再点「测试连接」。

---

## 3. 切换到 active 向量库后依然不可用

**现象**

向量库配置 `is_active=true` 后，文档入库或检索仍报连接异常。

**原因**

基础设施健康仅代表容器存活，不代表当前 active 配置的连接串、API Key 或路由有效。

**解决**

先检查基础设施，再检查应用层 active 向量库探测：

```bash
make doctor
```

`make doctor` 会依次检查 Postgres/Redis/Qdrant，然后执行应用层 active vector probe。若失败，按输出修正 active 配置后重试。
