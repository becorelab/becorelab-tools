"""소싱콕 Market Finder MCP 도구 (포트 8090)"""

import asyncio
import json as _json


def register(mcp, client, base_url):

    # ── 키워드 스캔 ──────────────────────────────────────────

    @mcp.tool()
    async def sourcing_scan_and_wait(keyword: str = "", timeout_seconds: int = 180) -> str:
        """새 키워드로 스캔 시작 + 완료까지 기다렸다가 결과를 한 번에 반환합니다.
        여러 번 poll 호출할 필요 없음! 도구 호출 1번으로 끝.
        keyword: 검색할 키워드 (필수)
        timeout_seconds: 최대 대기 시간 (기본 180초 = 3분)
        주의: 먼저 sourcing_scans로 기존 스캔 확인 후, 없을 때만 사용"""
        if not keyword:
            return "[오류] keyword를 입력해주세요."
        try:
            # 1. 스캔 시작
            start_resp = await client.post(f"{base_url}/api/scan/manual", json={"keyword": keyword})
            start_data = _json.loads(start_resp.text)
            scan_id = start_data.get("scan_id") or start_data.get("id")
            if not scan_id:
                return f"[오류] scan_id 못 받음: {start_resp.text[:200]}"

            # 2. 완료까지 polling (10초 간격)
            elapsed = 0
            while elapsed < timeout_seconds:
                await asyncio.sleep(10)
                elapsed += 10
                poll_resp = await client.get(f"{base_url}/api/scan/{scan_id}/poll")
                poll_data = _json.loads(poll_resp.text)
                status = poll_data.get("scan", {}).get("status", "")
                if status == "scanned":
                    # 3. 상세 데이터 반환
                    detail_resp = await client.get(f"{base_url}/api/scan/{scan_id}")
                    return f"완료! scan_id={scan_id}\n{detail_resp.text}"
                elif status == "failed":
                    return f"[실패] scan_id={scan_id}, status=failed\n{poll_resp.text[:300]}"
            return f"[타임아웃] {timeout_seconds}초 경과. scan_id={scan_id}로 나중에 sourcing_scan_detail 호출하세요."
        except Exception as e:
            return f"[오류] 스캔 실패: {e}"

    @mcp.tool()
    async def sourcing_wait_for_scans(scan_ids: str = "", timeout_seconds: int = 300) -> str:
        """여러 진행 중인 스캔이 완료될 때까지 기다립니다 (병렬 polling).
        scan_ids: 쉼표로 구분된 scan_id (예: '2614,2615,2616')
        timeout_seconds: 최대 대기 시간 (기본 300초 = 5분)"""
        if not scan_ids:
            return "[오류] scan_ids를 입력해주세요."
        try:
            ids = [int(s.strip()) for s in scan_ids.split(",") if s.strip()]
            pending = set(ids)
            completed = {}
            elapsed = 0
            while pending and elapsed < timeout_seconds:
                await asyncio.sleep(10)
                elapsed += 10
                # 병렬 polling
                tasks = [client.get(f"{base_url}/api/scan/{sid}/poll") for sid in pending]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for sid, res in zip(list(pending), results):
                    if isinstance(res, Exception):
                        continue
                    try:
                        data = _json.loads(res.text)
                        status = data.get("scan", {}).get("status", "")
                        if status in ("scanned", "failed"):
                            completed[sid] = status
                            pending.discard(sid)
                    except Exception:
                        pass
            # 결과 요약
            lines = [f"완료 {len(completed)}개, 진행중 {len(pending)}개"]
            for sid, status in completed.items():
                lines.append(f"  scan_id={sid}: {status}")
            for sid in pending:
                lines.append(f"  scan_id={sid}: 타임아웃 (아직 진행중)")
            return "\n".join(lines)
        except Exception as e:
            return f"[오류] {e}"

    @mcp.tool()
    async def sourcing_scan_new(keyword: str = "") -> str:
        """새 키워드로 시장조사(스캔)를 시작합니다. 주의: 먼저 sourcing_scans로 기존 스캔이 있는지 확인 후, 없을 때만 사용하세요!
        keyword: 검색할 키워드 (필수, 예: '스팟 분')"""
        if not keyword:
            return "[오류] keyword를 입력해주세요."
        try:
            resp = await client.post(f"{base_url}/api/scan/manual", json={"keyword": keyword})
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_scan_poll(scan_id: int = 0) -> str:
        """스캔 진행 상태를 확인합니다.
        scan_id: 스캔 ID (필수)"""
        if not scan_id:
            return "[오류] scan_id를 입력해주세요."
        try:
            resp = await client.get(f"{base_url}/api/scan/{scan_id}/poll")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_scans() -> str:
        """전체 시장조사(스캔) 목록을 가져옵니다. 새 스캔을 시작하기 전에 반드시 이 도구로 기존 스캔이 있는지 먼저 확인하세요!"""
        try:
            resp = await client.get(f"{base_url}/api/scans")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_scan_detail(scan_id: int = 0) -> str:
        """특정 스캔의 상세 정보 (상품, 키워드, 가격대 포함)를 가져옵니다.
        scan_id: 스캔 ID (필수)"""
        if not scan_id:
            return "[오류] scan_id를 입력해주세요."
        try:
            resp = await client.get(f"{base_url}/api/scan/{scan_id}")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_scan_keywords(scan_id: int = 0) -> str:
        """스캔의 키워드 데이터 (변형 + 쿠팡 자동완성 + 연관 키워드)를 가져옵니다.
        scan_id: 스캔 ID (필수)"""
        if not scan_id:
            return "[오류] scan_id를 입력해주세요."
        try:
            resp = await client.get(f"{base_url}/api/scan/{scan_id}/keywords")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_scan_status_update(scan_id: int = 0, status: str = "") -> str:
        """스캔 상태를 변경합니다 (GO / PASS 판정).
        scan_id: 스캔 ID (필수), status: 'go' 또는 'pass'"""
        if not scan_id or not status:
            return "[오류] scan_id와 status(go/pass)를 입력해주세요."
        try:
            resp = await client.put(f"{base_url}/api/scan/{scan_id}/status", json={"status": status})
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    # ── 자동 스캔 ────────────────────────────────────────────

    @mcp.tool()
    async def sourcing_autoscan_start(keywords: str = "", delay: int = 5) -> str:
        """키워드 목록으로 자동 스캔을 시작합니다.
        keywords: 쉼표로 구분된 키워드 (예: '스팟 분,여드름 패치,무릎 보호대')
        delay: 스캔 간격 초 (기본 5)"""
        if not keywords:
            return "[오류] keywords를 입력해주세요."
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        try:
            resp = await client.post(f"{base_url}/api/autoscan/start",
                                     json={"keywords": kw_list, "delay": delay})
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_autoscan_status() -> str:
        """자동 스캔 진행 상태를 확인합니다."""
        try:
            resp = await client.get(f"{base_url}/api/autoscan/status")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_autoscan_results() -> str:
        """자동 스캔 결과 (기회점수 순 정렬)를 가져옵니다."""
        try:
            resp = await client.get(f"{base_url}/api/autoscan/results")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_autoscan_stop() -> str:
        """진행 중인 자동 스캔을 중지합니다."""
        try:
            resp = await client.post(f"{base_url}/api/autoscan/stop")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    # ── 인사이트 (기회분석) ───────────────────────────────────

    @mcp.tool()
    async def sourcing_opportunities(status: str = "") -> str:
        """소싱 기회 상품(인사이트) 목록을 가져옵니다. 주의: 이 목록에는 개별 상품 데이터가 포함되지 않습니다! 특정 키워드의 상품(가격, 매출, 순위 등)을 보려면 반드시 sourcing_scan_detail(scan_id)을 추가 호출하세요.
        status: 'go' (GO 판정만), 'hold', 'drop' 또는 빈 문자열 (전체)"""
        params = {}
        if status:
            params["status"] = status
        try:
            resp = await client.get(f"{base_url}/api/opportunities", params=params)
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    # ── 상세분석 (가격대, 시장구조, 원가 등) ──────────────────

    @mcp.tool()
    async def sourcing_detail_analysis_start(scan_id: int = 0) -> str:
        """상세분석을 시작합니다 (상위 상품 상세페이지 수집 + AI 분석).
        가격대, 시장 구조, 소싱원가 분석이 포함됩니다.
        scan_id: 스캔 ID (필수)"""
        if not scan_id:
            return "[오류] scan_id를 입력해주세요."
        try:
            resp = await client.post(f"{base_url}/api/scan/{scan_id}/detail-analysis")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_detail_analysis(scan_id: int = 0) -> str:
        """상세분석 결과를 가져옵니다 (가격대, 시장구조, 소싱원가 포함).
        scan_id: 스캔 ID (필수)"""
        if not scan_id:
            return "[오류] scan_id를 입력해주세요."
        try:
            resp = await client.get(f"{base_url}/api/scan/{scan_id}/detail-analysis")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_detail_chat(scan_id: int = 0, question: str = "") -> str:
        """상세분석 데이터에 후속 질문을 합니다 (AI가 답변).
        scan_id: 스캔 ID (필수), question: 질문 (필수)
        예: '시장 평균가 대비 최적 진입가격은?', '원가 구조 분석해줘'"""
        if not scan_id or not question:
            return "[오류] scan_id와 question을 입력해주세요."
        try:
            resp = await client.post(f"{base_url}/api/scan/{scan_id}/detail-chat",
                                     json={"question": question})
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    # ── 리뷰 분석 ────────────────────────────────────────────

    @mcp.tool()
    async def sourcing_reviews_start(scan_id: int = 0) -> str:
        """상위 상품 리뷰 수집 + AI 분석을 시작합니다.
        scan_id: 스캔 ID (필수)"""
        if not scan_id:
            return "[오류] scan_id를 입력해주세요."
        try:
            resp = await client.post(f"{base_url}/api/scan/{scan_id}/reviews")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_reviews(scan_id: int = 0) -> str:
        """리뷰 분석 결과를 가져옵니다.
        scan_id: 스캔 ID (필수)"""
        if not scan_id:
            return "[오류] scan_id를 입력해주세요."
        try:
            resp = await client.get(f"{base_url}/api/scan/{scan_id}/reviews")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_reviews_chat(scan_id: int = 0, question: str = "") -> str:
        """리뷰 데이터에 후속 질문을 합니다 (AI가 답변).
        scan_id: 스캔 ID (필수), question: 질문 (필수)"""
        if not scan_id or not question:
            return "[오류] scan_id와 question을 입력해주세요."
        try:
            resp = await client.post(f"{base_url}/api/scan/{scan_id}/reviews/chat",
                                     json={"question": question})
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    # ── RFQ (견적요청) ───────────────────────────────────────

    @mcp.tool()
    async def sourcing_rfq_generate(scan_id: int = 0) -> str:
        """GO 판정된 스캔에서 RFQ를 자동 생성합니다.
        scan_id: 스캔 ID (필수)"""
        if not scan_id:
            return "[오류] scan_id를 입력해주세요."
        try:
            resp = await client.post(f"{base_url}/api/scan/{scan_id}/rfq/generate")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_rfqs() -> str:
        """견적 요청(RFQ) 목록을 가져옵니다."""
        try:
            resp = await client.get(f"{base_url}/api/rfqs")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_rfq_detail(rfq_id: int = 0) -> str:
        """특정 RFQ의 상세 정보 (견적 포함)를 가져옵니다.
        rfq_id: RFQ ID (필수)"""
        if not rfq_id:
            return "[오류] rfq_id를 입력해주세요."
        try:
            resp = await client.get(f"{base_url}/api/rfq/{rfq_id}")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_rfq_publish(rfq_id: int = 0) -> str:
        """RFQ를 알리바바에 발행합니다.
        rfq_id: RFQ ID (필수)"""
        if not rfq_id:
            return "[오류] rfq_id를 입력해주세요."
        try:
            resp = await client.post(f"{base_url}/api/rfq/{rfq_id}/publish")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_rfq_compare(rfq_id: int = 0) -> str:
        """RFQ에 대한 업체별 견적 비교표를 가져옵니다.
        rfq_id: RFQ ID (필수)"""
        if not rfq_id:
            return "[오류] rfq_id를 입력해주세요."
        try:
            resp = await client.get(f"{base_url}/api/rfq/{rfq_id}/compare")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    # ── 통계/히스토리 ────────────────────────────────────────

    @mcp.tool()
    async def sourcing_stats() -> str:
        """소싱콕 대시보드 통계 (스캔 수, 기회상품 수 등)를 가져옵니다."""
        try:
            resp = await client.get(f"{base_url}/api/stats")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"

    @mcp.tool()
    async def sourcing_history() -> str:
        """소싱 히스토리 타임라인을 가져옵니다."""
        try:
            resp = await client.get(f"{base_url}/api/history")
            return resp.text
        except Exception as e:
            return f"[오류] 소싱콕 연결 실패: {e}"
