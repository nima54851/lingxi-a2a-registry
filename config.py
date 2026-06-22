"""
灵犀 A2A Platform - 配置
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 服务配置
HOST = "0.0.0.0"
PORT = 18432

# 数据库
DB_PATH = os.path.join(BASE_DIR, "a2a_registry.db")

# A2A 协议配置
A2A_AGENT_NAME = "灵犀全球 A2A 平台"
A2A_AGENT_VERSION = "1.0.0"
A2A_AGENT_URL = f"http://{HOST}:{PORT}"

# OpenClaw MCP Serve 公网端点（已配置）
OPENCLAW_MCP_URL = "https://175.27.140.23:20447"
OPENCLAW_MCP_TOKEN = "SKzBr2s09RGQgRyxD0Dvuua5MJgAQyF4p8TwpG5HbYIQuOnQ"

# 平台信息
PLATFORM_NAME = "Lingxi A2A Registry"
PLATFORM_URL = f"http://{HOST}:{PORT}"
PLATFORM_DESCRIPTION = "全球 AI Agent 发现、注册与协作平台 — Built by 灵犀"
