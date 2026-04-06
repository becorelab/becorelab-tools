"""네이버 검색광고 API MCP 도구"""
import asyncio
import hashlib
import hmac
import base64
import time
import json as _json

import httpx


NAVER_AD_BASE = "https://api.searchad.naver.com"
NAVER_CUSTOMER_ID = "1985896"
NAVER_API_KEY = "010000000001ec664366c8b7d5aa8f5511280358c20f6e715cc1e8c60a347ef0a108f4ef59"
NAVER_SECRET_KEY = "AQAAAAAB7GZDZsi31aqPVREoA1jC88Jr8tixVLmHcRg+Tvqi0A=="


def _naver_headers(method: str, path: str) -> dict:
    """네이버 검색광고 API 인증 헤더 생성 (HMAC-SHA256)"""
    timestamp = str(int(time.time() * 1000))
    sign = f"{timestamp}.{method}.{path}"
    signature = hmac.new(
        NAVER_SECRET_KEY.encode("utf-8"),
        sign.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64.b64encode(signature).decode("utf-8")
    return {
        "X-Custid": NAVER_CUSTOMER_ID,
        "X-API-KEY": NAVER_API_KEY,
        "X-Timestamp": timestamp,
        "X-Signature": sig_b64,
        "Content-Type": "application/json",
    }


async def _get(path: str) -> str:
    """GET 요청 헬퍼"""
    headers = _naver_headers("GET", path)
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.get(f"{NAVER_AD_BASE}{path}", headers=headers)
        resp.raise_for_status()
        return resp.text


async def _post(path: str, body: dict | None = None) -> str:
    """POST 요청 헬퍼"""
    headers = _naver_headers("POST", path)
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(f"{NAVER_AD_BASE}{path}", headers=headers, json=body)
        resp.raise_for_status()
        return resp.text


async def _put(path: str, body: dict | None = None) -> str:
    """PUT 요청 헬퍼"""
    headers = _naver_headers("PUT", path)
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.put(f"{NAVER_AD_BASE}{path}", headers=headers, json=body)
        resp.raise_for_status()
        return resp.text


def register(mcp, client, base_url=None):
    """네이버 검색광고 도구를 MCP 서버에 등록합니다. base_url은 사용하지 않음."""

    # ── 1. 캠페인 목록 ──────────────────────────────────────
    @mcp.tool()
    async def naver_ad_campaigns() -> str:
        """네이버 검색광고 전체 캠페인 목록을 조회합니다.
        캠페인 ID, 이름, 상태, 예산 등을 확인할 수 있습니다."""
        try:
            return await _get("/ncc/campaigns")
        except Exception as e:
            return f"[오류] 네이버 검색광고 API 실패: {e}"

    # ── 2. 캠페인 상세 ──────────────────────────────────────
    @mcp.tool()
    async def naver_ad_campaign_detail(campaign_id: str) -> str:
        """특정 캠페인의 상세 정보를 조회합니다.
        campaign_id: 캠페인 ID (naver_ad_campaigns로 확인 가능)"""
        try:
            return await _get(f"/ncc/campaigns/{campaign_id}")
        except Exception as e:
            return f"[오류] 네이버 검색광고 API 실패: {e}"

    # ── 3. 광고그룹 목록 ────────────────────────────────────
    @mcp.tool()
    async def naver_ad_adgroups(campaign_id: str) -> str:
        """캠페인에 속한 광고그룹 목록을 조회합니다.
        campaign_id: 캠페인 ID"""
        try:
            return await _get(f"/ncc/adgroups?campaignId={campaign_id}")
        except Exception as e:
            return f"[오류] 네이버 검색광고 API 실패: {e}"

    # ── 4. 키워드 목록 ──────────────────────────────────────
    @mcp.tool()
    async def naver_ad_keywords(adgroup_id: str) -> str:
        """광고그룹에 등록된 키워드 목록을 조회합니다.
        adgroup_id: 광고그룹 ID (naver_ad_adgroups로 확인 가능)"""
        try:
            return await _get(f"/ncc/keywords?nccAdgroupId={adgroup_id}")
        except Exception as e:
            return f"[오류] 네이버 검색광고 API 실패: {e}"

    # ── 5. 키워드 도구 (검색량/경쟁도) ──────────────────────
    @mcp.tool()
    async def naver_ad_keyword_tool(keyword: str) -> str:
        """키워드의 월간 검색량, 경쟁도, 클릭률 등을 조회합니다.
        소싱 시 시장 수요 파악에 매우 유용합니다!
        keyword: 검색할 키워드 (쉼표로 여러 개 가능, 예: '건조기시트,섬유탈취제')"""
        try:
            return await _get(f"/keywordstool?hintKeywords={keyword}&showDetail=1")
        except Exception as e:
            return f"[오류] 네이버 검색광고 API 실패: {e}"

    # ── 6. 비즈머니 잔액 ────────────────────────────────────
    @mcp.tool()
    async def naver_ad_bizmoney() -> str:
        """네이버 검색광고 비즈머니(광고비 잔액)를 조회합니다.
        현재 충전 잔액과 사용 가능 금액을 확인합니다."""
        try:
            return await _get("/billing/bizmoney")
        except Exception as e:
            return f"[오류] 네이버 검색광고 API 실패: {e}"

    # ── 7. 캠페인별 통계 ────────────────────────────────────
    @mcp.tool()
    async def naver_ad_stats_campaign(
        campaign_id: str,
        start_date: str,
        end_date: str,
    ) -> str:
        """캠페인별 광고 성과 통계를 조회합니다 (비동기 리포트).
        노출수, 클릭수, 비용, CTR, CPC 등을 확인합니다.
        campaign_id: 캠페인 ID
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)"""
        try:
            body = {
                "reportTp": "CAMPAIGN_STATS",
                "statDt": start_date.replace("-", ""),
                "endDt": end_date.replace("-", ""),
                "campaignId": campaign_id,
            }
            # 리포트 생성 요청
            result = await _post("/stat-reports", body)
            report = _json.loads(result)
            report_job_id = report.get("reportJobId")
            if not report_job_id:
                return result  # 즉시 결과가 온 경우

            # 폴링 (최대 60초)
            for _ in range(12):
                await asyncio.sleep(5)
                status_text = await _get(f"/stat-reports/{report_job_id}")
                status = _json.loads(status_text)
                if status.get("status") == "READY":
                    # 결과 다운로드
                    download_url = status.get("downloadUrl")
                    if download_url:
                        async with httpx.AsyncClient(timeout=30) as c:
                            dl = await c.get(download_url)
                            return dl.text
                    return status_text
                elif status.get("status") == "FAILURE":
                    return f"[오류] 리포트 생성 실패: {status_text}"
            return "[오류] 리포트 생성 시간 초과 (60초)"
        except Exception as e:
            return f"[오류] 네이버 검색광고 API 실패: {e}"

    # ── 8. 키워드별 통계 ────────────────────────────────────
    @mcp.tool()
    async def naver_ad_stats_keyword(
        adgroup_id: str,
        start_date: str,
        end_date: str,
    ) -> str:
        """키워드별 광고 성과 통계를 조회합니다 (비동기 리포트).
        어떤 키워드가 효과적인지 분석할 수 있습니다.
        adgroup_id: 광고그룹 ID
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)"""
        try:
            body = {
                "reportTp": "KEYWORD_STATS",
                "statDt": start_date.replace("-", ""),
                "endDt": end_date.replace("-", ""),
                "nccAdgroupId": adgroup_id,
            }
            result = await _post("/stat-reports", body)
            report = _json.loads(result)
            report_job_id = report.get("reportJobId")
            if not report_job_id:
                return result

            for _ in range(12):
                await asyncio.sleep(5)
                status_text = await _get(f"/stat-reports/{report_job_id}")
                status = _json.loads(status_text)
                if status.get("status") == "READY":
                    download_url = status.get("downloadUrl")
                    if download_url:
                        async with httpx.AsyncClient(timeout=30) as c:
                            dl = await c.get(download_url)
                            return dl.text
                    return status_text
                elif status.get("status") == "FAILURE":
                    return f"[오류] 리포트 생성 실패: {status_text}"
            return "[오류] 리포트 생성 시간 초과 (60초)"
        except Exception as e:
            return f"[오류] 네이버 검색광고 API 실패: {e}"

    # ── 9. 키워드 예상 실적 ─────────────────────────────────
    @mcp.tool()
    async def naver_ad_estimate(keyword: str, bid: int = 500) -> str:
        """키워드의 예상 클릭수, 노출수, 비용을 추정합니다.
        입찰가별 예상 성과를 미리 확인할 수 있습니다.
        keyword: 키워드
        bid: 입찰가(원), 기본값 500원"""
        try:
            body = {
                "device": "PC",
                "keywordplus": False,
                "key": keyword,
                "bids": [bid],
            }
            return await _post("/estimate/performance", body)
        except Exception as e:
            return f"[오류] 네이버 검색광고 API 실패: {e}"

    # ── 10. 캠페인 ON/OFF ───────────────────────────────────
    @mcp.tool()
    async def naver_ad_campaign_toggle(campaign_id: str, enable: bool) -> str:
        """캠페인을 켜거나 끕니다.
        campaign_id: 캠페인 ID
        enable: True=켜기, False=끄기"""
        try:
            body = {
                "nccCampaignId": campaign_id,
                "userLock": not enable,  # userLock=True면 OFF
            }
            return await _put(f"/ncc/campaigns/{campaign_id}", body)
        except Exception as e:
            return f"[오류] 네이버 검색광고 API 실패: {e}"
