"""그로스 profit-status 응답 구조 진단용 (1회성)

목적: 페이지 기본 로드(최근7일) 시 발화하는 profit-status 응답 전체를
      파일로 덤프해서, 일별(daily) breakdown이 들어있는지 확인.
      → 있으면 '이번 달' 버튼 클릭 없이도 매일 어제치 추출 가능.

버튼 클릭 안 함 (Akamai 부담 최소화). 로그인 1회만.
출력: automation/logs/gross_probe_dump.json (요청본문 + 응답 전체)
"""
import json, time, sys
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
from coupang_ad_config import ACCOUNTS

AUTH = "https://advertising.coupang.com/user/login?_cap_client=WING&returnUrl=%2Fdashboard"
SETTLE_URL = "https://wing.coupang.com/tenants/rfm/settlements/home"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")
DUMP = "/Users/macmini_ky/ClaudeAITeam/automation/logs/gross_probe_dump.json"


def main(account="chaewoom", headless=True):
    acct = ACCOUNTS[account]
    captured = []

    def on_resp(r):
        if "profit-status/search" in r.url:
            try:
                captured.append({"url": r.url, "req": r.request.post_data, "resp": r.json()})
            except Exception as e:
                captured.append({"url": r.url, "error": str(e)})

    with sync_playwright() as p:
        b = p.chromium.launch(headless=headless, channel="chrome",
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"])
        ctx = b.new_context(viewport={"width": 1600, "height": 1000}, locale="ko-KR",
                            user_agent=UA, accept_downloads=True)
        pg = ctx.new_page(); Stealth().apply_stealth_sync(pg)
        pg.on("response", on_resp)

        print(f"[{datetime.now():%H:%M:%S}] 로그인 시도...")
        pg.goto(AUTH, wait_until="domcontentloaded", timeout=60000); time.sleep(3)
        if "Access Denied" in pg.inner_text("body"):
            b.close(); print("❌ Akamai Access Denied"); sys.exit(1)
        if pg.query_selector('input[name="username"]'):
            pg.fill('input[name="username"]', acct["id"])
            pg.fill('input[name="password"]', acct["pw"]); time.sleep(1)
            try:
                with pg.expect_navigation(timeout=30000, wait_until="load"):
                    pg.click('input[name="login"]')
            except Exception:
                pass
            time.sleep(4)
        if "xauth" in pg.url or "/login" in pg.url.lower():
            b.close(); print(f"❌ 로그인 실패 (URL={pg.url[:60]})"); sys.exit(1)
        print(f"✅ 로그인 성공 → 정산현황 로드 (버튼 클릭 안 함)")

        pg.goto(SETTLE_URL, wait_until="domcontentloaded", timeout=60000); time.sleep(10)
        b.close()

    with open(DUMP, "w", encoding="utf-8") as f:
        json.dump(captured, f, ensure_ascii=False, indent=2)
    print(f"\n캡처 {len(captured)}건 → {DUMP}")
    # 구조 요약 출력
    for i, c in enumerate(captured):
        if "resp" in c:
            r = c["resp"]
            print(f"\n[{i}] 요청본문: {c.get('req')}")
            print(f"    응답 최상위 키: {list(r.keys()) if isinstance(r, dict) else type(r)}")
            # 일별 리스트 후보 탐색
            if isinstance(r, dict):
                for k, v in r.items():
                    if isinstance(v, list):
                        print(f"    🔍 리스트 필드 '{k}' (len={len(v)})"
                              + (f" 첫항목키: {list(v[0].keys())}" if v and isinstance(v[0], dict) else ""))


if __name__ == "__main__":
    main(headless="--headed" not in sys.argv)
