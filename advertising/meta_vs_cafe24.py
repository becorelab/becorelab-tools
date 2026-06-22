#!/usr/bin/env python3
"""메타 광고비 vs 카페24 실매출 → 실질 ROAS (광고 하치 전용)

메타 픽셀이 놓치는 자사몰 전환을 카페24 실매출(erp.db, 이지어드민 자동수집)로 보정.
카페24 유입은 메타가 거의 전부라는 전제(대표님) — 카페24 전체매출 vs 메타 전체광고비.

사용:
  python3 meta_vs_cafe24.py              # 최근 7일 (어제까지)
  python3 meta_vs_cafe24.py --days 14
  python3 meta_vs_cafe24.py --include-today

옵션:
  --days N          (기본 7)
  --account ilbia   (기본) | washing
  --include-today   오늘도 포함 (기본은 어제까지 — 오늘은 미완성치라 제외)

주의: 카페24는 이지어드민 09:30/10:00 수집이라 당일·어제치가 늦게 채워질 수 있음.
      '누락⚠️' 표시된 날은 실질ROAS 합산에서 자동 제외됨.
"""
import argparse, datetime, json, sqlite3, sys
import requests

ACCOUNTS = {'ilbia': 'act_939432264476274', 'washing': 'act_1374146073384332'}
ENV_PATHS = ['/Users/macmini_ky/ClaudeAITeam/automation/.env',
             '/Users/macmini_ky/ClaudeAITeam/mcp-server/.env']
ERP_DB = '/Users/macmini_ky/ClaudeAITeam/erp/erp.db'
CAFE24_CHANNEL = '비코어랩 카페24 일비아'
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


def meta_daily(tok, acct, since, until):
    p = {'access_token': tok, 'level': 'account', 'time_increment': 1,
         'time_range': json.dumps({'since': str(since), 'until': str(until)}),
         'fields': 'spend,action_values', 'limit': 200}
    d = requests.get(f'{GRAPH}/{acct}/insights', params=p).json()
    if 'error' in d:
        print('❌ 메타 API:', d['error'].get('message'))
        sys.exit(1)
    out = {}
    for c in d.get('data', []):
        dt = c.get('date_start')
        val = 0
        for a in c.get('action_values', []):
            if a['action_type'] in ('purchase', 'omni_purchase'):
                val = max(val, float(a['value']))
        out[dt] = {'spend': float(c.get('spend', 0)), 'pixel': val}
    return out


def cafe24_daily(since, until):
    con = sqlite3.connect(ERP_DB)
    cur = con.cursor()
    cur.execute(
        "SELECT sale_date, SUM(total_amount) FROM sales "
        "WHERE channel=? AND sale_date BETWEEN ? AND ? GROUP BY sale_date",
        (CAFE24_CHANNEL, str(since), str(until)))
    out = {r[0]: float(r[1] or 0) for r in cur.fetchall()}
    con.close()
    return out


def main():
    ap = argparse.ArgumentParser(description='메타 광고비 vs 카페24 실매출 실질ROAS')
    ap.add_argument('--days', type=int, default=7)
    ap.add_argument('--account', default='ilbia', choices=list(ACCOUNTS))
    ap.add_argument('--include-today', action='store_true')
    a = ap.parse_args()

    tok = load_token()
    acct = ACCOUNTS[a.account]
    today = datetime.date.today()
    until = today if a.include_today else today - datetime.timedelta(days=1)
    since = until - datetime.timedelta(days=a.days - 1)

    meta = meta_daily(tok, acct, since, until)
    cafe = cafe24_daily(since, until)

    print(f'=== 메타 vs 카페24 실질ROAS | {a.account} | {since}~{until} ===')
    print('일자     메타광고비   픽셀매출  카페24실매출  픽셀ROAS 실질ROAS')
    ts = tp = tc = tc_spend = 0
    for dt in sorted(set(list(meta) + list(cafe))):
        m = meta.get(dt, {'spend': 0, 'pixel': 0})
        sp, px = m['spend'], m['pixel']
        c = cafe.get(dt)
        ts += sp; tp += px
        pr = f'{px / sp:>6.2f}' if sp else '     -'
        if c is None:
            cstr, rr = '    누락⚠️', '     -'
        else:
            cstr = f'{int(c):>10,}'
            rr = f'{c / sp:>6.2f}' if sp else '     -'
            tc += c; tc_spend += sp
        print(f'{dt[5:]}   {int(sp):>9,} {int(px):>9,} {cstr}  {pr} {rr}')
    print('---')
    if ts:
        print(f'합계 전체        : 광고비 {int(ts):,} / 픽셀매출 {int(tp):,}  → 픽셀ROAS {tp / ts:.2f}')
    if tc_spend:
        print(f'합계 카페24有날  : 광고비 {int(tc_spend):,} / 카페24실매출 {int(tc):,}  → 실질ROAS {tc / tc_spend:.2f}')
    print('※ 카페24=이지어드민 자동수집(09:30/10:00). 당일·어제치 지연 가능, 누락일은 실질ROAS 합산 제외')


if __name__ == '__main__':
    main()
