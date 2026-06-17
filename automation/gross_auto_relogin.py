"""그로스 세션 자동 재로그인 — 대표님 손 없이 무인 복구 (2026-06-12 하치)

원리:
- 9222 CDP 헤드리스 크롬은 Akamai가 xauth 로그인 라우트를 차단함 (Access Denied)
- 그러나 광고 다운로드 크론과 동일한 stealth+Chrome 채널 브라우저는 xauth 로그인을 통과함 (매일 06:30 검증됨)
- → 별도 stealth 브라우저로 xauth SSO 로그인 → wing 진입 → 쿠키를 백업파일에 저장
- coupang_gross_daily.py가 백업쿠키를 CDP 컨텍스트에 주입해 복구하는 기존 경로를 그대로 재사용

사용: coupang_gross_daily.py가 세션 만료 시 자동 호출. 단독 실행도 가능:
  python3 gross_auto_relogin.py
"""
import json, time, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coupang_ad_config import ACCOUNTS
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

WING_AUTH_URL = "https://advertising.coupang.com/user/login?_cap_client=WING&returnUrl=%2Fdashboard"
SALES_URL = "https://wing.coupang.com/tenants/business-insight/sales-analysis"
COOKIE_BACKUP = "/Users/macmini_ky/ClaudeAITeam/automation/gross_session_cookies.json"


def auto_relogin(account_key="chaewoom"):
    """stealth 브라우저로 wing 세션 확보 → 쿠키 백업 갱신. 성공 시 True."""
    acct = ACCOUNTS[account_key]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome",
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            locale="ko-KR")
        pg = ctx.new_page()
        Stealth().apply_stealth_sync(pg)
        try:
            pg.goto(WING_AUTH_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)
            if "Access Denied" in pg.inner_text('body'):
                print("  [재로그인] ❌ Akamai 차단")
                return False
            ok = False
            BACKOFF = [0, 30, 45, 60, 90]  # 새벽/간헐 Akamai 차단 대응 — 점증 백오프로 끈질기게
            for attempt in range(5):
                if attempt:
                    print(f"  [재로그인] 재시도 {attempt+1}/5 — {BACKOFF[attempt]}초 대기")
                    time.sleep(BACKOFF[attempt])
                    pg.goto(WING_AUTH_URL, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(3)
                    if "Access Denied" in pg.inner_text('body'):  # 일시 차단이면 다음 재시도로
                        continue
                try:
                    pg.wait_for_selector('input[name="username"]', timeout=20000)
                except Exception:
                    continue
                pg.fill('input[name="username"]', acct["id"])
                pg.fill('input[name="password"]', acct["pw"])
                time.sleep(1)
                try:
                    with pg.expect_navigation(timeout=30000, wait_until="load"):
                        pg.click('input[name="login"]')
                    time.sleep(3)
                except Exception:
                    time.sleep(3)
                if "xauth" in pg.url and "advertising.coupang.com" not in pg.url:
                    continue
                ok = True
                break
            if not ok:
                print("  [재로그인] ❌ xauth 로그인 실패")
                return False
            pg.goto(SALES_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
            if "wing.coupang.com" not in pg.url or "login" in pg.url.lower():
                print(f"  [재로그인] ❌ wing 진입 실패: {pg.url[:80]}")
                return False
            json.dump(ctx.cookies(), open(COOKIE_BACKUP, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"  [재로그인] ✅ wing 세션 확보, 백업쿠키 갱신")
            return True
        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(0 if auto_relogin() else 1)
