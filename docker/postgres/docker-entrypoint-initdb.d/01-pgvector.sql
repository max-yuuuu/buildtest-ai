-- 首次初始化数据卷时执行（已有 volume 不会再次跑，需见 docker-compose 注释手动执行）
CREATE EXTENSION IF NOT EXISTS vector;
