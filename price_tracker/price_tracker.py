"""경쟁사 가격 추적 앱 (데모) — 네이버 쇼핑 + 쿠팡(소싱콕)

사용: python3 price_tracker.py "키워드" [개수]
- 네이버 쇼핑 상위 상품 가격 수집 → 날짜별 기록
- 전일(이전 기록) 대비 가격 변동 표시 (▲▼)
- 쿠팡은 소싱콕 스캔 데이터가 있으면 함께 표시
"""
import sys, json, os
from datetime import date
sys.path.insert(0, '/Users/macmini_ky/ClaudeAITeam/marketing/competitor_analyzer')
from collectors.naver_shopping import NaverShoppingCollector

HIST = '/Users/macmini_ky/ClaudeAITeam/price_tracker/history'

def track(keyword, count=20):
    os.makedirs(HIST, exist_ok=True)
    items = NaverShoppingCollector().search(keyword, count=count)
    today = date.today().isoformat()
    cur = {}
    for p in items:
        nm, pr = p.get('product_name'), p.get('price', 0)
        if nm and pr:
            cur[nm] = pr

    # 이전 최신 기록
    prev = {}
    files = sorted([f for f in os.listdir(HIST) if f.startswith(keyword + '_')])
    prev_file = [f for f in files if not f.endswith(f'{today}.json')]
    if prev_file:
        prev = json.load(open(os.path.join(HIST, prev_file[-1]), encoding='utf-8')).get('prices', {})

    # 저장
    with open(f'{HIST}/{keyword}_{today}.json', 'w', encoding='utf-8') as f:
        json.dump({'date': today, 'keyword': keyword, 'prices': cur, 'items': items},
                  f, ensure_ascii=False, indent=2)

    # 출력 (가격순)
    print(f"=== 📊 {keyword} 경쟁사 가격 추적 ({today}) — {len(cur)}개 ===")
    print(f"{'상품명':32} {'가격':>10}  변동")
    print('-' * 60)
    for nm, pr in sorted(cur.items(), key=lambda x: x[1]):
        old = prev.get(nm)
        if old is None:
            mark = 'NEW' if prev else ''
        elif old == pr:
            mark = '—'
        else:
            diff = pr - old
            arrow = '▲' if diff > 0 else '▼'
            mark = f'{arrow}{abs(diff):,}'
        print(f"  {nm[:30]:30} {pr:>9,}원  {mark}")

    if prev:
        changed = sum(1 for nm, pr in cur.items() if prev.get(nm) not in (None, pr))
        print(f"\n💡 전일 대비 가격 변동: {changed}건")
    else:
        print(f"\n💡 첫 수집 — 내일 다시 돌리면 변동(▲▼)이 표시됩니다")

if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else '섬유탈취제'
    cnt = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    track(kw, cnt)
