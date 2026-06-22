"""
A2A 平台 API - FastAPI 路由
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import hashlib
from datetime import datetime

from database import AgentDB, init_db
from config import *

# ── Pydantic Models ──────────────────────────────────────────

class Capabilities(BaseModel):
    tools: bool = False
    streaming: bool = False
    push_notifications: bool = False
    state_transition_history: bool = False

class AgentCard(BaseModel):
    """Google A2A Agent Card 标准"""
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: Capabilities = Field(default_factory=Capabilities)
    skills: List[Dict[str, Any]] = []
    provider: Optional[Dict[str, str]] = None
    icon_url: Optional[str] = None
    tags: List[str] = []
    auth_type: str = "none"  # none, api_key, jwt, oauth


class AgentRegisterRequest(BaseModel):
    """Agent 注册请求"""
    name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., max_length=500)
    url: str = Field(..., description="Agent 的 A2A Webhook 或 HTTP 端点")
    version: str = "1.0.0"
    capabilities: Optional[Capabilities] = None
    skills: Optional[List[Dict[str, Any]]] = []
    provider_name: Optional[str] = None
    provider_url: Optional[str] = None
    icon_url: Optional[str] = None
    tags: Optional[List[str]] = []
    auth_type: str = "none"
    api_key: Optional[str] = None  # 如果需要认证


class AgentSearchRequest(BaseModel):
    query: str = ""
    tags: Optional[List[str]] = None
    skill: Optional[str] = None
    limit: int = 20
    offset: int = 0
    sort_by: str = "rating"


class A2AMessage(BaseModel):
    """A2A 协议消息"""
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


# ── FastAPI App ──────────────────────────────────────────────

app = FastAPI(
    title="灵犀 A2A Registry API",
    description="全球 AI Agent 发现、注册与协作平台",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局数据库实例
db: AgentDB = None


@app.on_event("startup")
async def startup():
    global db
    init_db()
    db = AgentDB()
    await db.connect()
    print(f"[A2A] 平台启动于 http://{HOST}:{PORT}")


@app.on_event("shutdown")
async def shutdown():
    if db:
        await db.close()


# ── 根路径 ────────────────────────────────────────────────────

@app.get("/")
async def root():
    """平台首页"""
    stats = await db.get_stats()
    return {
        "name": PLATFORM_NAME,
        "version": "1.0.0",
        "description": PLATFORM_DESCRIPTION,
        "urls": {
            "api": f"{PLATFORM_URL}/api",
            "agents": f"{PLATFORM_URL}/api/agents",
            "stats": f"{PLATFORM_URL}/api/stats",
            "health": f"{PLATFORM_URL}/health",
            "agent_card": f"{PLATFORM_URL}/.well-known/agent.json",
        },
        "stats": stats,
    }


# ── 健康检查 ─────────────────────────────────────────────────

@app.get("/health")
async def health():
    stats = await db.get_stats()
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), **stats}


# ── Agent 注册 ────────────────────────────────────────────────

@app.post("/api/agents")
async def register_agent(req: AgentRegisterRequest):
    """注册一个新 Agent"""
    # 生成 agent_id
    raw = f"{req.name}:{req.url}:{datetime.utcnow().isoformat()}"
    agent_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    # 构建 provider
    provider = None
    if req.provider_name:
        provider = {"name": req.provider_name, "url": req.provider_url or ""}

    # 构建 Agent Card
    card = {
        "agent_id": agent_id,
        "name": req.name,
        "description": req.description,
        "url": req.url,
        "version": req.version,
        "capabilities": (req.capabilities.model_dump() if req.capabilities else {"tools": False}),
        "skills": req.skills or [],
        "provider": provider,
        "icon_url": req.icon_url,
        "tags": req.tags or [],
        "auth_type": req.auth_type,
        "a2a_endpoint": req.url,
        "status": "active",
        "rating": 0.0,
        "rating_count": 0,
        "call_count": 0,
    }

    result, msg = await db.register_agent(card)

    # 反序列化
    for field in ["capabilities", "skills", "tags"]:
        val = result.get(field)
        if isinstance(val, str):
            import json
            try:
                result[field] = json.loads(val)
            except:
                result[field] = []

    return {
        "success": True,
        "message": f"Agent '{req.name}' {msg} successfully",
        "agent_id": agent_id,
        "agent_card_url": f"{PLATFORM_URL}/api/agents/{agent_id}/card",
        "agent": result,
    }


@app.get("/api/agents")
async def list_agents(
    q: str = Query("", description="搜索关键词"),
    tags: str = Query("", description="标签，逗号分隔"),
    skill: str = Query("", description="技能名称"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("rating", description="rating/calls/recent/name"),
):
    """搜索 Agent 列表"""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    agents, total = await db.list_agents(
        query=q, tags=tag_list, skill=skill,
        limit=limit, offset=offset, sort_by=sort
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "agents": agents,
    }


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    """获取单个 Agent 详情"""
    agent = await db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """删除 Agent"""
    ok = await db.delete_agent(agent_id)
    return {"success": ok, "agent_id": agent_id}


@app.post("/api/agents/{agent_id}/heartbeat")
async def heartbeat(agent_id: str):
    """Agent 心跳保活"""
    agent = await db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.heartbeat(agent_id)
    return {"success": True, "agent_id": agent_id}


# ── Agent Card (A2A 标准) ────────────────────────────────────

@app.get("/api/agents/{agent_id}/card")
async def get_agent_card(agent_id: str):
    """返回符合 Google A2A 规范的 Agent Card"""
    agent = await db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    import json
    caps = agent.get("capabilities")
    if isinstance(caps, str):
        caps = json.loads(caps)

    return {
        "name": agent["name"],
        "description": agent["description"],
        "url": agent.get("a2a_endpoint") or agent.get("url", ""),
        "version": agent.get("version", "1.0.0"),
        "capabilities": caps or {"tools": False},
        "skills": json.loads(agent["skills"]) if isinstance(agent["skills"], str) else agent.get("skills", []),
        "provider": {
            "name": agent.get("provider", "").get("name", "") if isinstance(agent.get("provider"), dict) else "",
            "url": agent.get("provider", "").get("url", "") if isinstance(agent.get("provider"), dict) else "",
        },
        "iconUrl": agent.get("icon_url"),
        "tags": json.loads(agent["tags"]) if isinstance(agent["tags"], str) else agent.get("tags", []),
    }


@app.get("/.well-known/agent.json")
async def well_known_agent_card():
    """平台自身的 Agent Card（A2A 发现端点）"""
    return {
        "name": A2A_AGENT_NAME,
        "description": PLATFORM_DESCRIPTION,
        "url": PLATFORM_URL,
        "version": A2A_AGENT_VERSION,
        "capabilities": {
            "tools": True,
            "streaming": False,
            "push_notifications": False,
            "state_transition_history": False,
        },
        "skills": [
            {
                "id": "agent-discovery",
                "name": "Agent Discovery",
                "description": "发现和搜索平台上的 AI Agent",
                "tags": ["discovery", "search", "registry"],
            },
            {
                "id": "agent-registration",
                "name": "Agent Registration",
                "description": "注册新 Agent 到平台",
                "tags": ["registration", "registry"],
            },
            {
                "id": "a2a-routing",
                "name": "A2A Message Routing",
                "description": "Agent 间消息路由转发",
                "tags": ["a2a", "routing", "messaging"],
            },
        ],
        "provider": {
            "name": "灵犀 (Lingxi)",
            "url": "https://github.com/nima54851/lingxi-agent-demos",
        },
        "tags": ["registry", "discovery", "a2a", "marketplace", "global"],
    }


# ── 统计 ──────────────────────────────────────────────────────

@app.get("/api/stats")
async def stats():
    """平台统计"""
    return await db.get_stats()


@app.get("/api/tags")
async def all_tags():
    """获取所有标签"""
    cursor = await db.db.execute("SELECT DISTINCT tags FROM agents WHERE status='active'")
    rows = await cursor.fetchall()
    import json
    all_tags = set()
    for row in rows:
        try:
            tags = json.loads(row[0]) if row[0] else []
            all_tags.update(tags)
        except:
            pass
    return sorted(all_tags)


# ── A2A 消息转发 ─────────────────────────────────────────────

@app.post("/api/a2a/relay")
async def a2a_relay(
    target_agent_id: str = Query(...),
    message: A2AMessage = None,
):
    """将 A2A 消息转发给目标 Agent"""
    target = await db.get_agent(target_agent_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target agent not found")

    endpoint = target.get("a2a_endpoint") or target.get("url")
    if not endpoint:
        raise HTTPException(status_code=400, detail="Target agent has no A2A endpoint")

    # 转发请求
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json=message.model_dump(exclude_none=True))
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Target agent timed out")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to relay: {str(e)}")


# ── 启动 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
