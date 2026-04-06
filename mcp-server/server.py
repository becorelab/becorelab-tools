#!/usr/bin/env python3
"""
비코어랩 MCP 서버 — Claude 앱에서 사무실 API 호출

사용법: Claude Desktop 앱 설정에서 MCP 서버로 등록
"""
import httpx
from mcp.server.fastmcp import FastMCP

from config import LOGISTICS_BASE, SOURCING_BASE, TIMEOUT
from apps import logistics, sourcing, goldbox, naver_searchad

mcp = FastMCP(
    "becorelab",
    instructions="""비코어랩 소싱/물류 데이터 조회 서버입니다.

## 모닝 브리핑 (가장 빠른 방법!)
- 대표님이 '오늘 현황', '브리핑', '모닝' 요청 → logistics_morning_briefing 한 번 호출!
- 매출/재고/발주/골드박스/API비용 전부 포함 (매일 3:50 자동 수집 데이터)
- 상세 데이터가 더 필요하면 개별 도구(logistics_*, sourcing_*)로 추가 조회

## 중요: 데이터 조회 순서
1. 기존 데이터를 먼저 확인하세요! 새로 스캔하기 전에 반드시 sourcing_scans로 기존 스캔 목록을 확인하세요.
2. 키워드가 이미 스캔되어 있으면 sourcing_scan_detail로 상세 데이터를 가져오세요.
3. 기존 스캔이 없을 때만 sourcing_scan_new로 새 스캔을 시작하세요.

## 도구 사용 흐름
- 기존 데이터 확인: sourcing_scans → sourcing_scan_detail(scan_id)
- 기회상품 조회: sourcing_opportunities (GO 판정된 것만 보려면 status=go)
- **중요**: sourcing_opportunities는 목록만 반환! 상품 상세(가격/매출/순위)를 보려면 반드시 sourcing_scan_detail(scan_id)을 호출하세요!
- 상세분석: sourcing_detail_analysis(scan_id) — 가격대, 시장구조, 원가
- 후속질문: sourcing_detail_chat(scan_id, question)
- 새 스캔: **sourcing_scan_and_wait(keyword)** 권장 — 시작+대기+결과를 한 번에! (도구 호출 1번)
  - 옛 방식: sourcing_scan_new → sourcing_scan_poll 반복 호출 (도구 사용 한도 빠르게 소진)
- 여러 스캔 대기: sourcing_wait_for_scans("2614,2615,2616") — 병렬 대기 후 결과 요약
- **중요**: 한 턴에 여러 스캔 결과가 필요하면 반드시 _and_wait 또는 _wait_for_scans 사용하세요!
"""
)
client = httpx.AsyncClient(timeout=TIMEOUT)

# 앱별 도구 등록
logistics.register(mcp, client, LOGISTICS_BASE)
sourcing.register(mcp, client, SOURCING_BASE)
goldbox.register(mcp, client, SOURCING_BASE)  # 골드박스도 소싱콕 서버
naver_searchad.register(mcp, client)  # 네이버 검색광고 (자체 URL 사용)

if __name__ == "__main__":
    mcp.run()
