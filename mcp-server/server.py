#!/usr/bin/env python3
"""
비코어랩 MCP 서버 — Claude 앱에서 사무실 API 호출

사용법: Claude Desktop 앱 설정에서 MCP 서버로 등록
"""
import httpx
from mcp.server.fastmcp import FastMCP

from config import LOGISTICS_BASE, SOURCING_BASE, TIMEOUT
from apps import logistics, sourcing, goldbox

mcp = FastMCP("becorelab")
client = httpx.AsyncClient(timeout=TIMEOUT)

# 앱별 도구 등록
logistics.register(mcp, client, LOGISTICS_BASE)
sourcing.register(mcp, client, SOURCING_BASE)
goldbox.register(mcp, client, SOURCING_BASE)  # 골드박스도 소싱콕 서버
# 새 앱 추가 시: from apps import newapp → newapp.register(mcp, client, BASE_URL)

if __name__ == "__main__":
    mcp.run()
