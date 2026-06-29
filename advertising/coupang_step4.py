#!/usr/bin/env python3
"""쿠팡 광고 Step4 심화 분석 (Cowork 로드맵 Step4 쿠팡판)

메타 4D는 연령·성별이지만, 쿠팡은 그 차원이 없는 대신 더 풍부한 차원이 있다:
  - 퍼널: 노출 → 클릭(CTR) → 주문(CVR) 단계별 누수
  - 직접/간접: 광고 직접전환 vs 간접(지연·오가닉) 전환 분리 → 표면ROAS 거품 자동검출
  - 키워드 4분면: ROAS×클릭으로 에이스/볼륨낭비(제외후보)/잠재(증액)/관망 분류
  - 교차전환맵: 광고집행 상품 → 실제 전환발생 상품 (스마트광고 A→B)

사용 예:
  python3 coupang_step4.py --account rocket --item 코튼            # 전체(4모드)
  python3 coupang_step4.py --account gross --item 입테이프 --mode keyword --bep 350
  python3 coupang_step4.py --account rocket --item 식세기 --mode funnel
"""
import argparse, glob, os, sys
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

XFER = '/Users/macmini_ky/Library/CloudStorage/GoogleDrive-cky2833@gmail.com/내 드라이브/Claude AI work space/mac window file transfer'
ACCT = {'rocket': 'A00290275', 'gross': 'A00940134', 'seirab': 'A01707416'}


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
    ap = argparse.ArgumentParser(description='쿠팡 광고 Step4 심화 (퍼널·직접간접·키워드4분면·교차전환맵)')
    ap.add_argument('--account', default='rocket', choices=list(ACCT))
    ap.add_argument('--date', default='', help='YYYYMMDD (기본 최신)')
    ap.add_argument('--item', default='', help='품목 필터 (예: 코튼, 식세기, 입테이프)')
    ap.add_argument('--mode', default='all', choices=['all', 'funnel', 'direct', 'keyword', 'crossmap'])
    ap.add_argument('--bep', type=float, default=300, help='키워드 4분면 손익분기 ROAS%% (기본 300)')
    ap.add_argument('--d14', action='store_true', help='14일 누적(소급반영) 기준')
    ap.add_argument('--days', type=int, default=1, help='최근 N일 1일파일 합산 (키워드 4분면 신뢰도↑)')
    a = ap.parse_args()

    code = ACCT[a.account]
    import re as _re
    files = sorted(glob.glob(f'{XFER}/{code}_pa_daily_keyword_*'))
    # 1일 파일만 (파일명 시작==종료) — 기간 합산파일 제외
    def is_1day(f):
        m = _re.search(r'_(\d{8})_(\d{8})', f)
        return bool(m) and m.group(1) == m.group(2)
    oneday = [f for f in files if is_1day(f)]
    if a.date:
        oneday = [f for f in oneday if a.date in f]
    if not oneday:
        print(f'❌ 보고서 없음: {code}_pa_daily_keyword_* {a.date}'); sys.exit(2)
    if a.days > 1:
        sel = oneday[-a.days:]
        df = pd.concat([pd.read_excel(f) for f in sel], ignore_index=True)
        d0, d1 = _re.search(r'_(\d{8})_', sel[0]).group(1), _re.search(r'_(\d{8})_', sel[-1]).group(1)
        fname = f'최근{len(sel)}일합산 {d0}~{d1}'
    else:
        fp = oneday[-1]; fname = os.path.basename(fp)
        df = pd.read_excel(fp)

    per = '(14일)' if a.d14 else '(1일)'
    c_prod = col(df, '광고집행 상품명', '상품명')
    c_cprod = col(df, '광고전환매출발생 상품명')
    c_jim = col(df, '광고 노출 지면')
    c_kw = col(df, '키워드')
    c_imp = col(df, '노출수')
    c_clk = col(df, '클릭수')
    c_cost = col(df, '광고비')
    c_ord = col(df, f'총 주문수{per}', '총 주문수(1일)')
    c_rev = col(df, f'총 전환매출액{per}', '총 전환매출액(1일)')
    c_drev = col(df, '직접 전환매출액(14일)' if a.d14 else '직접 전환매출액(1일)', '직접 전환매출액(1일)')
    c_irev = col(df, '간접 전환매출액(14일)' if a.d14 else '간접 전환매출액(1일)', '간접 전환매출액(1일)')
    if not all([c_prod, c_clk, c_cost, c_ord, c_rev]):
        print('❌ 컬럼 매칭 실패:', list(df.columns)); sys.exit(3)

    if a.item:
        df = df[df[c_prod].apply(lambda x: a.item in str(x) or a.item in cat(x))]
        if df.empty:
            print(f'❌ "{a.item}" 데이터 없음'); sys.exit(2)

    def is_bi(v): return '비검색' in str(v)
    tag = '14일누적' if a.d14 else '1일(당일)'
    item_lbl = f' · {a.item}' if a.item else ''
    print(f'=== 쿠팡 Step4 {a.account}({code}){item_lbl} — {fname} [{tag}] ===')

    # ── 1. 퍼널: 노출 → 클릭(CTR) → 주문(CVR) ──
    if a.mode in ('all', 'funnel') and c_imp:
        print('\n■ 퍼널 (노출→클릭→주문)')
        print(f'{"지면":<8}{"노출":>9}{"클릭":>7}{"CTR":>7}{"주문":>6}{"CVR":>7}{"ROAS":>7}')
        rows = [('전체', df)]
        if c_jim:
            rows += [('검색', df[~df[c_jim].apply(is_bi)]), ('비검색', df[df[c_jim].apply(is_bi)])]
        for lbl, sub in rows:
            imp, clk = sub[c_imp].sum(), sub[c_clk].sum()
            ordr, rev, cost = sub[c_ord].sum(), sub[c_rev].sum(), sub[c_cost].sum()
            ctr = clk / imp * 100 if imp else 0
            cvr = ordr / clk * 100 if clk else 0
            roas = rev / cost * 100 if cost else 0
            print(f'{lbl:<8}{int(imp):>9,}{int(clk):>7,}{ctr:>6.2f}%{int(ordr):>6}{cvr:>6.1f}%{roas:>6.0f}%')
        # 누수 진단: 검색 CTR 기준 (비검색은 추천 노출폭탄이라 전체CTR 왜곡)
        sr = df[~df[c_jim].apply(is_bi)] if c_jim else df
        simp, sclk, sord = sr[c_imp].sum(), sr[c_clk].sum(), sr[c_ord].sum()
        sctr = sclk / simp * 100 if simp else 0
        scvr = sord / sclk * 100 if sclk else 0
        diag = []
        if sctr < 1.0: diag.append(f'검색CTR {sctr:.2f}% 낮음→노출 대비 클릭 약(썸네일/순위/가격)')
        if scvr < 12: diag.append(f'검색CVR {scvr:.1f}% 낮음→클릭 대비 전환 약(상세/리뷰/가격)')
        if diag: print('  ⚠️ ' + ' / '.join(diag))
        else: print(f'  ✅ 검색 퍼널 양호 (CTR {sctr:.2f}% / CVR {scvr:.1f}%)')

    # ── 2. 직접/간접 분리: 표면ROAS 거품 검출 ──
    if a.mode in ('all', 'direct') and c_drev and c_irev:
        print('\n■ 직접/간접 전환 (표면ROAS 거품 검출)')
        drev, irev, cost = df[c_drev].sum(), df[c_irev].sum(), df[c_cost].sum()
        tot = drev + irev
        droas = drev / cost * 100 if cost else 0
        troas = tot / cost * 100 if cost else 0
        ibi = irev / tot * 100 if tot else 0
        print(f'  직접ROAS {droas:.0f}% (광고 직접전환) | 총ROAS {troas:.0f}% | 간접비중 {ibi:.0f}%')
        if ibi >= 50:
            print(f'  ⚠️ 간접비중 {ibi:.0f}% 높음 → 지연·오가닉 어트리뷰션 의심. 총ROAS는 거품일 수 있음, 직접ROAS가 진짜 광고 기여')
        elif ibi >= 30:
            print(f'  🟡 간접비중 {ibi:.0f}% — 지연전환 일부 포함, 직접ROAS 병행 확인')
        else:
            print(f'  ✅ 직접전환 위주({100-ibi:.0f}%) — ROAS 신뢰도 높음')

    # ── 3. 키워드 4분면: 제외/증액 자동 추천 ──
    if a.mode in ('all', 'keyword') and c_kw and c_jim:
        srch = df[(~df[c_jim].apply(is_bi)) &
                  (df[c_kw].astype(str).str.strip().replace('nan', '') != '')]
        if not srch.empty:
            kw = srch.groupby(c_kw).agg(클릭=(c_clk, 'sum'), 광고비=(c_cost, 'sum'),
                                        주문=(c_ord, 'sum'), 매출=(c_rev, 'sum')).reset_index()
            kw = kw[kw['광고비'] >= 300]
            if not kw.empty:
                kw['ROAS'] = (kw['매출'] / kw['광고비'] * 100).round()
                kw['CVR'] = (kw['주문'] / kw['클릭'] * 100).round(1)
                cmed = kw['클릭'].median()
                bep = a.bep
                minclk = max(cmed, 5)  # 최소 5클릭 이상이라야 "클릭 많음"(소액 1~2클릭 노이즈 제거)
                def quad(r):
                    hi_roas = r['ROAS'] >= bep
                    hi_clk = r['클릭'] >= minclk
                    if hi_roas and hi_clk: return '🏆에이스'
                    if (not hi_roas) and hi_clk:
                        return '🔴볼륨낭비(제외후보)' if r['ROAS'] < bep * 0.6 else '🟡관망'
                    if hi_roas and not hi_clk: return '🚀잠재(증액)'
                    return '⚪관망'
                kw['분류'] = kw.apply(quad, axis=1)
                print(f'\n■ 키워드 4분면 (검색, BEP {bep:.0f}% / 클릭기준 {minclk:.0f}+)')
                print(f'{"키워드":<20}{"클릭":>5}{"광고비":>8}{"ROAS":>6}{"CVR":>7}  분류')
                for _, r in kw.sort_values('광고비', ascending=False).head(15).iterrows():
                    print(f'{str(r[c_kw])[:20]:<20}{int(r["클릭"]):>5}{int(r["광고비"]):>8,}{int(r["ROAS"]):>5}%{r["CVR"]:>6.1f}%  {r["분류"]}')
                ex = kw[kw['분류'].str.contains('제외후보')]
                if not ex.empty:
                    waste = int(ex['광고비'].sum())
                    if a.days > 1:
                        unit, note = f'{a.days}일누적', ' (여러날 합산 — 신뢰도↑)'
                    elif a.d14:
                        unit, note = '14일', ''
                    else:
                        unit, note = '일', ' ⚠️1일 단발 — --days 7 로 재확인 권장'
                    print(f'  💡 제외후보 {len(ex)}개 = 광고비 {waste:,}원/{unit} (ROAS<{bep*0.6:.0f}%·클릭{minclk:.0f}+).{note}')
                up = kw[kw['분류'].str.contains('잠재')]
                if not up.empty:
                    print(f'  💡 증액후보 {len(up)}개 (ROAS>{bep:.0f}%인데 클릭 적음) — 입찰가↑ 여지')

    # ── 4. 교차전환맵: 집행 → 전환발생 (스마트광고 A→B) ──
    if a.mode in ('all', 'crossmap') and c_cprod:
        cr = df[df[c_rev] > 0].copy()
        if not cr.empty:
            cr['집행'] = cr[c_prod].apply(cat)
            cr['전환'] = cr[c_cprod].apply(cat)
            xx = cr[cr['집행'] != cr['전환']].groupby(['집행', '전환'])[c_rev].sum().sort_values(ascending=False)
            if not xx.empty:
                print('\n■ 교차전환맵 (A 광고 → B 구매, 스마트광고)')
                for (aitem, bitem), rev in xx.head(10).items():
                    print(f'    {aitem} 광고 → {bitem} 구매: {int(rev):,}원')
                print('    ※ 같은 캠페인에 여러 품목이 있을 때, 광고예산이 어디서 어디로 전환되는지')

    print('\n※ GMV(판매가) ROAS. 1일=당일(소급 덜됨)/14일=누적(--d14). 직접=광고 직접전환·간접=지연/타경로.')


if __name__ == '__main__':
    main()
