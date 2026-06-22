"""
数据库模块 - SQLite 持久化
"""
import sqlite3
import json
import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional, List
from config import DB_PATH


def init_db():
    """同步初始化数据库（首次使用）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            url TEXT,
            version TEXT DEFAULT '1.0.0',
            capabilities TEXT,  -- JSON
            skills TEXT,        -- JSON array
            provider TEXT,
            provider_url TEXT,
            icon_url TEXT,
            tags TEXT,          -- JSON array
            auth_type TEXT DEFAULT 'none',  -- none, api_key, jwt, oauth
            a2a_endpoint TEXT,
            mcp_endpoint TEXT,
            status TEXT DEFAULT 'active',  -- active, inactive, maintenance
            rating REAL DEFAULT 0.0,
            rating_count INTEGER DEFAULT 0,
            call_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            last_seen TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller_id TEXT,
            callee_id TEXT,
            method TEXT,
            success INTEGER,
            latency_ms INTEGER,
            error TEXT,
            called_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT,
            rating INTEGER,
            comment TEXT,
            reviewer TEXT,
            created_at TEXT
        )
    """)
    # 全文搜索索引
    c.execute("CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_agents_tags ON agents(tags)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)")
    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


class AgentDB:
    """异步数据库操作"""

    def __init__(self):
        self.db_path = DB_PATH

    async def connect(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row

    async def close(self):
        await self.db.close()

    async def register_agent(self, agent_data: dict) -> dict:
        """注册或更新 Agent"""
        now = datetime.utcnow().isoformat()
        agent_data.setdefault("created_at", now)
        agent_data["updated_at"] = now
        agent_data["last_seen"] = now

        # 序列化复杂字段（Pydantic 模型、dict、list）
        for field in ["capabilities", "skills", "tags", "provider"]:
            val = agent_data.get(field)
            if val is not None:
                if hasattr(val, "model_dump"):  # Pydantic model
                    val = val.model_dump()
                if isinstance(val, (dict, list)):
                    agent_data[field] = json.dumps(val)
                elif isinstance(val, str):
                    pass  # already string
                else:
                    agent_data[field] = str(val)

        cols = list(agent_data.keys())
        vals = list(agent_data.values())

        # 检查是否存在
        existing = await self.db.execute(
            "SELECT agent_id FROM agents WHERE agent_id = ?", (agent_data["agent_id"],)
        )
        row = await existing.fetchone()

        if row:
            # UPDATE - 只更新提供的字段
            set_clauses = [f"{k} = ?" for k in cols]
            set_clauses.append("updated_at = ?")
            set_clauses.append("last_seen = ?")
            vals.extend([now, now])
            await self.db.execute(
                f"UPDATE agents SET {', '.join(set_clauses)} WHERE agent_id = ?",
                vals + [agent_data["agent_id"]]
            )
            msg = "updated"
        else:
            # INSERT
            ph = ", ".join(["?"] * len(cols))
            await self.db.execute(
                f"INSERT OR REPLACE INTO agents ({', '.join(cols)}) VALUES ({ph})",
                vals
            )
            msg = "registered"

        await self.db.commit()

        # 返回完整记录
        cursor = await self.db.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_data["agent_id"],)
        )
        row = await cursor.fetchone()
        return dict(row), msg

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        """获取单个 Agent"""
        cursor = await self.db.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_agents(
        self,
        query: str = "",
        tags: list = None,
        skill: str = "",
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "rating",
    ) -> tuple[List[dict], int]:
        """搜索 Agent"""
        conditions = ["status = 'active'"]
        params = []

        if query:
            conditions.append("(name LIKE ? OR description LIKE ? OR provider LIKE ?)")
            q = f"%{query}%"
            params.extend([q, q, q])

        if tags:
            for tag in tags:
                conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")

        if skill:
            conditions.append("skills LIKE ?")
            params.append(f"%{skill}%")

        where = " AND ".join(conditions)

        # 排序
        order_map = {
            "rating": "rating DESC",
            "calls": "call_count DESC",
            "recent": "last_seen DESC",
            "name": "name ASC",
        }
        order = order_map.get(sort_by, "rating DESC")

        # 总数
        total_cursor = await self.db.execute(
            f"SELECT COUNT(*) FROM agents WHERE {where}", params
        )
        total = (await total_cursor.fetchone())[0]

        # 数据
        params.extend([limit, offset])
        cursor = await self.db.execute(
            f"SELECT * FROM agents WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
            params
        )
        rows = await cursor.fetchall()
        agents = [dict(r) for r in rows]

        # 反序列化 JSON 字段
        for a in agents:
            for field in ["capabilities", "skills", "tags"]:
                val = a.get(field)
                if isinstance(val, str):
                    try:
                        a[field] = json.loads(val)
                    except:
                        a[field] = []
                elif val is None:
                    a[field] = []

        return agents, total

    async def heartbeat(self, agent_id: str):
        """Agent 心跳"""
        await self.db.execute(
            "UPDATE agents SET last_seen = ? WHERE agent_id = ?",
            (datetime.utcnow().isoformat(), agent_id)
        )
        await self.db.commit()

    async def record_call(self, caller_id: str, callee_id: str, method: str,
                          success: bool, latency_ms: int = 0, error: str = ""):
        """记录调用"""
        await self.db.execute(
            """INSERT INTO agent_calls
               (caller_id, callee_id, method, success, latency_ms, error, called_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (caller_id, callee_id, method, int(success), latency_ms, error,
             datetime.utcnow().isoformat())
        )
        # 更新 call_count
        await self.db.execute(
            "UPDATE agents SET call_count = call_count + 1 WHERE agent_id = ?",
            (callee_id,)
        )
        await self.db.commit()

    async def get_stats(self) -> dict:
        """平台统计"""
        cursor = await self.db.execute(
            "SELECT COUNT(*), SUM(call_count) FROM agents WHERE status='active'"
        )
        row = await cursor.fetchone()
        cursor2 = await self.db.execute("SELECT COUNT(*) FROM agents")
        row2 = await cursor2.fetchone()
        cursor3 = await self.db.execute("SELECT COUNT(*) FROM agent_calls WHERE called_at > datetime('now', '-24 hours')")
        row3 = await cursor3.fetchone()
        return {
            "total_agents": row2[0] or 0,
            "active_agents": row[0] or 0,
            "total_calls": row[1] or 0,
            "calls_24h": row3[0] or 0,
        }

    async def delete_agent(self, agent_id: str) -> bool:
        """删除 Agent"""
        await self.db.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
        await self.db.commit()
        return True
