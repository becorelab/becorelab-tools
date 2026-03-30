"""골드박스 MCP 도구 (소싱콕 포트 8090)"""


def register(mcp, client, base_url):

    @mcp.tool()
    async def goldbox_start() -> str:
        """쿠팡 골드박스 크롤링을 시작합니다. 실시간 딜 상품을 수집합니다."""
        try:
            resp = await client.post(f"{base_url}/api/goldbox/start")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def goldbox_status() -> str:
        """골드박스 크롤링 진행 상태를 확인합니다."""
        try:
            resp = await client.get(f"{base_url}/api/goldbox/status")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def goldbox_products() -> str:
        """수집된 골드박스 상품 목록을 가져옵니다."""
        try:
            resp = await client.get(f"{base_url}/api/goldbox/products")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def goldbox_history(date: str = "") -> str:
        """골드박스 일별 기록을 가져옵니다.
        date: YYYY-MM-DD (생략하면 날짜 목록 반환)"""
        try:
            if date:
                resp = await client.get(f"{base_url}/api/goldbox/history/{date}")
            else:
                resp = await client.get(f"{base_url}/api/goldbox/history")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def goldbox_auto_scan(date: str = "", delay: int = 5) -> str:
        """골드박스 상품에서 키워드 추출 → 시장조사 자동 스캔을 시작합니다.
        date: 기준일 (YYYY-MM-DD, 생략하면 최근), delay: 스캔 간격(초)"""
        try:
            data = {"delay": delay}
            if date:
                data["date"] = date
            resp = await client.post(f"{base_url}/api/goldbox/auto-scan", json=data)
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def goldbox_auto_scan_status() -> str:
        """골드박스 자동 스캔 진행 상태를 확인합니다."""
        try:
            resp = await client.get(f"{base_url}/api/goldbox/auto-scan/status")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def goldbox_auto_scan_results(date: str = "") -> str:
        """골드박스 자동 스캔 결과 (기회점수 순 정렬)를 가져옵니다.
        date: 필터 (YYYY-MM-DD, 생략하면 전체)"""
        try:
            params = {}
            if date:
                params["date"] = date
            resp = await client.get(f"{base_url}/api/goldbox/auto-scan/results", params=params)
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"
