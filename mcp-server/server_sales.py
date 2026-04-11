#!/usr/bin/env python3
"""
비코어랩 Sales MCP 서버 — 매출/물류 전용

평소 항상 켜두는 코어 서버. 매출/재고/발주 데이터 조회 전담.
도구 약 10개로 가벼움.
"""
import httpx
from mcp.server.fastmcp import FastMCP

from config import LOGISTICS_BASE, TIMEOUT
from apps import logistics

mcp = FastMCP(
    "becorelab-sales",
    instructions="""비코어랩 매출/물류 데이터 서버 (iLBiA 브랜드).

## 가장 빠른 길: 모닝 브리핑
- '오늘 현황', '브리핑', '모닝' 요청 → logistics_morning_briefing 한 번 호출!
- 매출/재고/발주/골드박스/API비용 통합 (매일 3:50 자동 수집)

## 도구 흐름
- 일별 매출: logistics_daily_report
- 월간 누적: logistics_sales_monthly
- 옵션별/채널별: logistics_sales_options
- 정산 (장기 데이터, 38개월): logistics_settlement(month) / logistics_settlement_months
- 재고: logistics_inventory_report
- 발주 분석: logistics_order_analysis
"""
)
client = httpx.AsyncClient(timeout=TIMEOUT)

# 물류만 등록
logistics.register(mcp, client, LOGISTICS_BASE)

if __name__ == "__main__":
    mcp.run()
