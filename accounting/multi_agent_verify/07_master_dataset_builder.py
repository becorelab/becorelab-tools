"""
4명 페르소나 토론용 마스터 데이터셋 빌더
- 모리(검증된 자체 계산) + 픽시(정산시트 광고비) 통합
- 14개월 월별: 매출 / 원가 / 이익(광고비 전) / 광고비 / 이익(광고비 후) / ROAS / 이익률
"""
import json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = 'C:/Users/info/ClaudeAITeam/accounting/multi_agent_verify'

with open(f'{BASE}/02_mori_result.json', 'r', encoding='utf-8') as f:
    mori = json.load(f)
with open(f'{BASE}/04_pixie_result.json', 'r', encoding='utf-8') as f:
    pixie = json.load(f)

months = sorted(mori['months'].keys())

dataset = {
    'description': '14개월 자사몰 월별 통합 데이터셋 (모리 자체계산 + 픽시 정산시트 광고비)',
    'months': {}
}

total = {
    'gross': 0, 'net_revenue': 0, 'net_revenue_with_ship': 0,
    'cost': 0, 'profit_pre_ad': 0, 'ad_spend': 0, 'profit_post_ad': 0,
    'qty': 0, 'order_count': 0
}

print(f"{'월':<10}{'매출(net+배송)':>15}{'원가':>13}{'이익(광고전)':>14}{'광고비':>13}{'이익(광고후)':>14}{'이익률':>9}{'블렌디드ROAS':>13}")
print('-' * 105)

for m in months:
    mori_m = mori['months'][m]
    pix_m = pixie['months'].get(m, {})

    revenue = mori_m['net_revenue_with_ship']
    cost = mori_m['cost']
    profit_pre = revenue - cost  # 광고비 전 이익 (배송비 포함 매출 기준)

    # 광고비: post_ad 시트 우선, 없으면 0
    ad_spend = 0
    post = pix_m.get('channel_sheet_post_ad', {})
    if post.get('found'):
        ad_spend = post.get('cafe24_ad_cost', 0) or 0

    profit_post = profit_pre - ad_spend
    margin_rate = profit_post / revenue if revenue > 0 else 0
    roas = revenue / ad_spend if ad_spend > 0 else 0

    dataset['months'][m] = {
        'revenue': revenue,
        'cost': cost,
        'profit_pre_ad': profit_pre,
        'ad_spend': ad_spend,
        'profit_post_ad': profit_post,
        'margin_rate_post_ad': margin_rate,
        'blended_roas': roas,
        'qty': mori_m['qty'],
        'order_count': mori_m['order_count'],
    }

    total['gross'] += mori_m['gross']
    total['net_revenue'] += mori_m['net_revenue']
    total['net_revenue_with_ship'] += revenue
    total['cost'] += cost
    total['profit_pre_ad'] += profit_pre
    total['ad_spend'] += ad_spend
    total['profit_post_ad'] += profit_post
    total['qty'] += mori_m['qty']
    total['order_count'] += mori_m['order_count']

    print(f"{m:<10}{revenue:>15,.0f}{cost:>13,.0f}{profit_pre:>14,.0f}{ad_spend:>13,.0f}{profit_post:>14,.0f}{margin_rate*100:>8.1f}%{roas:>12.2f}")

print('-' * 105)
total_margin = total['profit_post_ad'] / total['net_revenue_with_ship'] if total['net_revenue_with_ship'] > 0 else 0
total_roas = total['net_revenue_with_ship'] / total['ad_spend'] if total['ad_spend'] > 0 else 0
print(f"{'합계':<10}{total['net_revenue_with_ship']:>15,.0f}{total['cost']:>13,.0f}{total['profit_pre_ad']:>14,.0f}{total['ad_spend']:>13,.0f}{total['profit_post_ad']:>14,.0f}{total_margin*100:>8.1f}%{total_roas:>12.2f}")

# 광고 데이터 있는 12개월만 별도 합계
ad_months = [m for m in months if dataset['months'][m]['ad_spend'] > 0]
if ad_months:
    print()
    print(f"※ 광고 데이터 있는 {len(ad_months)}개월 ({ad_months[0]}~{ad_months[-1]}):")
    sub = {k: 0 for k in total}
    for m in ad_months:
        d = dataset['months'][m]
        sub['net_revenue_with_ship'] += d['revenue']
        sub['cost'] += d['cost']
        sub['profit_pre_ad'] += d['profit_pre_ad']
        sub['ad_spend'] += d['ad_spend']
        sub['profit_post_ad'] += d['profit_post_ad']
    sub_margin = sub['profit_post_ad'] / sub['net_revenue_with_ship']
    sub_roas = sub['net_revenue_with_ship'] / sub['ad_spend']
    print(f"  매출: {sub['net_revenue_with_ship']:,.0f}")
    print(f"  원가: {sub['cost']:,.0f}")
    print(f"  이익(광고비 전): {sub['profit_pre_ad']:,.0f}")
    print(f"  광고비: {sub['ad_spend']:,.0f} (매출 대비 {sub['ad_spend']/sub['net_revenue_with_ship']*100:.1f}%)")
    print(f"  이익(광고비 후): {sub['profit_post_ad']:,.0f}")
    print(f"  이익률: {sub_margin*100:.1f}%")
    print(f"  블렌디드 ROAS: {sub_roas:.2f}")

dataset['totals'] = total
dataset['totals']['margin_rate_post_ad'] = total_margin
dataset['totals']['blended_roas'] = total_roas

with open(f'{BASE}/07_master_dataset.json', 'w', encoding='utf-8') as f:
    json.dump(dataset, f, ensure_ascii=False, indent=2)

print(f'\n✓ 저장: {BASE}/07_master_dataset.json')
