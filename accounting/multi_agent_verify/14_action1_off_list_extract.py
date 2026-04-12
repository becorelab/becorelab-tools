"""
액션 1 (즉시 출혈 차단) — OFF 대상 캠페인/소재 정확 추출
- 입력: 08_meta_ad_data.json (옵시디언 14개월 추출)
- 출력: OFF 권장 리스트 + 마케터 전달용 액션 카드
"""
import json, sys, io
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = 'C:/Users/info/ClaudeAITeam/accounting/multi_agent_verify'

with open(f'{BASE}/08_meta_ad_data.json', 'r', encoding='utf-8') as f:
    meta = json.load(f)

print('=' * 80)
print('🚨 액션 1 OFF 리스트 — 옵시디언 14개월 데이터 기반')
print('=' * 80)

# 1. Top campaigns ilbia 보기
print('\n## 1. 일비아 캠페인 14개월 누적 (지출 큰 순)')
print('-' * 80)
top = meta.get('top_campaigns', {}).get('ilbia', [])
print(f"{'#':<3}{'캠페인명':<45}{'지출':>13}{'ROAS':>8}{'전환':>7}{'활성일':>7}")
print('-' * 80)
for i, c in enumerate(top[:20], 1):
    name = c.get('name', '')[:43]
    spend = c.get('total_spend', 0)
    roas = c.get('avg_roas', 0)
    conv = c.get('total_conversions', 0)
    days = c.get('active_days', 0)
    print(f"{i:<3}{name:<45}{spend:>13,.0f}{roas:>8.2f}{conv:>7.0f}{days:>7}")

# 2. 좀비/적자 캠페인 식별 (지출 100K 이상 + ROAS 1.5 미만)
print('\n## 2. 🔴 OFF 권장 캠페인 (지출 100K+ & ROAS 1.5 미만)')
print('-' * 80)
zombie = []
for c in top:
    spend = c.get('total_spend', 0)
    roas = c.get('avg_roas', 0)
    if spend >= 100000 and roas < 1.5:
        zombie.append(c)

print(f"{'#':<3}{'캠페인명':<45}{'지출':>13}{'ROAS':>8}{'전환':>7}{'활성일':>7}")
print('-' * 80)
for i, c in enumerate(zombie, 1):
    name = c.get('name', '')[:43]
    print(f"{i:<3}{name:<45}{c['total_spend']:>13,.0f}{c['avg_roas']:>8.2f}{c['total_conversions']:>7.0f}{c['active_days']:>7}")

total_zombie_spend = sum(c['total_spend'] for c in zombie)
print('-' * 80)
print(f"OFF 권장 누적 지출: {total_zombie_spend:,.0f}원")

# 3. 카테고리별 ROAS 최저/최고
print('\n## 3. 소재 카테고리별 효율 (14개월 누적)')
print('-' * 80)
cats = meta.get('creative_categories', {})
sorted_cats = sorted(cats.items(), key=lambda x: x[1].get('avg_roas', 0))
print(f"{'카테고리':<20}{'지출':>13}{'비중':>8}{'ROAS':>8}{'전환':>8}")
print('-' * 80)
for name, info in sorted_cats:
    print(f"{name:<20}{info.get('spend', 0):>13,.0f}{info.get('share', 0)*100:>7.1f}%{info.get('avg_roas', 0):>8.2f}{info.get('conversions', 0):>8.0f}")

# 4. 최근 30일 일별 (가장 최근 데이터 확인)
print('\n## 4. 최근 30일 일비아 캠페인 활성 상태 체크')
print('-' * 80)
daily = meta.get('daily', [])
if daily:
    recent = daily[-30:]
    print(f"기간: {recent[0]['date']} ~ {recent[-1]['date']}")

    # 최근 30일에 활성이었던 캠페인 모음
    recent_camps = {}
    for day in recent:
        for c in day.get('campaigns_ilbia', []):
            n = c.get('name', '')
            if n not in recent_camps:
                recent_camps[n] = {'spend': 0, 'conv': 0, 'days': 0, 'last_seen': '', 'roas_sum': 0}
            recent_camps[n]['spend'] += c.get('spend', 0)
            recent_camps[n]['conv'] += c.get('conversions', 0)
            recent_camps[n]['days'] += 1
            recent_camps[n]['last_seen'] = day['date']
            recent_camps[n]['roas_sum'] += c.get('roas', 0)

    print(f"\n최근 30일 활성 캠페인 수: {len(recent_camps)}")
    print(f"\n{'캠페인명':<45}{'지출':>13}{'ROAS평균':>10}{'전환':>7}{'활성':>6}")
    print('-' * 80)
    sorted_recent = sorted(recent_camps.items(), key=lambda x: -x[1]['spend'])
    for n, d in sorted_recent[:15]:
        avg_r = d['roas_sum'] / d['days'] if d['days'] > 0 else 0
        name = n[:43]
        print(f"{name:<45}{d['spend']:>13,.0f}{avg_r:>10.2f}{d['conv']:>7.0f}{d['days']:>6}")

# 5. JSON 출력 (액션 카드용)
output = {
    'generated_at': datetime.now().isoformat(),
    'source': 'opsidian 14-month meta ad data',
    'off_recommended': [
        {
            'name': c['name'],
            'total_spend': c['total_spend'],
            'avg_roas': c['avg_roas'],
            'total_conversions': c['total_conversions'],
            'active_days': c['active_days'],
            'reason': 'ROAS < 1.5 with spend >= 100K',
        }
        for c in zombie
    ],
    'category_efficiency': sorted_cats,
    'total_off_spend': total_zombie_spend,
}

with open(f'{BASE}/14_action1_off_list.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)

print(f'\n✓ JSON 저장: {BASE}/14_action1_off_list.json')
