#!/usr/bin/env python3
"""
쿠팡 광고 구글시트 업데이트 스크립트
5/10 ~ 5/11 데이터 추가
"""
import json
import warnings
warnings.filterwarnings('ignore')

import gspread
from google.oauth2.service_account import Credentials
from collections import defaultdict

# ============================================================
# 설정
# ============================================================
SHEET_ID = '1bmN5H7lB-kIr9Oo5vqUokXanTM0O7xeCMgHoP24WAJg'
SERVICE_ACCOUNT = '/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json'
DATA_DIR = '/Users/macmini_ky/ClaudeAITeam/marketing/coupang_data'

# 파일 경로
FILES = {
    'becorelab_510': f'{DATA_DIR}/A00290275_pa_daily_keyword_20260510_20260510.json',
    'becorelab_511': f'{DATA_DIR}/A00290275_pa_daily_keyword_20260511_20260511.json',
    'becorelab_507_510': f'{DATA_DIR}/A00290275_pa_daily_keyword_20260507_20260510.json',
    'chaeum_510': f'{DATA_DIR}/A00940134_pa_daily_keyword_20260510_20260510.json',
    'chaeum_511': f'{DATA_DIR}/A00940134_pa_daily_keyword_20260511_20260511.json',
}

# ============================================================
# 헬퍼 함수
# ============================================================
def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def fmt_won(v):
    """₩1,234 형식"""
    return f'₩{int(round(v)):,}'

def fmt_pct(v, decimals=1):
    """123.4% 형식"""
    return f'{round(v, decimals)}%'

def fmt_pct2(v):
    """소수점 2자리 %"""
    return f'{round(v, 2)}%'

def safe_div(a, b):
    return a / b if b else 0

def date_str(raw):
    """20260510.0 → 2026-05-10"""
    s = str(int(raw))
    return f'{s[:4]}-{s[4:6]}-{s[6:]}'

def aggregate_by_date(data):
    """날짜별 합산"""
    agg = defaultdict(lambda: {
        'ad_cost': 0, 'revenue': 0, 'orders': 0,
        'impressions': 0, 'clicks': 0
    })
    for row in data:
        d = date_str(row['날짜'])
        agg[d]['ad_cost']      += row.get('광고비', 0) or 0
        agg[d]['revenue']      += row.get('총 전환매출액(1일)', 0) or 0
        agg[d]['orders']       += row.get('총 주문수(1일)', 0) or 0
        agg[d]['impressions']  += row.get('노출수', 0) or 0
        agg[d]['clicks']       += row.get('클릭수', 0) or 0
    return dict(sorted(agg.items()))

def aggregate_by_date_campaign(data):
    """날짜+캠페인별 합산"""
    agg = defaultdict(lambda: {
        'ad_cost': 0, 'revenue': 0, 'orders': 0,
        'impressions': 0, 'clicks': 0
    })
    for row in data:
        d = date_str(row['날짜'])
        campaign = row.get('캠페인') or row.get('캠페인명') or ''
        key = (d, campaign)
        agg[key]['ad_cost']      += row.get('광고비', 0) or 0
        agg[key]['revenue']      += row.get('총 전환매출액(1일)', 0) or 0
        agg[key]['orders']       += row.get('총 주문수(1일)', 0) or 0
        agg[key]['impressions']  += row.get('노출수', 0) or 0
        agg[key]['clicks']       += row.get('클릭수', 0) or 0
    return dict(sorted(agg.items()))

def aggregate_by_date_zone(data):
    """날짜+노출지면별 합산"""
    zone_map = {
        '검색 영역': 'search',
        '비검색 영역': 'nonsearch',
    }
    agg = defaultdict(lambda: {
        'search':    {'ad_cost': 0, 'revenue': 0, 'orders': 0, 'clicks': 0},
        'nonsearch': {'ad_cost': 0, 'revenue': 0, 'orders': 0, 'clicks': 0},
    })
    for row in data:
        d = date_str(row['날짜'])
        zone_raw = row.get('광고 노출 지면') or row.get('노출 영역') or ''
        zone = zone_map.get(zone_raw)
        if not zone:
            continue
        agg[d][zone]['ad_cost']  += row.get('광고비', 0) or 0
        agg[d][zone]['revenue']  += row.get('총 전환매출액(1일)', 0) or 0
        agg[d][zone]['orders']   += row.get('총 주문수(1일)', 0) or 0
        agg[d][zone]['clicks']   += row.get('클릭수', 0) or 0
    return dict(sorted(agg.items()))

def aggregate_by_date_campaign_zone(data):
    """날짜+캠페인+노출지면별 합산 (_비코어랩_검색비검색_data용)"""
    zone_map = {'검색 영역': 'search', '비검색 영역': 'nonsearch'}
    agg = defaultdict(lambda: {
        'search':    {'ad_cost': 0, 'revenue': 0, 'orders': 0, 'clicks': 0},
        'nonsearch': {'ad_cost': 0, 'revenue': 0, 'orders': 0, 'clicks': 0},
    })
    for row in data:
        d = date_str(row['날짜'])
        campaign = row.get('캠페인') or row.get('캠페인명') or ''
        zone_raw = row.get('광고 노출 지면') or row.get('노출 영역') or ''
        zone = zone_map.get(zone_raw)
        if not zone:
            continue
        key = (d, campaign)
        agg[key][zone]['ad_cost']  += row.get('광고비', 0) or 0
        agg[key][zone]['revenue']  += row.get('총 전환매출액(1일)', 0) or 0
        agg[key][zone]['orders']   += row.get('총 주문수(1일)', 0) or 0
        agg[key][zone]['clicks']   += row.get('클릭수', 0) or 0
    return dict(sorted(agg.items()))

def make_summary_row(d, agg):
    """요약 시트 행 생성 (날짜, 광고비, 매출, ROAS, 주문, 노출, 클릭, CTR, CPC, 전환율, 메모)"""
    ad  = agg['ad_cost']
    rev = agg['revenue']
    ord = agg['orders']
    imp = agg['impressions']
    clk = agg['clicks']
    roas  = safe_div(rev, ad) * 100
    ctr   = safe_div(clk, imp) * 100
    cpc   = safe_div(ad, clk)
    cvr   = safe_div(ord, clk) * 100
    return [
        d,
        fmt_won(ad),
        fmt_won(rev),
        fmt_pct(roas, 1),
        str(int(ord)),
        f'{int(imp):,}',
        str(int(clk)),
        fmt_pct(ctr, 2),
        fmt_won(cpc),
        fmt_pct(cvr, 1),
        ''
    ]

def make_campaign_row(d, campaign, agg):
    """캠페인별 시트 행 생성"""
    ad  = agg['ad_cost']
    rev = agg['revenue']
    ord = agg['orders']
    imp = agg['impressions']
    clk = agg['clicks']
    roas = safe_div(rev, ad) * 100
    ctr  = safe_div(clk, imp) * 100
    cpc  = safe_div(ad, clk)
    cvr  = safe_div(ord, clk) * 100
    return [
        d,
        campaign,
        fmt_won(ad),
        fmt_won(rev),
        fmt_pct(roas, 1),
        str(int(ord)),
        f'{int(imp):,}',
        str(int(clk)),
        fmt_pct(ctr, 2),
        fmt_won(cpc),
        fmt_pct(cvr, 1),
        ''
    ]

# ============================================================
# 메인
# ============================================================
def main():
    # 인증
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(SHEET_ID)

    # 데이터 로드
    print('JSON 데이터 로드 중...')
    becorelab_510 = load_json(FILES['becorelab_510'])
    becorelab_511 = load_json(FILES['becorelab_511'])
    becorelab_507_510 = load_json(FILES['becorelab_507_510'])
    chaeum_510 = load_json(FILES['chaeum_510'])
    chaeum_511 = load_json(FILES['chaeum_511'])

    # 비코어랩 데이터 합치기 (5/10, 5/11)
    becorelab_new = becorelab_510 + becorelab_511
    # 채움컴퍼니 데이터 합치기
    chaeum_new = chaeum_510 + chaeum_511

    results = {}

    # =========================================================
    # 1. 📊 비코어랩 요약 (gid=1655464820) — 마지막 5/09 → 5/10, 5/11 추가
    # =========================================================
    print('\n[1] 📊 비코어랩 요약 업데이트...')
    ws = ss.get_worksheet_by_id(1655464820)
    agg = aggregate_by_date(becorelab_new)
    rows_to_add = []
    for d, v in agg.items():
        if d >= '2026-05-10':
            rows_to_add.append(make_summary_row(d, v))
    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option='USER_ENTERED')
        print(f'  → {len(rows_to_add)}행 추가 (날짜: {[r[0] for r in rows_to_add]})')
    results['비코어랩 요약'] = {'added': len(rows_to_add), 'last': rows_to_add[-1][0] if rows_to_add else 'N/A'}

    # =========================================================
    # 2. 📊 비코어랩 검색/비검색 (gid=923097320) — 마지막 5/06 → 5/07~5/11 추가
    # 이 시트는 숫자만 (₩ 없음, % 없음, 소수 ROAS)
    # =========================================================
    print('\n[2] 📊 비코어랩 검색/비검색 업데이트...')
    ws = ss.get_worksheet_by_id(923097320)
    # 5/07~5/10은 becorelab_507_510에서, 5/11은 becorelab_511에서
    becorelab_507_511 = becorelab_507_510 + becorelab_511
    agg_zone = aggregate_by_date_zone(becorelab_507_511)
    rows_to_add = []
    for d, zones in agg_zone.items():
        if d < '2026-05-07':
            continue
        s = zones['search']
        n = zones['nonsearch']
        s_roas = safe_div(s['revenue'], s['ad_cost'])
        n_roas = safe_div(n['revenue'], n['ad_cost'])
        s_cpc  = int(safe_div(s['ad_cost'], s['clicks']))
        n_cpc  = int(safe_div(n['ad_cost'], n['clicks']))
        total_ad  = s['ad_cost'] + n['ad_cost']
        total_rev = s['revenue'] + n['revenue']
        total_roas = safe_div(total_rev, total_ad)
        row = [
            d,
            str(int(s['ad_cost'])),
            str(int(s['revenue'])),
            str(round(s_roas, 4)),
            str(int(s['orders'])),
            str(int(s['clicks'])),
            str(s_cpc),
            str(int(n['ad_cost'])),
            str(int(n['revenue'])),
            str(round(n_roas, 4)),
            str(int(n['orders'])),
            str(int(n['clicks'])),
            str(n_cpc),
            str(int(total_ad)),
            str(int(total_rev)),
            str(round(total_roas, 4)),
        ]
        rows_to_add.append(row)
    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option='USER_ENTERED')
        print(f'  → {len(rows_to_add)}행 추가 (날짜: {[r[0] for r in rows_to_add]})')
    results['비코어랩 검색/비검색'] = {'added': len(rows_to_add), 'last': rows_to_add[-1][0] if rows_to_add else 'N/A'}

    # =========================================================
    # 3. 📊 채움컴퍼니 요약 (gid=1435070093) — 마지막 5/09 → 5/10, 5/11 추가
    # =========================================================
    print('\n[3] 📊 채움컴퍼니 요약 업데이트...')
    ws = ss.get_worksheet_by_id(1435070093)
    agg = aggregate_by_date(chaeum_new)
    rows_to_add = []
    for d, v in agg.items():
        if d >= '2026-05-10':
            rows_to_add.append(make_summary_row(d, v))
    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option='USER_ENTERED')
        print(f'  → {len(rows_to_add)}행 추가 (날짜: {[r[0] for r in rows_to_add]})')
    results['채움컴퍼니 요약'] = {'added': len(rows_to_add), 'last': rows_to_add[-1][0] if rows_to_add else 'N/A'}

    # =========================================================
    # 4. 📊 채움컴퍼니 캠페인별 (gid=1568908840) — 마지막 5/09 → 5/10, 5/11 추가
    # =========================================================
    print('\n[4] 📊 채움컴퍼니 캠페인별 업데이트...')
    ws = ss.get_worksheet_by_id(1568908840)
    agg_camp = aggregate_by_date_campaign(chaeum_new)
    rows_to_add = []
    date_camp_map = defaultdict(dict)
    for (d, camp), v in agg_camp.items():
        if d >= '2026-05-10':
            date_camp_map[d][camp] = v
    for d in sorted(date_camp_map.keys()):
        for camp, v in sorted(date_camp_map[d].items()):
            rows_to_add.append(make_campaign_row(d, camp, v))
    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option='USER_ENTERED')
        print(f'  → {len(rows_to_add)}행 추가 (날짜: {sorted(set(r[0] for r in rows_to_add))})')
    results['채움컴퍼니 캠페인별'] = {'added': len(rows_to_add), 'last': rows_to_add[-1][0] if rows_to_add else 'N/A'}

    # =========================================================
    # 5. 📊 채움컴퍼니 검색/비검색 (gid=1600279019) — 마지막 5/09 → 5/10, 5/11 추가
    # 형식: ₩ 있음, % 있음 (소수점 0)
    # =========================================================
    print('\n[5] 📊 채움컴퍼니 검색/비검색 업데이트...')
    ws = ss.get_worksheet_by_id(1600279019)
    agg_zone = aggregate_by_date_zone(chaeum_new)
    rows_to_add = []
    for d, zones in agg_zone.items():
        if d < '2026-05-10':
            continue
        s = zones['search']
        n = zones['nonsearch']
        s_roas = safe_div(s['revenue'], s['ad_cost']) * 100
        n_roas = safe_div(n['revenue'], n['ad_cost']) * 100
        s_cpc  = safe_div(s['ad_cost'], s['clicks'])
        n_cpc  = safe_div(n['ad_cost'], n['clicks'])
        total_ad  = s['ad_cost'] + n['ad_cost']
        total_rev = s['revenue'] + n['revenue']
        total_roas = safe_div(total_rev, total_ad) * 100
        row = [
            d,
            fmt_won(s['ad_cost']),
            fmt_won(s['revenue']),
            fmt_pct(s_roas, 1),
            str(int(s['orders'])),
            str(int(s['clicks'])),
            fmt_won(s_cpc),
            fmt_won(n['ad_cost']),
            fmt_won(n['revenue']),
            fmt_pct(n_roas, 1),
            str(int(n['orders'])),
            str(int(n['clicks'])),
            fmt_won(n_cpc),
            fmt_won(total_ad),
            fmt_won(total_rev),
            fmt_pct(total_roas, 1),
        ]
        rows_to_add.append(row)
    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option='USER_ENTERED')
        print(f'  → {len(rows_to_add)}행 추가 (날짜: {[r[0] for r in rows_to_add]})')
    results['채움컴퍼니 검색/비검색'] = {'added': len(rows_to_add), 'last': rows_to_add[-1][0] if rows_to_add else 'N/A'}

    # =========================================================
    # 6. _비코어랩_검색비검색_data (gid=678110573) — 마지막 5/09 → 5/10, 5/11 추가
    # 헤더: 날짜, 캠페인, 검색_광고비, 검색_매출, 검색_ROAS, 검색_주문, 검색_클릭, 검색_CPC,
    #        비검색_광고비, 비검색_매출, 비검색_ROAS, 비검색_주문, 비검색_클릭, 비검색_CPC,
    #        합계_광고비, 합계_매출, 합계_ROAS
    # 마지막 2행이 개별캠페인 + 전체(합계)
    # =========================================================
    print('\n[6] _비코어랩_검색비검색_data 업데이트...')
    ws = ss.get_worksheet_by_id(678110573)
    agg_camp_zone = aggregate_by_date_campaign_zone(becorelab_new)

    # 날짜별로 캠페인 그룹핑
    date_data = defaultdict(dict)
    for (d, camp), zones in agg_camp_zone.items():
        if d >= '2026-05-10':
            date_data[d][camp] = zones

    rows_to_add = []
    for d in sorted(date_data.keys()):
        camps = date_data[d]
        # 전체 합계
        total = {
            'search':    {'ad_cost': 0, 'revenue': 0, 'orders': 0, 'clicks': 0},
            'nonsearch': {'ad_cost': 0, 'revenue': 0, 'orders': 0, 'clicks': 0},
        }
        for camp, zones in sorted(camps.items()):
            s = zones['search']
            n = zones['nonsearch']
            # 개별 캠페인 행
            s_roas = safe_div(s['revenue'], s['ad_cost']) * 100
            n_roas = safe_div(n['revenue'], n['ad_cost']) * 100
            s_cpc  = safe_div(s['ad_cost'], s['clicks'])
            n_cpc  = safe_div(n['ad_cost'], n['clicks'])
            total_ad  = s['ad_cost'] + n['ad_cost']
            total_rev = s['revenue'] + n['revenue']
            total_roas = safe_div(total_rev, total_ad) * 100
            # 합계 빈 칸 처리 (캠페인 개별: 합계 3열 비워도 되지만 기존 패턴 보면 있음)
            row = [
                d, camp,
                fmt_won(s['ad_cost']), fmt_won(s['revenue']), fmt_pct(s_roas, 1),
                str(int(s['orders'])), str(int(s['clicks'])), fmt_won(s_cpc),
                fmt_won(n['ad_cost']), fmt_won(n['revenue']), fmt_pct(n_roas, 1),
                str(int(n['orders'])), str(int(n['clicks'])), fmt_won(n_cpc),
                fmt_won(total_ad), fmt_won(total_rev), fmt_pct(total_roas, 1),
            ]
            # 개별 캠페인에서 합계 열이 비어있으면 비워두기
            if total_ad == 0:
                row[14] = ''
                row[15] = ''
                row[16] = ''
            rows_to_add.append(row)
            # 누적
            for zone in ['search', 'nonsearch']:
                for k in ['ad_cost', 'revenue', 'orders', 'clicks']:
                    total[zone][k] += zones[zone][k]

        # 전체(합계) 행
        s = total['search']
        n = total['nonsearch']
        s_roas = safe_div(s['revenue'], s['ad_cost']) * 100
        n_roas = safe_div(n['revenue'], n['ad_cost']) * 100
        s_cpc  = safe_div(s['ad_cost'], s['clicks'])
        n_cpc  = safe_div(n['ad_cost'], n['clicks'])
        total_ad  = s['ad_cost'] + n['ad_cost']
        total_rev = s['revenue'] + n['revenue']
        total_roas = safe_div(total_rev, total_ad) * 100
        rows_to_add.append([
            d, '전체(합계)',
            fmt_won(s['ad_cost']), fmt_won(s['revenue']), fmt_pct(s_roas, 1),
            str(int(s['orders'])), str(int(s['clicks'])), fmt_won(s_cpc),
            fmt_won(n['ad_cost']), fmt_won(n['revenue']), fmt_pct(n_roas, 1),
            str(int(n['orders'])), str(int(n['clicks'])), fmt_won(n_cpc),
            fmt_won(total_ad), fmt_won(total_rev), fmt_pct(total_roas, 1),
        ])

    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option='USER_ENTERED')
        print(f'  → {len(rows_to_add)}행 추가 (날짜: {sorted(set(r[0] for r in rows_to_add))})')
    results['_비코어랩_검색비검색_data'] = {'added': len(rows_to_add), 'last': rows_to_add[-1][0] if rows_to_add else 'N/A'}

    # =========================================================
    # 7. 📊 채움 요약 (gid=1855258001) — 마지막 5/09 → 5/10, 5/11 추가
    # 비코어랩 요약과 동일 형식, 채움컴퍼니 데이터
    # 단, ROAS/전환율 소수점 2자리 (기존 형식 확인: 264.84%, 208.66% 등)
    # =========================================================
    print('\n[7] 📊 채움 요약 업데이트...')
    ws = ss.get_worksheet_by_id(1855258001)
    # 채움 요약은 전환율 소수점 2자리
    agg = aggregate_by_date(chaeum_new)
    rows_to_add = []
    for d, v in agg.items():
        if d < '2026-05-10':
            continue
        ad  = v['ad_cost']
        rev = v['revenue']
        ord = v['orders']
        imp = v['impressions']
        clk = v['clicks']
        roas  = safe_div(rev, ad) * 100
        ctr   = safe_div(clk, imp) * 100
        cpc   = safe_div(ad, clk)
        cvr   = safe_div(ord, clk) * 100
        row = [
            d,
            fmt_won(ad),
            fmt_won(rev),
            fmt_pct2(roas),
            str(int(ord)),
            f'{int(imp):,}',
            str(int(clk)),
            fmt_pct2(ctr),
            fmt_won(cpc),
            fmt_pct2(cvr),
            ''
        ]
        rows_to_add.append(row)
    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option='USER_ENTERED')
        print(f'  → {len(rows_to_add)}행 추가 (날짜: {[r[0] for r in rows_to_add]})')
    results['채움 요약'] = {'added': len(rows_to_add), 'last': rows_to_add[-1][0] if rows_to_add else 'N/A'}

    # =========================================================
    # 8. 📊 채움 캠페인별 (gid=181108781) — 마지막 5/09 → 5/10, 5/11 추가
    # 전환율 소수점 2자리
    # =========================================================
    print('\n[8] 📊 채움 캠페인별 업데이트...')
    ws = ss.get_worksheet_by_id(181108781)
    agg_camp = aggregate_by_date_campaign(chaeum_new)
    rows_to_add = []
    date_camp_map = defaultdict(dict)
    for (d, camp), v in agg_camp.items():
        if d >= '2026-05-10':
            date_camp_map[d][camp] = v
    for d in sorted(date_camp_map.keys()):
        for camp, v in sorted(date_camp_map[d].items()):
            ad  = v['ad_cost']
            rev = v['revenue']
            ord = v['orders']
            imp = v['impressions']
            clk = v['clicks']
            roas  = safe_div(rev, ad) * 100
            ctr   = safe_div(clk, imp) * 100
            cpc   = safe_div(ad, clk)
            cvr   = safe_div(ord, clk) * 100
            rows_to_add.append([
                d, camp,
                fmt_won(ad), fmt_won(rev),
                fmt_pct2(roas),
                str(int(ord)),
                f'{int(imp):,}',
                str(int(clk)),
                fmt_pct2(ctr),
                fmt_won(cpc),
                fmt_pct2(cvr),
                ''
            ])
    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option='USER_ENTERED')
        print(f'  → {len(rows_to_add)}행 추가 (날짜: {sorted(set(r[0] for r in rows_to_add))})')
    results['채움 캠페인별'] = {'added': len(rows_to_add), 'last': rows_to_add[-1][0] if rows_to_add else 'N/A'}

    # =========================================================
    # 최종 보고
    # =========================================================
    print('\n' + '='*60)
    print('✅ 업데이트 완료 요약')
    print('='*60)
    for sheet, info in results.items():
        print(f'  {sheet}: {info["added"]}행 추가, 마지막 날짜={info["last"]}')
    print('='*60)

if __name__ == '__main__':
    main()
