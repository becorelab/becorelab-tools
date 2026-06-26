#!/usr/bin/env python3
"""메타 광고 인사이트 조회 (광고 하치 전용)

토큰 자동 로드 + 레벨별(캠페인/소재/오디언스/지면/일별) 한 줄 조회.
매번 토큰 읽고 requests 코드 새로 짜던 걸 도구화.

사용 예:
  python3 meta_insights.py                       # 오늘 캠페인별
  python3 meta_insights.py --level ad            # 오늘 소재별
  python3 meta_insights.py --level age           # 오늘 연령/성별
  python3 meta_insights.py --level placement     # 노출 지면별
  python3 meta_insights.py --date last_7d --daily   # 최근 7일 일별 추이
  python3 meta_insights.py --campaign 식세기      # 특정 캠페인만

옵션:
  --account ilbia(기본)|washing
  --date    today(기본)|yesterday|last_7d|last_14d|last_30d
  --level   campaign(기본)|ad|age|placement
  --daily   일별 분해(time_increment=1)
  --campaign <부분일치 필터>
"""
import argparse, sys
import requests

ACCOUNTS = {'ilbia': 'act_939432264476274', 'washing': 'act_1374146073384332'}
ENV_PATHS = ['/Users/macmini_ky/ClaudeAITeam/automation/.env',
             '/Users/macmini_ky/ClaudeAITeam/mcp-server/.env']
GRAPH = 'https://graph.facebook.com/v21.0'


def load_token():
    for f in ENV_PATHS:
        try:
            for line in open(f):
                if line.startswith('META_ACCESS_TOKEN'):
                    t = line.split('=', 1)[1].strip().strip('"').strip("'")
                    if t:
                        return t
        except FileNotFoundError:
            pass
    print('❌ META_ACCESS_TOKEN 못 찾음 (automation/.env 확인)')
    sys.exit(2)


def purch(c):
    pur = val = 0
    for a in c.get('actions', []):
        if a['action_type'] in ('purchase', 'omni_purchase'):
            pur = max(pur, int(float(a['value'])))
    for a in c.get('action_values', []):
        if a['action_type'] in ('purchase', 'omni_purchase'):
            val = max(val, float(a['value']))
    return pur, val


def funnel(c):
    """퍼널 단계 추출: 클릭→ATC→IC→구매 (자사몰 전환 캠페인용)"""
    acts = {}
    for x in c.get('actions', []):
        acts[x['action_type']] = max(acts.get(x['action_type'], 0), int(float(x['value'])))
    clk = int(float(c.get('inline_link_clicks') or c.get('clicks') or acts.get('link_click', 0)))
    atc = acts.get('add_to_cart') or acts.get('omni_add_to_cart', 0)
    ic = acts.get('initiate_checkout') or acts.get('omni_initiated_checkout', 0)
    pur = acts.get('purchase') or acts.get('omni_purchase', 0)
    return clk, atc, ic, pur


def main():
    ap = argparse.ArgumentParser(description='메타 광고 인사이트 한 줄 조회')
    ap.add_argument('--account', default='ilbia', choices=list(ACCOUNTS))
    ap.add_argument('--level', default='campaign', choices=['campaign', 'ad', 'age', 'placement', 'cross'])
    ap.add_argument('--date', default='today')
    ap.add_argument('--daily', action='store_true', help='일별 분해(time_increment=1)')
    ap.add_argument('--funnel', action='store_true', help='퍼널 단계별(클릭→ATC→IC→구매) 누수율')
    ap.add_argument('--campaign', default='', help='캠페인명 부분일치 필터')
    ap.add_argument('--min-spend', type=float, default=50)
    a = ap.parse_args()

    tok = load_token()
    acct = ACCOUNTS[a.account]
    lvl = 'ad' if a.level in ('ad', 'cross') else 'campaign'
    p = {'access_token': tok, 'level': lvl, 'date_preset': a.date,
         'fields': 'campaign_name,ad_name,spend,purchase_roas,frequency,reach,actions,action_values,clicks,inline_link_clicks',
         'limit': 500}
    if a.daily:
        p['time_increment'] = 1
    if a.level == 'age':
        p['breakdowns'] = 'age,gender'
    if a.level == 'placement':
        p['breakdowns'] = 'publisher_platform,platform_position'
    if a.level == 'cross':
        # 소재 × 오디언스 교차 (어떤 소재가 어떤 연령/성별에 효율적인가)
        # ※ 메타 API는 ROAS + 3차원(연령·성별·지면) 동시 breakdown 불가 → 소재×오디언스 2D로 실현
        p['breakdowns'] = 'age,gender'

    d = requests.get(f'{GRAPH}/{acct}/insights', params=p).json()
    if 'error' in d:
        print('❌', d['error'].get('message'))
        sys.exit(1)
    rows = d.get('data', [])
    if a.campaign:
        rows = [c for c in rows if a.campaign in c.get('campaign_name', '')]

    sp = lambda c: float(c.get('spend', 0))
    tot = sum(sp(c) for c in rows)
    roasv = lambda c: float(c.get('purchase_roas', [{}])[0].get('value', 0)) if c.get('purchase_roas') else 0

    def lab_of(c):
        if a.daily: return c.get('date_start', '')
        if a.level == 'ad': return c.get('ad_name', '')[:26]
        if a.level == 'age': return f"{c.get('age', '')}/{c.get('gender', '')}"
        if a.level == 'placement': return f"{c.get('publisher_platform', '')}/{c.get('platform_position', '')}"[:26]
        if a.level == 'cross': return f"_{c.get('ad_name', '').split('_')[-1][:7]}·{c.get('age', '')}/{c.get('gender', '')[:1]}"[:20]
        return c.get('campaign_name', '')[:26]

    # ── 퍼널 모드: 클릭→ATC→IC→구매 누수율 ──
    if a.funnel:
        print(f'=== 메타 {a.account} | 퍼널 | {a.date} ===')
        print(f'{"":<26}{"클릭":>6}{"ATC":>6}{"IC":>6}{"구매":>5}  C→ATC  ATC→IC  IC→구매')
        for c in sorted(rows, key=lambda c: -sp(c)):
            if sp(c) < a.min_spend: continue
            clk, atc, ic, pur = funnel(c)
            c2a = f'{atc/clk*100:.0f}%' if clk else '-'
            a2i = f'{ic/atc*100:.0f}%' if atc else '-'
            i2p = f'{pur/ic*100:.0f}%' if ic else '-'
            print(f'{lab_of(c):<26}{clk:>6}{atc:>6}{ic:>6}{pur:>5}  {c2a:>5}  {a2i:>6}  {i2p:>6}')
        # 합산 누수 진단
        T = lambda i: sum(funnel(c)[i] for c in rows if sp(c) >= a.min_spend)
        clk, atc, ic, pur = T(0), T(1), T(2), T(3)
        print(f'{"합계":<26}{clk:>6}{atc:>6}{ic:>6}{pur:>5}  '
              f'{atc/clk*100 if clk else 0:>4.0f}%  {ic/atc*100 if atc else 0:>5.0f}%  {pur/ic*100 if ic else 0:>5.0f}%')
        diag = []
        if clk and atc/clk < 0.15: diag.append(f'Click→ATC {atc/clk*100:.0f}% 낮음(<15%)→소재/오디언스/가격')
        if ic and pur/ic < 0.5: diag.append(f'IC→구매 {pur/ic*100:.0f}% 낮음(<50%)→자사몰 결제UX/가격비교 이탈')
        if diag: print('⚠️ ' + ' / '.join(diag))
        return

    # ── 일반/교차: 4D는 ROAS 높은 순(고효율 조합 특정), 그 외 지출순 ──
    print(f'=== 메타 {a.account} | {a.level} | {a.date}{" 일별" if a.daily else ""} ===')
    keyf = (lambda c: c.get('date_start', '')) if a.daily else \
           ((lambda c: -roasv(c)) if a.level == 'cross' else (lambda c: -sp(c)))
    for c in sorted(rows, key=keyf):
        s = sp(c)
        if s < a.min_spend:
            continue
        rv = roasv(c)
        fq = float(c.get('frequency', 0))
        rc = int(c.get('reach', 0))
        pur, _ = purch(c)
        cpp = int(s / pur) if pur else 0
        share = f'({int(s / tot * 100):>2}%)' if tot else ''
        print(f'{lab_of(c):<26} 지출{int(s):>7,}{share} ROAS{rv:>5.2f} 구매{pur:>3} CPP{cpp:>7,} 빈도{fq:.2f} reach{rc:,}')
    print(f'총지출 {int(tot):,}')


if __name__ == '__main__':
    main()
