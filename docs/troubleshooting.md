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

在 backend 容器里执行迁移:

```bash
docker compose exec backend alembic upgrade head
```

之后修改模型时:

```bash
docker compose exec backend alembic revision --autogenerate -m "描述"
docker compose exec backend alembic upgrade head
```

> 注意:`docker compose up` **不会**自动跑迁移,首次启动或拉到新迁移后必须手动执行。
