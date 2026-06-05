"""쿠팡 로켓그로스 매출 수집 → ERP settlement_monthly 갱신

설계 (2026-06-05, Akamai 안전):
- 채움컴퍼니(chaewoom) Wing 로그인 → 로켓그로스 정산현황 → profit-status 응답 가로채기
- ⚠️ API 직접 호출은 Akamai가 차단(xauth) → 반드시 대시보드 자체 호출의 response를 capture
- ⚠️ 하루 1회만 실행 (로그인 최소화). 권장: 매일 광고 다운로드 크론 직후 1회.
- profit-status: totalSalesAmountWithRefund(순매출) / totalDeductionAmount(차감) / profitAmount(이익)
  recognitionDate 기준(매출인식일), UTC=KST-9h

미검증: '이번 달' 버튼 클릭(MTD 트리거) — Akamai 식은 뒤 라이브 검증 필요.
캡처된 응답 중 당월 범위를 자동 선택, 없으면 마지막 응답(최근7일) fallback + 경고.
"""
import json, time, sys, sqlite3
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
from coupang_ad_config import ACCOUNTS

ERP_DB = "/Users/macmini_ky/ClaudeAITeam/erp/erp.db"
AUTH = "https://advertising.coupang.com/user/login?_cap_client=WING&returnUrl=%2Fdashboard"
SETTLE_URL = "https://wing.coupang.com/tenants/rfm/settlements/home"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")


def fetch_gross(account="chaewoom", headless=True):
    """로그인 → 정산현황 → profit-status 응답 전부 캡처해서 반환 [(req_postdata, json), ...]"""
    acct = ACCOUNTS[account]
    captured = []

    def on_resp(r):
        if "profit-status/search" in r.url:
            try:
                captured.append((r.request.post_data, r.json()))
            except Exception:
                pass

    with sync_playwright() as p:
        b = p.chromium.launch(headless=headless, channel="chrome",
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"])
        ctx = b.new_context(viewport={"width": 1600, "height": 1000}, locale="ko-KR",
                            user_agent=UA, accept_downloads=True)
        pg = ctx.new_page(); Stealth().apply_stealth_sync(pg)
        pg.on("response", on_resp)

        # 1) 로그인
        pg.goto(AUTH, wait_until="domcontentloaded", timeout=60000); time.sleep(3)
        if "Access Denied" in pg.inner_text("body"):
            b.close(); raise RuntimeError("Akamai Access Denied (로그인 단계)")
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
            b.close(); raise RuntimeError(f"로그인 실패 (URL={pg.url[:60]})")

        # 2) 정산현황 (기본 로드 = 최근7일 profit-status 발화)
        pg.goto(SETTLE_URL, wait_until="domcontentloaded", timeout=60000); time.sleep(9)
        try:
            pg.keyboard.press("Escape"); time.sleep(1)
        except Exception:
            pass
        # 3) '이번 달' 클릭 → 당월(MTD) profit-status 발화 (미검증, best-effort)
        for strat in ("locator", "js"):
            try:
                if strat == "locator":
                    pg.get_by_text("이번 달", exact=True).first.click(timeout=6000)
                else:
                    pg.evaluate("""()=>{const e=[...document.querySelectorAll('*')]
                        .find(x=>x.children.length===0&&(x.innerText||'').trim()==='이번 달');
                        if(e){(e.closest('button,[role=button],li,a')||e).click();}}""")
                time.sleep(6); break
            except Exception:
                continue
        b.close()
    return captured


def pick_for_month(captured, ym):
    """ym='2026-06' 의 1일~말일 범위에 가장 잘 맞는 캡처 선택. recognitionDateFrom(UTC)→KST 비교."""
    target_from = f"{ym}-01"
    best = None
    for req, j in captured:
        if not req:
            continue
        try:
            d = json.loads(req)
            frm_utc = d.get("recognitionDateFrom", "")[:19]
            # UTC → KST(+9h) 날짜
            kst = (datetime.strptime(frm_utc, "%Y-%m-%dT%H:%M:%S") + timedelta(hours=9)).strftime("%Y-%m-%d")
            if kst == target_from:
                best = j
        except Exception:
            continue
    if best:
        return best, True
    return (captured[-1][1] if captured else None), False


def main():
    today = datetime.now()
    ym = today.strftime("%Y-%m")
    print(f"[{today:%Y-%m-%d %H:%M}] 그로스 매출 수집 시작 ({ym})")
    captured = fetch_gross()
    print(f"  profit-status 캡처 {len(captured)}건")
    data, exact = pick_for_month(captured, ym)
    if not data:
        print("  ❌ 그로스 데이터 못 받음 (로그인/캡처 실패)"); sys.exit(1)
    sales = round(data.get("totalSalesAmountWithRefund", 0))
    profit = round(data.get("profitAmount", 0))
    if not exact:
        print(f"  ⚠️ 당월 정확 범위 캡처 실패 → fallback(최근7일 등) 사용. '이번 달' 클릭 검증 필요!")
    conn = sqlite3.connect(ERP_DB, timeout=30)
    conn.execute("""INSERT OR REPLACE INTO settlement_monthly (year_month, channel, amount, source)
                    VALUES (?,?,?,?)""", (ym, "쿠팡 그로스", sales, "wing_gross_cron"))
    conn.commit(); conn.close()
    print(f"  ✅ 그로스 {ym} 매출 {sales:,} (이익 {profit:,}) → ERP settlement_monthly 적재 (정확범위={exact})")


if __name__ == "__main__":
    main()
