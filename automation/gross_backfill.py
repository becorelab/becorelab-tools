"""그로스 일별 매출 백필 — 지정 날짜범위를 vi-detail로 수집해 ERP 적재 (멱등)
사용: python3 gross_backfill.py 2026-06-01 2026-06-07
"""
import json, time, sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
from coupang_gross_daily import upsert, _clean_cookies, COOKIE_BACKUP, CDP_URL, SALES_URL

def daterange(a, b):
    d0=datetime.strptime(a,"%Y-%m-%d"); d1=datetime.strptime(b,"%Y-%m-%d")
    cur=d0
    while cur<=d1:
        yield cur.strftime("%Y-%m-%d"); cur+=timedelta(days=1)

def make_handle(body):
    def handle(route):
        if 'vi-detail-search' in route.request.url and route.request.method=='POST':
            route.continue_(post_data=body)
        else:
            route.continue_()
    return handle

def collect(ctx, ds):
    body=json.dumps({"startDate":ds,"endDate":ds,"registrationTypes":["NORMAL","RFM"],
                     "pageNumber":0,"pageSize":100,"sortBy":"GMV","sortOrder":"DESC",
                     "vendorItemIds":[],"includeSoldVICount":True})
    got=[]
    pg=ctx.new_page()
    pg.route('**/vi-detail-search', make_handle(body))
    def on_resp(r):
        if 'vi-detail-search' in r.url:
            try: got.append(r.json())
            except Exception: pass
    pg.on('response', on_resp)
    pg.goto(SALES_URL, wait_until='domcontentloaded', timeout=60000)
    try: pg.wait_for_load_state('networkidle', timeout=15000)
    except Exception: pass
    for _ in range(3): pg.mouse.wheel(0,1200); time.sleep(1.5)
    time.sleep(2)
    pg.close()
    rows=[]
    for r in got:
        if isinstance(r,dict) and 'vendorItems' in r:
            for vi in r['vendorItems']:
                d=vi['vendorItemDetails']; m=vi['businessInsightsMetricsResponse']
                g=m.get('totalGmv',0); u=m.get('totalUnitsSold',0); o=m.get('totalOrders',0)
                if g or u: rows.append((str(d['vendorItemId']),d['itemName'],int(u),round(g),int(o)))
    return rows

def main():
    a,b=sys.argv[1],sys.argv[2]
    with sync_playwright() as p:
        br=p.chromium.connect_over_cdp(CDP_URL, timeout=30000)
        ctx=br.contexts[0]
        # 세션 체크/복원
        pg=ctx.new_page(); pg.goto(SALES_URL, wait_until='domcontentloaded', timeout=60000)
        if 'xauth' in pg.url or 'login' in pg.url.lower():
            pg.close()
            ctx.add_cookies(_clean_cookies(json.load(open(COOKIE_BACKUP,encoding='utf-8'))))
            pg=ctx.new_page(); pg.goto(SALES_URL, wait_until='domcontentloaded', timeout=60000)
            if 'xauth' in pg.url or 'login' in pg.url.lower():
                pg.close(); print("❌ 세션 만료 — 재로그인 필요"); sys.exit(1)
        pg.close()
        for ds in daterange(a,b):
            rows=collect(ctx, ds)
            if rows:
                upsert(ds, rows)
                print(f"  {ds}: {len(rows)}옵션 / GMV {sum(r[3] for r in rows):,}원")
            else:
                print(f"  {ds}: 판매없음")

if __name__=="__main__":
    main()
