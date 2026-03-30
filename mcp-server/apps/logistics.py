"""물류 대시보드 MCP 도구 (포트 8082)"""


def register(mcp, client, base_url):

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
    async def logistics_order_analysis() -> str:
        """재고 분석 (현재 재고 vs 판매속도 기반 발주 필요 여부)"""
        try:
            resp = await client.get(f"{base_url}/api/order-analysis")
            return resp.text
        except Exception as e:
            return f"[오류] 물류서버 연결 실패: {e}"
