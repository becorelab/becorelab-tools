#!/usr/bin/env python3
"""
비코어랩 Sourcing MCP 서버 — 소싱 + 골드박스 전용

소싱콕(시장조사 / 인사이트 / RFQ) 작업할 때만 켜는 서버.
도구 약 33개.
"""
import httpx
from mcp.server.fastmcp import FastMCP

from config import SOURCING_BASE, TIMEOUT
from apps import sourcing, goldbox

mcp = FastMCP(
    "becorelab-sourcing",
    instructions="""비코어랩 소싱 데이터 서버 (소싱콕 + 골드박스).

## 데이터 조회 순서 (중요!)
1. 새 스캔 전에 반드시 sourcing_scans로 기존 목록 확인
2. 키워드 이미 있으면 sourcing_scan_detail(scan_id)로 가져오기
3. 없을 때만 sourcing_scan_and_wait(keyword) — 스캔+대기+결과를 한 번에

## 인사이트 / 상세분석
- sourcing_opportunities (status='go') — GO 판정 상품
- sourcing_opportunities는 목록만! 상품 상세는 sourcing_scan_detail(scan_id) 필수
- sourcing_detail_analysis(scan_id) — 가격대/시장구조/원가
- sourcing_detail_chat(scan_id, question) — 분석 데이터 후속 질문

## RFQ
- sourcing_rfq_generate → sourcing_rfq_publish → sourcing_rfq_compare

## 골드박스
- goldbox_top3 — 오늘의 골드박스 TOP3
- goldbox_auto_scan_results — 자동 스캔 결과 (기회점수 순)
"""
)
client = httpx.AsyncClient(timeout=TIMEOUT)

# 소싱 + 골드박스
sourcing.register(mcp, client, SOURCING_BASE)
goldbox.register(mcp, client, SOURCING_BASE)

if __name__ == "__main__":
    mcp.run()
