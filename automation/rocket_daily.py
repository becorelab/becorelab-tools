"""로켓배송 1P 매출 매일 자동 수집 → ERP sales 반영

흐름: supplyhub_scraper.scrape_supplyhub(이번달1일~어제) → 입고상세 items
     → 날짜별 발주(+)/반출(-) 공급가+세액 집계 → ERP sales 반영
launchd: 매일 1회 (그로스 광고크론처럼 빈도 낮춰 Akamai 회피)
※ supplyhub_login이 403(Akamai)이면 그날 스킵. 잦은 재시도 금지(계정잠김).
"""
import sys, re
from collections import defaultdict
from datetime import date, timedelta
sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/logistics")
sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
from supplyhub_scraper import scrape_supplyhub
from rocket_sales_sync import upsert

def num(v):
    if v is None: return 0
    if isinstance(v,(int,float)): return v
    try: return float(str(v).replace(',','').strip())
    except Exception: return 0

def items_to_daily(items):
    daily = defaultdict(lambda: {'supply':0.0,'tax':0.0})
    for r in items:
        gubun = r.get('구분') or r.get('구분 ') or ''
        t = str(r.get('입고/반출시각','') or '')[:10].replace('/','-')
        if not re.match(r'\d{4}-\d{2}-\d{2}', t): continue
        sign = 1 if '발주' in gubun else -1
        daily[t]['supply'] += num(r.get('총공급가액')) * sign
        daily[t]['tax'] += num(r.get('총세액')) * sign
    return daily

def main():
    today = date.today()
    first = today.replace(day=1).isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()
    print(f"[로켓 일별] 입고상세 수집: {first} ~ {yesterday}")
    res = scrape_supplyhub(first, yesterday)
    if not res:
        print("  ❌ supplyhub 수집 실패(Akamai 403 등) — 오늘 스킵"); sys.exit(1)
    items = res.get('items', [])
    if not items:
        print("  (입고 데이터 없음)"); return
    daily = items_to_daily(items)
    n = upsert(daily)
    tot = sum(round(v['supply'])+round(v['tax']) for v in daily.values())
    print(f"  ✅ 로켓 1P {n}일 → ERP sales 반영. 총 {tot:,}원")

if __name__ == "__main__":
    main()
