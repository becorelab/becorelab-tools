"""쿠팡 로켓그로스 — 매일 어제치 옵션별 매출 수집 → ERP gross_daily_sales 적재

방식 (2026-06-09 확립):
- 대표님 채움 Wing 세션이 저장된 /ChromeCDP 프로필을 직접 열어(로그인 0회) Akamai 회피
- route로 vi-detail-search 요청 본문을 "어제 1일" 범위로 치환 (페이지 정상요청이라 통과)
- 옵션별 GMV(매출, 주문일 기준)/판매량/주문수 획득
- 물류비 = 단가표(gross_logistics_rates.json) × 수량 (입출고 개당비례 + 배송 건당)
- 수수료 = GMV × 8.58% (로켓그로스 기본요율 근사)
- ERP gross_daily_sales upsert (sale_date+option_id PK, 멱등)
※ connect_over_cdp는 launchd headless 크롬의 리소스 제약 탓에 CDP 응답 timeout → 프로필 직접 기동 방식 채택.
※ 정확한 정산(프로모션 면제/저가할인/실수수료)은 월정산 파일로 보정.
"""
import json, time, sys, sqlite3, os, subprocess
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

SALES_URL = "https://wing.coupang.com/tenants/business-insight/sales-analysis"
ERP_DB = "/Users/macmini_ky/ClaudeAITeam/erp/erp.db"
RATES = "/Users/macmini_ky/ClaudeAITeam/accounting/gross_logistics_rates.json"
PROFILE = "/Users/macmini_ky/ChromeCDP"  # 대표님 채움 Wing 세션 저장된 프로필
CFT = ("/Users/macmini_ky/Library/Caches/ms-playwright/chromium-1217/"
       "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
CDP_LAUNCHD = "com.becorelab.chrome-cdp"
COMMISSION_RATE = 0.0858

def _uid():
    return str(os.getuid())

def fetch_options_for(date_str):
    """하루치 옵션별 판매 [(oid,name,units,gmv,orders)].
    launchd 상시 CDP 크롬 정지 → 같은 프로필 직접 열기(제약 없는 크롬) → 작업 → 종료 → launchd 재가동."""
    body = json.dumps({"startDate":date_str,"endDate":date_str,"registrationTypes":["NORMAL","RFM"],
                       "pageNumber":0,"pageSize":100,"sortBy":"GMV","sortOrder":"DESC",
                       "vendorItemIds":[],"includeSoldVICount":True})
    got = []
    subprocess.run(["launchctl","bootout",f"gui/{_uid()}/{CDP_LAUNCHD}"], capture_output=True)
    subprocess.run(["pkill","-f",f"user-data-dir={PROFILE}"], capture_output=True)
    time.sleep(3)
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                PROFILE, headless=True, executable_path=CFT,
                args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-dev-shm-usage"])
            pg = ctx.new_page()
            def handle(route):
                if 'vi-detail-search' in route.request.url and route.request.method=='POST':
                    route.continue_(post_data=body)
                else:
                    route.continue_()
            pg.route('**/vi-detail-search', handle)
            def on_resp(r):
                if 'vi-detail-search' in r.url:
                    try: got.append(r.json())
                    except Exception: pass
            pg.on('response', on_resp)
            pg.goto(SALES_URL, wait_until='domcontentloaded', timeout=60000)
            if 'xauth' in pg.url or 'login' in pg.url.lower():
                ctx.close(); raise RuntimeError("세션 만료 — 대표님 채움 Wing 재로그인 필요")
            try: pg.wait_for_load_state('networkidle', timeout=20000)
            except Exception: pass
            for _ in range(3): pg.mouse.wheel(0,1200); time.sleep(2)
            time.sleep(3)
            ctx.close()
    finally:
        subprocess.run(["launchctl","bootstrap",f"gui/{_uid()}",
                        f"/Users/macmini_ky/Library/LaunchAgents/{CDP_LAUNCHD}.plist"], capture_output=True)
    rows = []
    for r in got:
        if isinstance(r,dict) and 'vendorItems' in r:
            for vi in r['vendorItems']:
                d=vi['vendorItemDetails']; m=vi['businessInsightsMetricsResponse']
                gmv=m.get('totalGmv',0); units=m.get('totalUnitsSold',0); orders=m.get('totalOrders',0)
                if gmv or units:
                    rows.append((str(d['vendorItemId']), d['itemName'], int(units), round(gmv), int(orders)))
    return rows

def upsert(date_str, rows):
    rates = json.load(open(RATES, encoding='utf-8'))
    conn = sqlite3.connect(ERP_DB, timeout=30)
    n=0
    for oid,name,units,gmv,orders in rows:
        rt = rates.get(oid, {})
        wh = (rt.get('입출고비_개당') or 0) * units
        ship = (rt.get('배송비_개당') or 0) * orders
        comm = round(gmv * COMMISSION_RATE)
        profit = round(gmv - wh - ship - comm)
        conn.execute("""INSERT INTO gross_daily_sales
            (sale_date,option_id,item_name,units_sold,gmv,orders,warehousing_fee,shipping_fee,commission,est_profit,source,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?, 'wing_cdp_daily', datetime('now','localtime'))
            ON CONFLICT(sale_date,option_id) DO UPDATE SET
              item_name=excluded.item_name, units_sold=excluded.units_sold, gmv=excluded.gmv,
              orders=excluded.orders, warehousing_fee=excluded.warehousing_fee, shipping_fee=excluded.shipping_fee,
              commission=excluded.commission, est_profit=excluded.est_profit, updated_at=excluded.updated_at""",
            (date_str,oid,name,units,gmv,orders,wh,ship,comm,profit))
        n+=1
    conn.commit(); conn.close()
    return n

def main():
    if len(sys.argv)>1 and sys.argv[1].count('-')==2:
        date_str = sys.argv[1]
    else:
        date_str = (datetime.now()-timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 그로스 일별 수집: {date_str}")
    rows = fetch_options_for(date_str)
    print(f"  옵션 {len(rows)}개 수집")
    if not rows:
        print("  (판매 없음 또는 수집 실패)"); return
    n = upsert(date_str, rows)
    tot_gmv = sum(r[3] for r in rows)
    print(f"  ✅ {n}개 옵션 → gross_daily_sales 적재. GMV합 {tot_gmv:,}원")

if __name__ == "__main__":
    main()
