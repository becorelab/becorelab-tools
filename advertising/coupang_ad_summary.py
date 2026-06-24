#!/usr/bin/env python3
"""쿠팡 광고 보고서 분석 v2 — 원본 전수 파싱 (광고 하치 전용)

전송폴더 키워드 보고서 xlsx를 통째로 읽어:
- 품목별 + 검색/비검색 ROAS 분리 + 자동매칭 클릭
- 캠페인 내 SKU별(광고집행 상품명) + 광고집행 vs 전환발생 구분(스마트 교차전환)
- 1일(당일)/14일(소급반영) 선택

⚠️ v1은 14일 누적만 쓰고 검색·비검색·SKU·전환발생을 무시 → "도구 한계"로 단편 분석 유발. v2에서 교정.

사용 예:
  python3 coupang_ad_summary.py --account rocket              # 품목별(1일) + 검색/비검색 + 자동매칭
  python3 coupang_ad_summary.py --account gross --by-campaign  # 캠페인별 + SKU별 + 실제전환(교차전환)
  python3 coupang_ad_summary.py --account rocket --d14         # 14일 누적(소급반영) 기준
  python3 coupang_ad_summary.py --account rocket --by-option 코튼  # 특정 품목 옵션ID별

주의: GMV(판매가) ROAS임 — 정산마진은 더 낮음.
"""
import argparse, glob, os, sys
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

XFER = '/Users/macmini_ky/Library/CloudStorage/GoogleDrive-cky2833@gmail.com/내 드라이브/Claude AI work space/mac window file transfer'
ACCT = {'rocket': 'A00290275', 'gross': 'A00940134'}


def cat(nm):
    s = str(nm)
    if '표백제' in s: return '캡슐표백제'
    if '캡슐세제' in s or '세탁세제' in s: return '캡슐세제'
    if '하트' in s and '식' in s: return '하트식세기'
    if '식기세척' in s: return '식세기(올인원)'
    if '섬유탈취' in s or '스타일' in s: return '섬유탈취제'
    if '건조기시트' in s or '코튼' in s: return '건조기시트 코튼블루'
    if '얼룩' in s: return '얼룩제거제'
    if '바이올렛' in s: return '바이올렛'
    if '베이비' in s: return '베이비크림'
    if '테이프' in s: return '입테이프'
    return '기타'


def col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    return None


def main():
    ap = argparse.ArgumentParser(description='쿠팡 광고 분석 v2 (검색/비검색·SKU·전환발생·1일/14일)')
    ap.add_argument('--account', default='rocket', choices=list(ACCT))
    ap.add_argument('--date', default='', help='YYYYMMDD (기본 최신)')
    ap.add_argument('--by-campaign', action='store_true', help='캠페인별 + SKU별 + 실제전환')
    ap.add_argument('--by-option', default='', help='해당 품목키워드를 옵션ID별로 분해')
    ap.add_argument('--d14', action='store_true', help='14일 누적(소급반영) 기준 (기본 1일)')
    a = ap.parse_args()

    code = ACCT[a.account]
    files = sorted(glob.glob(f'{XFER}/{code}_pa_daily_keyword_*'))
    if not files:
        print(f'❌ 보고서 없음: {code}_pa_daily_keyword_*'); sys.exit(2)
    if a.date:
        files = [f for f in files if a.date in f]
        if not files:
            print(f'❌ {a.date} 보고서 없음'); sys.exit(2)
    fp = files[-1]
    fname = os.path.basename(fp)
    df = pd.read_excel(fp)

    c_prod = col(df, '광고집행 상품명', '상품명')
    c_cprod = col(df, '광고전환매출발생 상품명')
    c_opt = col(df, '광고집행 옵션ID', '옵션ID')
    c_camp = col(df, '캠페인명', '캠페인')
    c_jim = col(df, '광고 노출 지면')
    c_kw = col(df, '키워드')
    c_imp = col(df, '노출수')
    c_clk = col(df, '클릭수')
    c_cost = col(df, '광고비')
    per = '(14일)' if a.d14 else '(1일)'
    c_ord = col(df, f'총 주문수{per}', '총 주문수(1일)', '주문수')
    c_rev = col(df, f'총 전환매출액{per}', '총 전환매출액(1일)', '전환매출액')
    if not all([c_prod, c_clk, c_cost, c_ord, c_rev]):
        print('❌ 컬럼 매칭 실패. 포맷 확인:', list(df.columns)); sys.exit(3)

    def is_bi(v):  # 비검색 영역
        return '비검색' in str(v)
    def is_auto(r):  # 자동매칭: 검색영역인데 키워드 없음
        return (c_jim and '검색' in str(r[c_jim]) and not is_bi(r[c_jim])
                and c_kw and str(r[c_kw]).strip() in ('', 'nan', '-'))

    tag = '14일누적(소급반영)' if a.d14 else '1일(당일)'
    print(f'=== 쿠팡 {a.account}({code}) — {fname} [{tag} 기준] ===')

    # ── 캠페인별 + SKU별 + 실제전환 ──
    if a.by_campaign and c_camp:
        for camp, cg in sorted(df.groupby(c_camp), key=lambda i: -i[1][c_cost].sum()):
            cost = cg[c_cost].sum()
            if cost < 300: continue
            clk, ordr, rev = cg[c_clk].sum(), cg[c_ord].sum(), cg[c_rev].sum()
            roas = round(rev / cost * 100) if cost else 0
            cvr = round(ordr / clk * 100, 1) if clk else 0
            print(f'\n■ {str(camp)[:36]} | 광고비{int(cost):,} 클릭{int(clk)} 주문{int(ordr)} 매출{int(rev):,} ROAS{roas}% CVR{cvr}%')
            for sku, sg in sorted(cg.groupby(c_prod), key=lambda i: -i[1][c_cost].sum()):
                sc = sg[c_cost].sum()
                if sc < 300: continue
                so, sr = sg[c_ord].sum(), sg[c_rev].sum()
                sroas = round(sr / sc * 100) if sc else 0
                print(f'    └집행 {cat(sku):<14} 광고비{int(sc):>7,} 주문{int(so):>3} 매출{int(sr):>8,} ROAS{sroas:>4}%')
            if c_cprod:
                cv = {}
                for _, r in cg[cg[c_rev] > 0].iterrows():
                    cv[cat(r[c_cprod])] = cv.get(cat(r[c_cprod]), 0) + r[c_rev]
                if cv:
                    s = ' / '.join(f'{k} {int(v):,}' for k, v in sorted(cv.items(), key=lambda i: -i[1]))
                    print(f'    ▶실제전환(발생상품 기준): {s}')
        print('\n⚠️ 스마트광고는 광고집행≠전환발생(A 보여주고 B 구매). SKU 집행ROAS는 참고용 — 실제 판매는 ▶실제전환 기준으로 볼 것.')

    # ── 옵션ID별 ──
    elif a.by_option and c_opt:
        agg = {}
        for _, r in df.iterrows():
            if a.by_option not in str(r[c_prod]): continue
            k = str(r[c_opt])
            x = agg.setdefault(k, {'클릭': 0, '광고비': 0, '주문': 0, '매출': 0})
            x['클릭'] += r[c_clk]; x['광고비'] += r[c_cost]; x['주문'] += r[c_ord]; x['매출'] += r[c_rev]
        print(f'{"옵션ID":<18} 광고비 클릭 주문 GMV매출 ROAS CVR')
        for k, x in sorted(agg.items(), key=lambda i: -i[1]['광고비']):
            if x['광고비'] < 300: continue
            roas = round(x['매출'] / x['광고비'] * 100) if x['광고비'] else 0
            cvr = round(x['주문'] / x['클릭'] * 100, 1) if x['클릭'] else 0
            print(f'{k[:18]:<18} {int(x["광고비"]):>7,} {int(x["클릭"]):>4} {int(x["주문"]):>3} {int(x["매출"]):>9,} {roas:>4}% {cvr:>4}%')

    # ── 품목별 + 검색/비검색 + 자동매칭 ──
    else:
        agg = {}
        for _, r in df.iterrows():
            k = cat(r[c_prod])
            x = agg.setdefault(k, {'클릭': 0, '광고비': 0, '주문': 0, '매출': 0,
                                   '검비': 0, '검매': 0, '비검비': 0, '비검매': 0, '자클': 0})
            x['클릭'] += r[c_clk]; x['광고비'] += r[c_cost]; x['주문'] += r[c_ord]; x['매출'] += r[c_rev]
            if c_jim and is_bi(r[c_jim]):
                x['비검비'] += r[c_cost]; x['비검매'] += r[c_rev]
            else:
                x['검비'] += r[c_cost]; x['검매'] += r[c_rev]
                if is_auto(r): x['자클'] += r[c_clk]
        print(f'{"품목":<14} {"광고비":>8} {"클릭":>4} {"주문":>4} {"매출":>9} {"ROAS":>5} {"CVR":>5} │ {"검색":>5} {"비검":>5} 자동매칭')
        for k, x in sorted(agg.items(), key=lambda i: -i[1]['광고비']):
            if x['광고비'] < 300: continue
            roas = round(x['매출'] / x['광고비'] * 100) if x['광고비'] else 0
            cvr = round(x['주문'] / x['클릭'] * 100, 1) if x['클릭'] else 0
            sr = round(x['검매'] / x['검비'] * 100) if x['검비'] else 0
            br = round(x['비검매'] / x['비검비'] * 100) if x['비검비'] else 0
            auto = f'클릭{int(x["자클"])}' if x['자클'] else '-'
            print(f'{k[:14]:<14} {int(x["광고비"]):>8,} {int(x["클릭"]):>4} {int(x["주문"]):>4} {int(x["매출"]):>9,} {roas:>4}% {cvr:>4}% │ {sr:>4}% {br:>4}% {auto}')

    print('※ GMV(판매가) ROAS. 1일=당일(소급 덜 됨)/14일=누적(--d14). 검색/비검색·SKU·전환발생 전수 파싱.')


if __name__ == '__main__':
    main()
