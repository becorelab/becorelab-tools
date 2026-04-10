#!/usr/bin/env python3
"""
비코어랩 Remote MCP 서버 — 모바일/외부 접속용 (SSE)

로컬 server.py와 동일한 도구, SSE transport로 외부 공개
Tailscale Funnel로 HTTPS 노출하여 claude.ai에서 사용

특징:
- 모든 도구 이름에 'becorelab_' prefix 자동 추가
- claude.ai의 도구 검색에 'becorelab' 키워드로 잘 잡히게 함
"""
import uvicorn
import httpx
from mcp.server.fastmcp import FastMCP

from config import LOGISTICS_BASE, SOURCING_BASE, TIMEOUT
from apps import logistics, sourcing, goldbox, naver_searchad, image_gen, meta_ads, obsidian

mcp = FastMCP(
    "becorelab",
    host="0.0.0.0",
    port=8500,
    instructions="""비코어랩(becorelab) 통합 데이터 서버 - iLBiA 브랜드 운영사

## 도구 카테고리 (모든 도구는 'becorelab_' prefix 사용)

### 📊 물류/매출 (becorelab_logistics_*)
- becorelab_logistics_morning_briefing - 모닝 브리핑 (매출/재고/발주/골드박스 통합)
- becorelab_logistics_daily_report - 일별 매출 리포트
- becorelab_logistics_inventory_report - 재고 현황
- becorelab_logistics_sales_daily/monthly - 매출 데이터

### 🔍 소싱 (becorelab_sourcing_*)
- becorelab_sourcing_scans - 스캔 목록
- becorelab_sourcing_scan_and_wait - 새 스캔 (블로킹)
- becorelab_sourcing_opportunities - GO 판정 상품

### 📢 메타 광고 (becorelab_meta_ad_*)
- becorelab_meta_ad_insights - 캠페인 성과 (일비아/세탁제품)
- becorelab_meta_ad_insights_all - 두 계정 한번에
- becorelab_meta_ad_campaigns - 캠페인 목록

### 🎯 네이버 검색광고 (becorelab_naver_ad_*)
### 🖼️ 이미지 생성 (becorelab_generate_*)
### 🎁 골드박스 (becorelab_goldbox_*)

### 📝 옵시디언 볼트 (becorelab_obsidian_*)
- becorelab_obsidian_list_files - 폴더 안 파일 목록
- becorelab_obsidian_read_file - 파일 읽기
- becorelab_obsidian_write_file - 파일 쓰기 (덮어쓰기)
- becorelab_obsidian_append_file - 파일에 내용 추가
- becorelab_obsidian_search - 키워드 검색
- becorelab_obsidian_recent_files - 최근 수정 파일

## 사용 팁
- 검색 키워드로 'becorelab'을 사용하면 모든 도구가 잡힙니다
- '모닝 브리핑', '오늘 현황' 요청 → becorelab_logistics_morning_briefing
- '광고 성과' 요청 → becorelab_meta_ad_insights_all
""",
)
client = httpx.AsyncClient(timeout=TIMEOUT)

# 앱별 도구 등록
logistics.register(mcp, client, LOGISTICS_BASE)
sourcing.register(mcp, client, SOURCING_BASE)
goldbox.register(mcp, client, SOURCING_BASE)
naver_searchad.register(mcp, client)
image_gen.register(mcp, client)
meta_ads.register(mcp, client)
obsidian.register(mcp, client)  # 옵시디언 볼트 (모바일에서도 접근 가능)

# Remote MCP는 핵심 도구만 노출 (모바일/원격 사용 최적화)
# 자주 쓰지 않는 deprecated 도구 제외
ALLOWED_TOOLS = {
    # 물류/매출 (5)
    "logistics_morning_briefing", "logistics_daily_report",
    "logistics_sales_daily", "logistics_sales_monthly", "logistics_inventory_report",
    # 메타 광고 (4)
    "meta_ad_accounts", "meta_ad_campaigns", "meta_ad_insights", "meta_ad_insights_all",
    # 소싱 (5)
    "sourcing_opportunities", "sourcing_scans", "sourcing_scan_detail",
    "sourcing_scan_and_wait", "sourcing_detail_analysis",
    # 옵시디언 (6)
    "obsidian_list_files", "obsidian_read_file", "obsidian_write_file",
    "obsidian_append_file", "obsidian_search", "obsidian_recent_files",
    # 네이버 광고 (3)
    "naver_ad_campaigns", "naver_ad_stats_campaign", "naver_ad_keyword_tool",
    # 이미지 생성 (2)
    "generate_image", "generate_banner",
    # 골드박스 (1)
    "goldbox_top3",
}

# 모든 도구 이름에 'becorelab_' prefix 추가 + 화이트리스트 필터링
PREFIX = "becorelab_"
old_tools = dict(mcp._tool_manager._tools)
mcp._tool_manager._tools = {}
for old_name, tool in old_tools.items():
    if old_name not in ALLOWED_TOOLS:
        continue
    new_name = f"{PREFIX}{old_name}"
    tool.name = new_name
    mcp._tool_manager._tools[new_name] = tool

print(f"[becorelab] {len(mcp._tool_manager._tools)} tools registered (filtered, with '{PREFIX}' prefix)")

if __name__ == "__main__":
    app = mcp.sse_app()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8500,
        timeout_keep_alive=600,  # SSE long-polling을 위한 keep-alive 10분
        timeout_graceful_shutdown=30,
        log_level="info",
    )
