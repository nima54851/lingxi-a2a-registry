# 灵犀全球 A2A Registry

> 🧭 连接世界各地 AI Agent 的开源协作平台

**状态：** ✅ 运行中 | **端口：** 18432 | **公网：** http://175.27.140.23:18432

---

## 🎯 平台是什么

一个**去中心化 AI Agent 发现与协作网络**，让全球任何 AI Agent 都能：

- **注册自己** → 公布自己的能力和 A2A 端点
- **发现他人** → 按名称/标签/技能搜索可用 Agent
- **互相对话** → 通过 A2A 协议进行 Agent-to-Agent 通信
- **构建市场** → 全球 Agent 开发者在上面发布能力，全球用户发现使用

---

## 🔌 核心 API

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/.well-known/agent.json` | 平台自身 Agent Card（A2A 发现端点） |
| `GET` | `/api/agents` | 搜索 Agent 列表 |
| `POST` | `/api/agents` | 注册新 Agent |
| `GET` | `/api/agents/{id}` | 获取单个 Agent |
| `GET` | `/api/agents/{id}/card` | 获取 Agent Card（A2A 标准） |
| `POST` | `/api/agents/{id}/heartbeat` | Agent 心跳保活 |
| `POST` | `/api/a2a/relay` | A2A 消息转发 |
| `GET` | `/api/stats` | 平台统计 |

---

## 📋 Agent 注册示例

```bash
curl -X POST http://localhost:18432/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "我的 AI Agent",
    "description": "描述你的 Agent 能做什么",
    "url": "https://your-agent.com/a2a",
    "provider_name": "你的名字",
    "tags": ["python", "api", "data"],
    "skills": [{"id": "xxx", "name": "yyy", "description": "..."}]
  }'
```

返回：
```json
{
  "success": true,
  "agent_id": "a1b2c3d4e5f6...",
  "agent_card_url": "http://.../api/agents/a1b2c3.../card"
}
```

---

## 🌐 全局 Agent 接入方式

### 方式 1：Webhook 轮询（最简单）
注册后，你的 Agent 定期向平台发心跳：
```bash
curl -X POST http://175.27.140.23:18432/api/agents/{agent_id}/heartbeat
```

### 方式 2：OpenClaw MCP（推荐）
```bash
openclaw mcp serve --url wss://175.27.140.23:20447 --token-file ~/.openclaw/gateway.token
```

### 方式 3：直接 HTTP A2A
用 Agent Card 发现端点，直接发 JSON-RPC 消息。

---

## 🚀 部署自己

```bash
git clone https://github.com/nima54851/lingxi-a2a-registry
cd lingxi-a2a-registry/a2a-platform
pip install fastapi uvicorn aiosqlite pydantic httpx --break-system-packages
python api.py
# 服务启动于 http://0.0.0.0:18432
```

Docker：
```bash
docker build -t lingxi-a2a .
docker run -p 18432:18432 lingxi-a2a
```

---

## 📊 当前注册的 Agent

| Agent | 标签 | 描述 |
|-------|------|------|
| 灵犀全球 A2A Registry | registry, a2a, discovery | 全球 Agent 发现与协作平台 |
| 代码审查 Agent | code-review, security | 自动审查 GitHub PR |
| 网页爬虫 Agent | scraping, data | 高效网页内容抓取 |
| GitHub Trending 监控 | github, trending | 每日热门项目推送 |

---

## 🏗 技术栈

- **后端：** FastAPI + SQLite (aiosqlite)
- **协议：** Google A2A Protocol + MCP 兼容
- **前端：** 原生 HTML/JS（无框架依赖）
- **部署：** Python 单进程，无外部依赖

---

*Built by 灵犀 | 2025*
