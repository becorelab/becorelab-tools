#!/usr/bin/env python3
"""쿠팡 광고 보고서 품목별 요약 (광고 하치 전용)

전송폴더의 키워드 보고서 xlsx → 품목별 광고비/클릭/주문/매출/ROAS/CVR.
매일 아침 보고서 파싱 코드 새로 짜던 걸 도구화.

사용 예:
  python3 coupang_ad_summary.py --account rocket           # 최신 로켓(비코어랩) 보고서
  python3 coupang_ad_summary.py --account gross --date 20260621
  python3 coupang_ad_summary.py --account rocket --by-option 코튼   # 특정 품목 옵션ID별

옵션:
  --account rocket(A00290275·비코어랩)|gross(A00940134·채움컴퍼니)
  --date YYYYMMDD (기본: 최신 파일)
  --by-option <품목키워드>  해당 품목을 옵션ID별로 분해

주의: GMV(판매가) ROAS임 — 정산마진은 더 낮음 (원가·물류·수수료·광고비 차감 전).
"""
import argparse, glob, os, sys
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

XFER = '/Users/macmini_ky/Library/CloudStorage/GoogleDrive-cky2833@gmail.com/내 드라이브/앱/mac window file transfer'
ACCT = {'rocket': 'A00290275', 'gross': 'A00940134'}


def cat(nm):
    s = str(nm)
    if '표백제' in s: return '캡슐표백제'
    if '캡슐세제' in s or '세탁세제' in s: return '캡슐세제'   # '코튼블루향'이 있어 코튼보다 먼저
    if '하트' in s and '식' in s: return '하트식세기'
    if '식기세척' in s: return '식세기(올인원)'
    if '섬유탈취' in s or '스타일' in s: return '섬유탈취제'
    if '건조기시트' in s or '코튼' in s: return '건조기시트 코튼블루'  # 캡슐세제·섬유탈취 위에서 걸러서 '코튼' 단독 안전
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
    ap = argparse.ArgumentParser(description='쿠팡 광고 품목별 요약')
    ap.add_argument('--account', default='rocket', choices=list(ACCT))
    ap.add_argument('--date', default='', help='YYYYMMDD (기본 최신)')
    ap.add_argument('--by-option', default='', help='해당 품목키워드를 옵션ID별로 분해')
    a = ap.parse_args()

    code = ACCT[a.account]
    files = sorted(glob.glob(f'{XFER}/{code}_pa_daily_keyword_*'))
    if not files:
        print(f'❌ 보고서 없음: {code}_pa_daily_keyword_*')
        sys.exit(2)
    if a.date:
        files = [f for f in files if a.date in f]
        if not files:
            print(f'❌ {a.date} 보고서 없음')
            sys.exit(2)
    fp = files[-1]
    fname = os.path.basename(fp)
    df = pd.read_excel(fp)

    c_prod = col(df, '광고집행 상품명', '상품명')
    c_opt = col(df, '광고집행 옵션ID', '옵션ID')
    c_imp = col(df, '노출수')
    c_clk = col(df, '클릭수')
    c_cost = col(df, '광고비')
    c_ord = col(df, '총 주문수(14일)', '총 주문수(1일)', '주문수')
    c_rev = col(df, '총 전환매출액(14일)', '전환매출액')
    if not all([c_prod, c_imp, c_clk, c_cost, c_ord, c_rev]):
        print('❌ 컬럼 매칭 실패. 보고서 포맷 확인:', list(df.columns))
        sys.exit(3)

    keyfn = (lambda r: str(r[c_opt])) if a.by_option else (lambda r: cat(r[c_prod]))
    agg = {}
    for _, r in df.iterrows():
        if a.by_option and a.by_option not in str(r[c_prod]):
            continue
        k = keyfn(r)
        x = agg.setdefault(k, {'노출': 0, '클릭': 0, '광고비': 0, '주문': 0, '매출': 0})
        x['노출'] += r[c_imp]; x['클릭'] += r[c_clk]; x['광고비'] += r[c_cost]
        x['주문'] += r[c_ord]; x['매출'] += r[c_rev]

    title = f'옵션별({a.by_option})' if a.by_option else '품목별'
    print(f'=== 쿠팡 {a.account}({code}) {title} — {fname} ===')
    print(f'{"항목":<18} 광고비 클릭 주문 GMV매출 ROAS CVR')
    for k, x in sorted(agg.items(), key=lambda i: -i[1]['광고비']):
        if x['광고비'] < 300:
            continue
        roas = round(x['매출'] / x['광고비'] * 100) if x['광고비'] else 0
        cvr = round(x['주문'] / x['클릭'] * 100, 1) if x['클릭'] else 0
        print(f'{k[:18]:<18} {int(x["광고비"]):>7,} {int(x["클릭"]):>4} {int(x["주문"]):>3} {int(x["매출"]):>9,} {roas:>4}% {cvr:>4}%')
    print('※ GMV(판매가) ROAS — 정산마진은 더 낮음')


if __name__ == '__main__':
    main()
