# KEYS.md — 密钥与环境变量清单

本文档列出 BuildTest AI 平台部署/开发需要你后续准备的所有密钥、账号和配置项。按优先级分组;Phase 1 MVP 必需项标 **[必需]**,Phase 2+ 标 **[稍后]**。

所有值最终写入 `.env` 文件(基于 `.env.example` 复制),**禁止**提交到 git。

---

## 1. 认证相关(NextAuth.js)

用于前端 GitHub / Google OAuth 登录。

### 1.1 GitHub OAuth **[必需]**
- 申请地址:https://github.com/settings/developers → New OAuth App
- Homepage URL: `http://localhost:3000`
- Authorization callback URL: `http://localhost:3000/api/auth/callback/github`
- 获得:
  - `GITHUB_ID` — Client ID
  - `GITHUB_SECRET` — Client Secret

### 1.2 Google OAuth **[必需]**
- 申请地址:https://console.cloud.google.com/ → APIs & Services → Credentials → Create OAuth client ID
- Application type: Web application
- Authorized redirect URI: `http://localhost:3000/api/auth/callback/google`
- 获得:
  - `GOOGLE_ID` — Client ID
  - `GOOGLE_SECRET` — Client Secret

### 1.3 NextAuth 会话密钥 **[必需]**
- `NEXTAUTH_SECRET` — 32+ 字节随机串
- 生成命令:`openssl rand -base64 32`
- `NEXTAUTH_URL` — 本地 `http://localhost:3000`,生产填真实域名

---

## 2. LLM / Embedding Provider

Provider 凭证通过平台 UI 动态添加并加密存储,不再从根目录 `.env` 读取 `OPENAI_API_KEY` / `OPENAI_BASE_URL`。

### 2.1 OpenAI **[按需]**
- 申请地址:https://platform.openai.com/api-keys
- 使用方式:在 Provider 管理页新增 OpenAI 类型并填写 API Key（可选 Base URL）

### 2.2 Anthropic **[稍后]**
- https://console.anthropic.com/settings/keys
- `ANTHROPIC_API_KEY`

### 2.3 智谱 / 通义 / Azure OpenAI **[稍后]**
- 视用户需求接入,平台本身不强依赖

---

## 3. 向量数据库

开发环境默认用 Docker Compose 起本地 Qdrant,无需外部 key;生产环境才要云托管 key。

### 3.1 Qdrant(本地 Docker)**[必需 — Docker 自动]**
- `QDRANT_URL`：
  - docker 内访问：`http://qdrant:6333`
  - 本机进程访问：`http://localhost:6333`
- `QDRANT_API_KEY=`(本地留空)

### 3.2 Qdrant Cloud / Milvus Cloud **[稍后]**
- 生产环境自行在 https://cloud.qdrant.io / https://zilliz.com 注册
- 获得 URL + API Key,通过平台 UI 录入(存入 `vector_db_configs` 表)

---

## 4. 基础设施

由 docker-compose 本地拉起,开发无需你准备,仅列出变量供参考。

### 4.1 PostgreSQL
- `DATABASE_URL`：
  - docker 内访问：`postgresql+asyncpg://buildtest:buildtest@postgres:5432/buildtest`
  - 本机进程访问：`postgresql+asyncpg://buildtest:buildtest@localhost:5432/buildtest`

### 4.2 Redis(Celery broker/backend)
- `REDIS_URL`：
  - docker 内访问：`redis://redis:6379/0`
  - 本机进程访问：`redis://localhost:6379/0`

---

## 5. 应用加密主密钥 **[必需]**

用于加密数据库中的 `*_encrypted` 字段(Provider API Key、向量库 API Key)。

- `APP_ENCRYPTION_KEY` — Fernet 格式,44 字符 base64
- 生成命令:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- **一旦生产环境落库加密后,此 key 绝不能丢,也不能换**。更换需要先解密所有数据再重新加密。

---

## 6. 对象存储(可选)

文档上传的原始文件存放。MVP 先用本地磁盘挂载,Phase 3 切云存储。

### 6.1 AWS S3 / 阿里云 OSS / 腾讯云 COS **[稍后]**
- `S3_ENDPOINT`
- `S3_BUCKET`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `S3_REGION`

---

## 7. 观测性(可选,Phase 4)

- `SENTRY_DSN` — 错误监控
- `PROMETHEUS_PUSHGATEWAY` — 指标上报
- `LOG_LEVEL=INFO`

---

## 8. CI/CD Secrets(GitHub Actions)

在 GitHub 仓库 Settings → Secrets and variables → Actions 配置:

- `DOCKER_HUB_TOKEN` **[稍后]**
- `DEPLOY_SSH_KEY` **[稍后]**

---

## 总结:Phase 1 MVP 启动前,你至少要准备

| # | 变量 | 来源 |
| :-: | :--- | :--- |
| 1 | `GITHUB_ID` / `GITHUB_SECRET` | GitHub OAuth App |
| 2 | `GOOGLE_ID` / `GOOGLE_SECRET` | Google Cloud OAuth |
| 3 | `NEXTAUTH_SECRET` | `openssl rand -base64 32` |
| 4 | `APP_ENCRYPTION_KEY` | `python -c "..."`(见 §5) |
其余(Postgres / Redis / Qdrant)docker-compose 自动处理,无需人工。Provider 密钥在应用内配置,无需预置到根 `.env`。

准备好后将值填入仓库根目录的 `.env` 文件(见 `.env.example`)。
