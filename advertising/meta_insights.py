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


def main():
    ap = argparse.ArgumentParser(description='메타 광고 인사이트 한 줄 조회')
    ap.add_argument('--account', default='ilbia', choices=list(ACCOUNTS))
    ap.add_argument('--level', default='campaign', choices=['campaign', 'ad', 'age', 'placement'])
    ap.add_argument('--date', default='today')
    ap.add_argument('--daily', action='store_true', help='일별 분해(time_increment=1)')
    ap.add_argument('--campaign', default='', help='캠페인명 부분일치 필터')
    ap.add_argument('--min-spend', type=float, default=50)
    a = ap.parse_args()

    tok = load_token()
    acct = ACCOUNTS[a.account]
    lvl = 'ad' if a.level == 'ad' else 'campaign'
    p = {'access_token': tok, 'level': lvl, 'date_preset': a.date,
         'fields': 'campaign_name,ad_name,spend,purchase_roas,frequency,reach,actions,action_values',
         'limit': 300}
    if a.daily:
        p['time_increment'] = 1
    if a.level == 'age':
        p['breakdowns'] = 'age,gender'
    if a.level == 'placement':
        p['breakdowns'] = 'publisher_platform,platform_position'

    d = requests.get(f'{GRAPH}/{acct}/insights', params=p).json()
    if 'error' in d:
        print('❌', d['error'].get('message'))
        sys.exit(1)
    rows = d.get('data', [])
    if a.campaign:
        rows = [c for c in rows if a.campaign in c.get('campaign_name', '')]

    print(f'=== 메타 {a.account} | {a.level} | {a.date}{" 일별" if a.daily else ""} ===')
    sp = lambda c: float(c.get('spend', 0))
    tot = sum(sp(c) for c in rows)
    for c in sorted(rows, key=lambda c: c.get('date_start', '') if a.daily else -sp(c)):
        s = sp(c)
        if s < a.min_spend:
            continue
        r = c.get('purchase_roas', [{}])
        rv = float(r[0]['value']) if r and 'value' in r[0] else 0
        fq = float(c.get('frequency', 0))
        rc = int(c.get('reach', 0))
        pur, _ = purch(c)
        cpp = int(s / pur) if pur else 0
        if a.daily:
            lab = c.get('date_start', '')
        elif a.level == 'ad':
            lab = c.get('ad_name', '')[:26]
        elif a.level == 'age':
            lab = f"{c.get('age', '')}/{c.get('gender', '')}"
        elif a.level == 'placement':
            lab = f"{c.get('publisher_platform', '')}/{c.get('platform_position', '')}"[:26]
        else:
            lab = c.get('campaign_name', '')[:26]
        share = f'({int(s / tot * 100):>2}%)' if tot else ''
        print(f'{lab:<26} 지출{int(s):>7,}{share} ROAS{rv:>5.2f} 구매{pur:>3} CPP{cpp:>7,} 빈도{fq:.2f} reach{rc:,}')
    print(f'총지출 {int(tot):,}')


if __name__ == '__main__':
    main()
