"""쿠팡 로켓그로스 — 매일 어제치 옵션별 매출 수집 → ERP gross_daily_sales 적재

방식 (2026-06-10 확정):
- 9222 헤드리스 CDP 크롬(launchd 상주)에 connect_over_cdp → 로그인0, Akamai 회피, 화면 X
- 세션 만료 시 백업쿠키(gross_session_cookies.json) 자동 주입 → 복원 (검증됨)
- route로 vi-detail-search 요청을 "어제 1일"로 치환(페이지 정상요청이라 통과)
- 옵션별 GMV(주문일 기준)/판매량/주문수 → 물류비 단가표 + 수수료 → ERP gross_daily_sales(멱등)
- 수집 성공 시 쿠키 재백업(세션 갱신분 저장)

※ 백업쿠키도 만료되면(서버측 세션 종료) 대표님 재로그인 필요:
   automation/gross_relogin.sh 실행 → 헤드풀 크롬 떠서 로그인 → 쿠키 백업 → 헤드리스 복귀
※ 정확한 정산(프로모션 면제/저가할인)은 월정산 파일로 보정.
"""
import json, time, sys, sqlite3, os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"
SALES_URL = "https://wing.coupang.com/tenants/business-insight/sales-analysis"
ERP_DB = "/Users/macmini_ky/ClaudeAITeam/erp/erp.db"
RATES = "/Users/macmini_ky/ClaudeAITeam/accounting/gross_logistics_rates.json"
COOKIE_BACKUP = "/Users/macmini_ky/ClaudeAITeam/automation/gross_session_cookies.json"
COMMISSION_RATE = 0.0858

def _clean_cookies(raw):
    out = []
    for c in raw:
        d = {k: c[k] for k in ('name','value','domain','path') if k in c}
        if c.get('expires',-1) > 0: d['expires'] = c['expires']
        d['httpOnly'] = c.get('httpOnly', False); d['secure'] = c.get('secure', False)
        ss = c.get('sameSite','Lax'); d['sameSite'] = ss if ss in ('Strict','Lax','None') else 'Lax'
        out.append(d)
    return out

def _logged_in(pg):
    return not ('xauth' in pg.url or 'login' in pg.url.lower())

def fetch_options_for(date_str):
    body = json.dumps({"startDate":date_str,"endDate":date_str,"registrationTypes":["NORMAL","RFM"],
                       "pageNumber":0,"pageSize":100,"sortBy":"GMV","sortOrder":"DESC",
                       "vendorItemIds":[],"includeSoldVICount":True})
    got = []
    def attach(pg):
        def handle(route):
            if 'vi-detail-search' in route.request.url and route.request.method=='POST':
                route.continue_(post_data=body)
            else: route.continue_()
        pg.route('**/vi-detail-search', handle)
        def on_resp(r):
            if 'vi-detail-search' in r.url:
                try: got.append(r.json())
                except Exception: pass
        pg.on('response', on_resp)
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=30000)
        ctx = b.contexts[0]
        pg = ctx.new_page(); attach(pg)
        pg.goto(SALES_URL, wait_until='domcontentloaded', timeout=60000)
        # 세션 만료 시 백업쿠키 주입 후 재시도
        if not _logged_in(pg):
            pg.close()
            if os.path.exists(COOKIE_BACKUP):
                try: ctx.add_cookies(_clean_cookies(json.load(open(COOKIE_BACKUP, encoding='utf-8'))))
                except Exception: pass
                pg = ctx.new_page(); attach(pg)
                pg.goto(SALES_URL, wait_until='domcontentloaded', timeout=60000)
            if not _logged_in(pg):
                pg.close()
                raise RuntimeError("세션 만료 — 백업쿠키도 만료. gross_relogin.sh로 대표님 재로그인 필요")
        try: pg.wait_for_load_state('networkidle', timeout=20000)
        except Exception: pass
        for _ in range(3): pg.mouse.wheel(0,1200); time.sleep(2)
        time.sleep(3)
        # 수집 성공 → 쿠키 재백업 (세션 갱신분)
        try: json.dump(ctx.cookies(), open(COOKIE_BACKUP,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
        except Exception: pass
        pg.close()  # 새 탭만 (b.close() 안 함 → 상주 크롬 유지)
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
    conn = sqlite3.connect(ERP_DB, timeout=30); n=0
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
    conn.commit(); conn.close(); return n

def sync_to_sales(date_str):
    """gross_daily_sales(해당일) → ERP sales 일별 집계 반영 (매출 화면에 보이게).
    채널='비코어랩 쿠팡 채움(자동)'(partner 90) 자리에 그로스 GMV 채움. 멱등."""
    conn = sqlite3.connect(ERP_DB, timeout=30)
    g = conn.execute("SELECT option_id,item_name,units_sold,gmv FROM gross_daily_sales WHERE sale_date=?", (date_str,)).fetchall()
    if not g:
        conn.close(); return 0
    gmv_sum = round(sum(r[3] for r in g))
    supply = round(gmv_sum/1.1); tax = gmv_sum - supply
    CH = '비코어랩 쿠팡 그로스'
    # 기존 그 채널 해당일 row 삭제(0원 자동분 + 이전 그로스분) → 멱등
    conn.execute("DELETE FROM sales WHERE channel=? AND sale_date=?", (CH, date_str))
    cur = conn.execute("""INSERT INTO sales
        (sale_date,partner_id,channel,channel_order_no,total_supply,total_tax,total_amount,status,source)
        VALUES (?,?,?,?,?,?,?, 'confirmed','wing_gross')""",
        (date_str, 90, CH, f"GROSS-{date_str}", supply, tax, gmv_sum))
    sid = cur.lastrowid
    for oid,name,units,gmv in g:
        conn.execute("INSERT INTO sale_lines (sale_id,product_name,qty,line_total) VALUES (?,?,?,?)",
                     (sid, name, units, round(gmv)))
    conn.commit(); conn.close(); return gmv_sum

def main():
    if len(sys.argv)>1 and sys.argv[1].count('-')==2:
        date_str = sys.argv[1]
    else:
        date_str = (datetime.now()-timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 그로스 일별 수집: {date_str}")
    try:
        rows = fetch_options_for(date_str)
    except Exception as e:
        print(f"  ❌ 수집 실패: {e}"); sys.exit(1)
    print(f"  옵션 {len(rows)}개 수집")
    if not rows:
        print("  (판매 없음)"); return
    n = upsert(date_str, rows)
    print(f"  ✅ {n}개 옵션 → gross_daily_sales 적재. GMV합 {sum(r[3] for r in rows):,}원")
    sv = sync_to_sales(date_str)
    print(f"  ✅ ERP sales 반영: {sv:,}원 (매출 화면에 그로스 표시)")

if __name__ == "__main__":
    main()
