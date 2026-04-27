# API 文档

## 概述

WeKnora 提供 RESTful API，所有接口路径前缀为 `/api/v1`。

### 访问 Swagger 文档

启动服务后访问：
- http://localhost:8080/swagger/index.html

原始 Swagger JSON：
- [docs/swagger.json](../docs/swagger.json)
- [docs/swagger.yaml](../docs/swagger.yaml)

### 认证方式

WeKnora 支持两种认证方式：

#### 1. JWT Token (用户认证)

```http
Authorization: Bearer <your-jwt-token>
```

#### 2. API Key (租户认证)

```http
X-API-Key: <your-api-key>
```

---

## API 分类

### 1. 认证 API (`/api/v1/auth`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/login` | POST | 用户登录 |
| `/register` | POST | 用户注册 |
| `/logout` | POST | 用户登出 |
| `/profile` | GET | 获取用户信息 |
| `/profile` | PUT | 更新用户信息 |

### 2. 知识库 API (`/api/v1/knowledgebase`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 列出知识库 |
| `/` | POST | 创建知识库 |
| `/:id` | GET | 获取知识库详情 |
| `/:id` | PUT | 更新知识库 |
| `/:id` | DELETE | 删除知识库 |

### 3. 知识 API (`/api/v1/knowledge`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 列出知识 |
| `/` | POST | 添加知识 |
| `/:id` | GET | 获取知识详情 |
| `/:id` | PUT | 更新知识 |
| `/:id` | DELETE | 删除知识 |
| `/upload` | POST | 上传文件 |
| `/search` | POST | 搜索知识 |

### 4. 会话 API (`/api/v1/session`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 列出会话 |
| `/` | POST | 创建会话 |
| `/:id` | GET | 获取会话详情 |
| `/:id` | PUT | 更新会话 |
| `/:id` | DELETE | 删除会话 |
| `/:id/chat` | POST | 发送消息 (非流式) |
| `/:id/chat/stream` | POST | 发送消息 (流式) |
| `/:id/agent` | POST | Agent 推理 |
| `/:id/messages` | GET | 获取历史消息 |

### 5. 模型 API (`/api/v1/model`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 列出模型 |
| `/` | POST | 添加模型 |
| `/:id` | GET | 获取模型详情 |
| `/:id` | PUT | 更新模型 |
| `/:id` | DELETE | 删除模型 |
| `/test` | POST | 测试模型连接 |

### 6. MCP 服务 API (`/api/v1/mcp`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 列出 MCP 服务 |
| `/` | POST | 添加 MCP 服务 |
| `/:id` | GET | 获取服务详情 |
| `/:id` | PUT | 更新服务 |
| `/:id` | DELETE | 删除服务 |
| `/:id/tools` | GET | 获取工具列表 |

### 7. Agent API (`/api/v1/agent`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 列出 Agent |
| `/` | POST | 创建 Agent |
| `/:id` | GET | 获取 Agent 详情 |
| `/:id` | PUT | 更新 Agent |
| `/:id` | DELETE | 删除 Agent |
| `/builtin` | GET | 列出内置 Agent |

### 8. IM API (`/api/v1/im`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/config` | GET | 获取 IM 配置 |
| `/config` | PUT | 更新 IM 配置 |
| `/status` | GET | 获取 IM 状态 |
| `/:platform/webhook` | POST | Webhook 回调 |

### 9. 系统 API (`/api/v1/system`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/info` | GET | 获取系统信息 |
| `/health` | GET | 健康检查 |
| `/config` | GET | 获取配置 |
| `/config` | PUT | 更新配置 |

### 10. 评估 API (`/api/v1/evaluation`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/dataset` | GET | 列出数据集 |
| `/dataset` | POST | 创建数据集 |
| `/dataset/:id/run` | POST | 运行评估 |
| `/result` | GET | 查看评估结果 |

---

## 使用示例

### 示例 1: 简单问答 (非流式)

```bash
curl -X POST http://localhost:8080/api/v1/session/{sessionId}/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是 RAG？",
    "knowledgeBaseIds": ["kb1", "kb2"]
  }'
```

### 示例 2: 流式问答

```bash
curl -X POST http://localhost:8080/api/v1/session/{sessionId}/chat/stream \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "query": "什么是 RAG？",
    "knowledgeBaseIds": ["kb1"]
  }' --no-buffer
```

### 示例 3: Agent 推理

```bash
curl -X POST http://localhost:8080/api/v1/session/{sessionId}/agent \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "query": "分析一下这些数据",
    "agentId": "data-analyst",
    "knowledgeBaseIds": ["kb1"],
    "enableWebSearch": true
  }' --no-buffer
```

### 示例 4: 上传文件

```bash
curl -X POST http://localhost:8080/api/v1/knowledge/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/document.pdf" \
  -F "knowledgeBaseId=kb1" \
  -F "title=我的文档"
```

### 示例 5: 创建知识库

```bash
curl -X POST http://localhost:8080/api/v1/knowledgebase \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "技术文档库",
    "description": "包含所有技术相关文档",
    "type": "document"
  }'
```

### 示例 6: 搜索知识

```bash
curl -X POST http://localhost:8080/api/v1/knowledge/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "RAG",
    "knowledgeBaseIds": ["kb1"],
    "limit": 10
  }'
```

---

## Go SDK 使用

WeKnora 提供官方 Go SDK，位于 `client/` 目录。

### 安装

```bash
go get github.com/Tencent/WeKnora/client
```

### 示例代码

```go
package main

import (
    "context"
    "fmt"
    "log"

    "github.com/Tencent/WeKnora/client"
)

func main() {
    // 创建客户端
    c := client.NewClient("http://localhost:8080")
    c.SetAPIKey("your-api-key") // 或使用 SetToken()

    ctx := context.Background()

    // 创建会话
    session, err := c.CreateSession(ctx, &client.CreateSessionRequest{
        Name: "我的会话",
    })
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println("Session:", session.ID)

    // 发送消息
    resp, err := c.Chat(ctx, session.ID, &client.ChatRequest{
        Query:             "你好",
        KnowledgeBaseIDs:  []string{"kb1"},
    })
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println("Answer:", resp.Answer)
}
```

---

## 错误处理

所有 API 使用统一的响应格式：

```json
{
  "success": true,
  "data": {},
  "message": "success",
  "code": 0
}
```

错误响应：

```json
{
  "success": false,
  "data": null,
  "message": "错误描述",
  "code": 400
}
```

### 常见 HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 403 | 禁止访问 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## Webhook

### IM 消息 Webhook

配置 IM 平台的 Webhook URL 为：
```
https://your-domain.com/api/v1/im/{platform}/webhook
```

支持的平台：
- wecom (企业微信)
- feishu (飞书)
- slack
- telegram
- dingtalk
- mattermost
- wechat (微信公众号)
