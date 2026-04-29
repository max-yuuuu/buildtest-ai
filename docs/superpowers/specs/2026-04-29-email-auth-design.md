# Email Registration & Login Design

Date: 2026-04-29

## Context

BuildTest AI 当前仅支持 GitHub 和 Google OAuth 登录。用户希望通过邮箱+密码注册和登录，同时保留现有第三方登录。

## Architecture Decision

采用 **NextAuth Credentials Provider + 后端注册 API** 方案：

- 所有认证（OAuth + 邮箱）统一走 NextAuth 的 JWT session 管道
- 后端负责注册、验证码、密码验证
- `external_id` 统一格式：OAuth 用 `provider:accountId`，邮箱用 `credentials:email`
- BFF / middleware 无需改动

## 1. Database Schema

### users 表变更

新增列：

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `password_hash` | `String(255)` | nullable | bcrypt 哈希密码，OAuth 用户为 NULL |

### 新增 verification_codes 表

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | UUID | PK, auto | 主键 |
| `email` | `String(255)` | not null, indexed | 目标邮箱 |
| `code_hash` | `String(255)` | not null | bcrypt 哈希后的验证码 |
| `purpose` | `String(20)` | not null | `register`（预留 `login` 扩展） |
| `expires_at` | `DateTime(tz)` | not null | 过期时间（创建后 5 分钟） |
| `attempts` | `Integer` | default 0 | 已尝试验证次数 |
| `used` | `Boolean` | default false | 是否已使用 |
| `created_at` | `DateTime(tz)` | server_default=now() | 创建时间 |

## 2. Backend API

新增 `backend/app/api/v1/auth.py`，提供以下端点：

### `POST /api/v1/auth/send-code`

入参：
```json
{ "email": "user@example.com", "purpose": "register" }
```

逻辑：
1. 若 `purpose=register`，检查 email 是否已被注册（查 `users` 表 `external_id` 前缀为 `credentials:` 且 email 匹配）
2. 检查同一邮箱 60 秒内是否已发送（防刷）
3. 生成 6 位随机数字验证码
4. 用 Resend API 发送验证码邮件
5. 将 code 的 bcrypt hash 存入 `verification_codes` 表（不存明文）

返回：
```json
{ "success": true, "expires_in": 300 }
```

### `POST /api/v1/auth/register`

入参：
```json
{
  "email": "user@example.com",
  "code": "123456",
  "password": "securePass123",
  "name": "张三"
}
```

逻辑：
1. 查 `verification_codes` 找最近一条未过期、未使用、email 匹配的记录
2. 验证 code（bcrypt compare），限制 attempts ≤ 5
3. 密码强度校验：≥ 8 位，至少包含字母和数字
4. bcrypt 哈希 password（cost=12）
5. 创建 user：`external_id = "credentials:{email}"`, `password_hash = hashed`
6. 标记验证码为 used

返回：
```json
{ "success": true }
```

### `POST /api/v1/auth/check-email`

入参：
```json
{ "email": "user@example.com" }
```

返回：
```json
{ "registered": true }
```

用于前端失焦时自动检测，切换登录/注册模式。

### `POST /api/v1/auth/verify-password`

入参：
```json
{ "email": "user@example.com", "password": "securePass123" }
```

逻辑：
1. 查 `users` 表找 `external_id = "credentials:{email}"`
2. bcrypt compare password 与 password_hash
3. 成功返回用户信息

返回：
```json
{ "id": "credentials:user@example.com", "email": "user@example.com", "name": "张三" }
```

此端点由 NextAuth Credentials authorize 函数内部调用（server-side，通过 `BACKEND_URL` 直连后端）。

### 前端调用路径

- `send-code`、`register`、`check-email`：前端通过 BFF 调用（`/api/backend/v1/auth/...`），复用现有代理逻辑
- `verify-password`：仅由 NextAuth authorize 在 server-side 调用，不经过 BFF

## 3. NextAuth Configuration

### `frontend/lib/auth.ts` 变更

新增 Credentials provider：

```ts
import Credentials from "next-auth/providers/credentials"

Credentials({
  name: "credentials",
  credentials: {
    email: { type: "email" },
    password: { type: "password" },
  },
  authorize: async (credentials) => {
    const res = await fetch(`${process.env.BACKEND_URL}/api/v1/auth/verify-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: credentials.email,
        password: credentials.password,
      }),
    })
    if (!res.ok) return null
    return await res.json()
  },
})
```

### JWT callback 改造

```ts
jwt: async ({ token, user, account }) => {
  if (account && account.provider !== "credentials") {
    // OAuth: 保持现有 stable ID 逻辑
    const stable = `${account.provider}:${String(account.providerAccountId)}`
    token.sub = stable
    token.id = stable
  } else if (user) {
    // Credentials: authorize 已返回正确的 id（credentials:email）
    token.sub = user.id
    token.id = user.id
  }
  return token
}
```

### session callback 保持不变

```ts
session: async ({ session, token }) => {
  if (session.user) {
    session.user.id = token.id ?? token.sub
  }
  return session
}
```

## 4. Frontend UI

### Login Page (`frontend/app/login/page.tsx`)

在现有 OAuth 按钮上方增加邮箱表单区域，通过 Tab 切换登录/注册模式：

```
┌─────────────────────────────────────────────┐
│          欢迎使用 BuildTest AI               │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  [登录]  [注册]    ← Tab 切换       │    │
│  ├─────────────────────────────────────┤    │
│  │                                     │    │
│  │  邮箱: [________________]           │    │
│  │                                     │    │
│  │  (注册模式下显示:)                   │    │
│  │  验证码: [____] [发送验证码]         │    │
│  │  用户名: [________________]         │    │
│  │                                     │    │
│  │  密码: [________________]           │    │
│  │                                     │    │
│  │  [登录 / 注册]  ← 提交按钮          │    │
│  │                                     │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ─────── 或 ───────                         │
│                                             │
│  [GitHub 登录]  [Google 登录]               │
│                                             │
└─────────────────────────────────────────────┘
```

### 交互流程

**登录模式：**
1. 输入邮箱和密码
2. 点击登录 → 调 `signIn("credentials", { email, password, callbackUrl })`
3. NextAuth authorize 验证通过 → JWT session 建立 → 跳转

**注册模式：**
1. 输入邮箱 → 点击「发送验证码」→ 调 `POST /api/v1/auth/send-code`
2. 收到验证码邮件，输入 6 位码
3. 输入用户名（可选）和密码
4. 点击注册 → 调 `POST /api/v1/auth/register`
5. 注册成功 → 自动调 `signIn("credentials", { email, password, callbackUrl })` 自动登录

**邮箱自动检测：**
- 输入邮箱后失焦（onBlur）→ 调 `POST /api/v1/auth/check-email`
- 已注册：自动切到登录模式
- 未注册：自动切到注册模式

## 5. Security

| 措施 | 说明 |
|---|---|
| 密码哈希 | bcrypt, cost=12 |
| 验证码哈希 | bcrypt 哈希后存储，不存明文 |
| 验证码过期 | 5 分钟有效期 |
| 尝试次数限制 | 验证码最多验证 5 次，超限作废 |
| 发送频率限制 | 同一邮箱 60 秒内只能发一次 |
| 密码强度 | ≥ 8 位，至少包含字母和数字 |
| 邮箱唯一性 | `external_id` unique 约束 |

## 6. Environment Variables

| 变量 | 层 | 说明 |
|---|---|---|
| `RESEND_API_KEY` | Backend | Resend 邮件服务 API Key |

## 7. Files Changed

| 层 | 文件 | 变更 |
|---|---|---|
| DB | `backend/app/models/user.py` | 新增 `password_hash` 列 |
| DB | `backend/app/models/verification_code.py` | 新建模型 |
| DB | `alembic/versions/` | 新增迁移 |
| Backend | `backend/app/api/v1/auth.py` | 新增：send-code, register, check-email, verify-password |
| Backend | `backend/app/repositories/verification_code.py` | 新增仓库 |
| Backend | `backend/app/schemas/auth.py` | 新增请求/响应 schema |
| Backend | `backend/app/services/email.py` | Resend 集成 |
| Frontend | `frontend/lib/auth.ts` | 新增 Credentials provider + JWT callback 改造 |
| Frontend | `frontend/app/login/page.tsx` | 新增邮箱表单 UI |
| Frontend | `frontend/lib/api.ts` | 新增 auth 相关 API 调用 |
| Env | `.env.example` | 新增 `RESEND_API_KEY` |

**不需要改动：** middleware.ts、BFF route、providers.tsx、后端其他业务路由。

## 8. Verification

- 注册：输入邮箱 → 发验证码 → 输入验证码+密码 → 注册成功 → 自动登录 → 跳转到 /providers
- 登录：输入邮箱+密码 → 登录成功 → 跳转到 /providers
- 重复注册：同一邮箱再次注册应提示已注册
- 验证码过期：5 分钟后验证码失效
- 验证码错误：5 次错误后验证码作废
- OAuth 不受影响：GitHub / Google 登录正常工作
- BFF 透传：邮箱用户的 `X-User-Id` 格式为 `credentials:email@example.com`
