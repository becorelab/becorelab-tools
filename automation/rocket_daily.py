"""로켓배송 1P 매출 매일 자동 수집 → ERP sales 반영

흐름: supplyhub_scraper.scrape_supplyhub(이번달1일~어제) → 입고상세 items
     → 날짜별 발주(+)/반출(-) 공급가+세액 집계 → ERP sales 반영
launchd: 매일 1회 (그로스 광고크론처럼 빈도 낮춰 Akamai 회피)
※ 서플라이허브 세션 만료/403(Akamai)이면 그날 스킵. 잦은 재시도 금지(계정잠김). 재로그인은 relogin.py로.
"""
import sys, re
from collections import defaultdict
from datetime import date, timedelta
sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/logistics")
sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
try:
    from alert import alert
except Exception:
    def alert(*a, **k):
        pass
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
        t = str(r.get('입고/반출시각') or r.get('입고/반출일자') or '')[:10].replace('/','-')
        if not re.match(r'\d{4}-\d{2}-\d{2}', t): continue
        sign = 1 if '발주' in gubun else -1
        daily[t]['supply'] += num(r.get('총공급가액')) * sign
        daily[t]['tax'] += num(r.get('총세액')) * sign
    return daily

def main():
    today = date.today()
    # 최근 40일 항상 수집 → 세션 끊겨 빠진 날도 다음 성공 때 자동 복구(멱등 upsert), 월경계 구멍 방지
    first = (today - timedelta(days=40)).isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()
    print(f"[로켓 일별] 입고상세 수집: {first} ~ {yesterday}")
    res = scrape_supplyhub(first, yesterday)
    if not res:
        print("  ❌ supplyhub 수집 실패(Akamai 403 등) — 오늘 스킵")
        # 알림 중복 방지(2026-07-08): keepalive가 만료 시 이미 두리로 1회 알림 + 마커 생성.
        # 마커 있으면 = 이미 대표님께 통보된 상태 → rocket_daily는 조용히 스킵(매일 도배 방지).
        # 대표님 재로그인(relogin.py) 시 마커 삭제 → 다음 만료 때 다시 1회 알림.
        import os as _os
        marker = _os.path.join(_os.path.dirname(__file__), ".supplyhub_expired")
        if not _os.path.exists(marker):
            alert("로켓 매출", "로켓배송 매출을 가져오려는데 쿠팡이 막아서 오늘은 못 가져왔어요 😢 서플라이허브 세션이 풀린 것 같아요. supplyhub_relogin.py로 재로그인만 해주시면 하치가 바로 채워드릴게요!", "critical")
        else:
            print("  (만료 마커 존재 — 이미 통보됨, 중복 알림 생략)")
        sys.exit(1)
    items = res.get('items', [])
    if not items:
        print("  (입고 데이터 없음)"); return
    daily = items_to_daily(items)
    n = upsert(daily)
    tot = sum(round(v['supply'])+round(v['tax']) for v in daily.values())
    print(f"  ✅ 로켓 1P {n}일 → ERP sales 반영. 총 {tot:,}원")

if __name__ == "__main__":
    main()
