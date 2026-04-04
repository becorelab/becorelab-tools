#!/usr/bin/env python3
"""
비코어랩 MCP 서버 — Claude 앱에서 사무실 API 호출

사용법: Claude Desktop 앱 설정에서 MCP 서버로 등록
"""
import httpx
from mcp.server.fastmcp import FastMCP

from config import LOGISTICS_BASE, SOURCING_BASE, TIMEOUT
from apps import logistics, sourcing, goldbox

mcp = FastMCP(
    "becorelab",
    instructions="""비코어랩 소싱/물류 데이터 조회 서버입니다.

## 중요: 데이터 조회 순서
1. 기존 데이터를 먼저 확인하세요! 새로 스캔하기 전에 반드시 sourcing_scans로 기존 스캔 목록을 확인하세요.
2. 키워드가 이미 스캔되어 있으면 sourcing_scan_detail로 상세 데이터를 가져오세요.
3. 기존 스캔이 없을 때만 sourcing_scan_new로 새 스캔을 시작하세요.

## 도구 사용 흐름
- 기존 데이터 확인: sourcing_scans → sourcing_scan_detail(scan_id)
- 기회상품 조회: sourcing_opportunities (GO 판정된 것만 보려면 status=go)
- 상세분석: sourcing_detail_analysis(scan_id) — 가격대, 시장구조, 원가
- 후속질문: sourcing_detail_chat(scan_id, question)
- 새 스캔: sourcing_scan_new(keyword) → sourcing_scan_poll(scan_id)로 상태 확인
"""
)
client = httpx.AsyncClient(timeout=TIMEOUT)

# 앱별 도구 등록
logistics.register(mcp, client, LOGISTICS_BASE)
sourcing.register(mcp, client, SOURCING_BASE)
goldbox.register(mcp, client, SOURCING_BASE)  # 골드박스도 소싱콕 서버
# 새 앱 추가 시: from apps import newapp → newapp.register(mcp, client, BASE_URL)

if __name__ == "__main__":
    mcp.run()
