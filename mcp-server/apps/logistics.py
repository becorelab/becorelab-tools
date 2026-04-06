"""물류 대시보드 MCP 도구 (포트 8082)"""

import json
import os

MORNING_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "morning_data.json"
)


def register(mcp, client, base_url):

    @mcp.tool()
    async def logistics_morning_briefing() -> str:
        """오늘의 모닝 브리핑 데이터를 가져옵니다 (매일 3:50 자동 수집).
        매출, 재고, 발주, 골드박스 TOP3, API 비용, 서버 상태 전부 포함.
        대표님이 '브리핑', '오늘 현황', '모닝' 등 요청하면 이 도구를 사용하세요."""
        try:
            if not os.path.exists(MORNING_DATA_PATH):
                return "[오류] morning_data.json 없음 — 새벽 자동화가 아직 실행 안 됐거나 실패했어요."
            with open(MORNING_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"[오류] 모닝 데이터 로드 실패: {e}"

    @mcp.tool()
    async def logistics_daily_report(date: str = "") -> str:
        """어제(또는 지정일) 매출 리포트를 가져옵니다.
        date: YYYY-MM-DD 형식 (생략하면 어제)"""
        params = {"format": "text"}
        if date:
            params["date"] = date
        try:
            resp = await client.get(f"{base_url}/api/daily-report", params=params)
            return resp.text
        except Exception as e:
            return f"[오류] 물류서버 연결 실패: {e}"

    @mcp.tool()
    async def logistics_inventory_report() -> str:
        """현재 재고 현황 리포트를 가져옵니다."""
        try:
            resp = await client.get(f"{base_url}/api/inventory-report", params={"format": "text"})
            return resp.text
        except Exception as e:
            return f"[오류] 물류서버 연결 실패: {e}"

    @mcp.tool()
    async def logistics_sales_monthly(month: str = "") -> str:
        """월간 누적 매출을 가져옵니다.
        month: YYYY-MM 형식 (생략하면 이번 달)"""
        params = {}
        if month:
            params["month"] = month
        try:
            resp = await client.get(f"{base_url}/api/sales-monthly", params=params)
            return resp.text
        except Exception as e:
            return f"[오류] 물류서버 연결 실패: {e}"

    @mcp.tool()
    async def logistics_sales_daily(date: str = "", days: int = 7) -> str:
        """일별 매출 데이터를 가져옵니다.
        date: 특정일 (YYYY-MM-DD) 또는 days: 최근 N일"""
        params = {}
        if date:
            params["date"] = date
        else:
            params["days"] = str(days)
        try:
            resp = await client.get(f"{base_url}/api/sales-daily", params=params)
            return resp.text
        except Exception as e:
            return f"[오류] 물류서버 연결 실패: {e}"

    @mcp.tool()
    async def logistics_fetch_data(date: str = "") -> str:
        """이지어드민 매출 데이터 수집을 시작합니다 (백그라운드).
        date: YYYY-MM-DD (생략하면 오늘)"""
        params = {}
        if date:
            params["date"] = date
        try:
            resp = await client.post(f"{base_url}/api/fetch-data", params=params)
            return resp.text
        except Exception as e:
            return f"[오류] 물류서버 연결 실패: {e}"

    @mcp.tool()
    async def logistics_sales_options(date: str = "") -> str:
        """옵션별 판매 데이터를 가져옵니다 (색상/사이즈별 + 채널별 크로스 분석).
        date: YYYY-MM-DD (생략하면 어제)"""
        params = {}
        if date:
            params["date"] = date
        try:
            resp = await client.get(f"{base_url}/api/sales-daily-orders", params=params)
            return resp.text
        except Exception as e:
            return f"[오류] 물류서버 연결 실패: {e}"

    @mcp.tool()
    async def logistics_settlement_months() -> str:
        """매출 정산 데이터가 있는 전체 월 목록을 가져옵니다 (2023년~현재)."""
        try:
            resp = await client.get(f"{base_url}/api/settlements")
            return resp.text
        except Exception as e:
            return f"[오류] 물류서버 연결 실패: {e}"

    @mcp.tool()
    async def logistics_settlement(month: str = "") -> str:
        """특정 월의 정산 데이터를 가져옵니다 (채널별 매출/수량/상품 상세 포함).
        month: YYYY-MM 형식 (필수, 예: '2026-02')"""
        if not month:
            return "[오류] month를 입력해주세요 (예: 2026-02)"
        try:
            resp = await client.get(f"{base_url}/api/settlements/{month}")
            return resp.text
        except Exception as e:
            return f"[오류] 물류서버 연결 실패: {e}"

    @mcp.tool()
    async def logistics_order_analysis() -> str:
        """재고 분석 (현재 재고 vs 판매속도 기반 발주 필요 여부)"""
        try:
            resp = await client.get(f"{base_url}/api/order-analysis")
            return resp.text
        except Exception as e:
            return f"[오류] 물류서버 연결 실패: {e}"
