#!/usr/bin/env python3
"""
비코어랩 Ads MCP 서버 — 광고 전용 (메타 + 네이버)

광고 분석/입찰 작업할 때만 켜는 서버.
도구 약 15개.
"""
import httpx
from mcp.server.fastmcp import FastMCP

from config import TIMEOUT
from apps import meta_ads, naver_searchad

mcp = FastMCP(
    "becorelab-ads",
    instructions="""비코어랩 광고 데이터 서버 (메타 + 네이버 검색광고).

## 메타 광고 (페이스북/인스타)
- meta_ad_insights — 캠페인 성과 (일비아 / 세탁제품 계정)
- meta_ad_insights_all — 두 계정 한 번에
- meta_ad_campaigns — 캠페인 목록
- meta_ad_accounts — 계정 정보

## 네이버 검색광고
- naver_ad_campaigns — 캠페인 목록
- naver_ad_stats_campaign — 캠페인별 성과
- naver_ad_keyword_tool — 키워드 검색량/연관어

## 사용 팁
- 광고 ROI/ROAS 분석: meta_ad_insights → 금액 + 전환 자동 계산
- 키워드 시장조사: naver_ad_keyword_tool (월간 검색량 + 클릭률)
"""
)
client = httpx.AsyncClient(timeout=TIMEOUT)

# 광고 도구만 등록
meta_ads.register(mcp, client)
naver_searchad.register(mcp, client)

if __name__ == "__main__":
    mcp.run()
