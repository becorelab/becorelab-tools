#!/usr/bin/env python3
"""광고변경사항 시트 기록 도구 (광고 하치 전용)

대표님 관리 시트 `1bmN5H7lB...` 의 '광고변경사항' 탭에 한 줄 기록.
매번 시트 구조를 다시 파악하지 않아도 되게 컬럼 매핑·삽입위치·좌정렬을 내장.

컬럼 매핑 (실측, 2026-06-22):
  [0]일자 [1]계정 [2]캠페인 [3]예산 [4]'' [5]'' [6]ROAS [7]코멘트
삽입: 최신순(맨 위 데이터행 위에 insert) + 새 행 좌정렬

사용 예:
  # OFF/단순변경 (예산·ROAS 없음)
  python3 log_ad_change.py --account 채움컴퍼니 \
    --campaign "260619_얼룩제거제 매출스타트 — 캠페인 OFF" \
    --comment "오가닉 클릭 회복으로 매출스타트 종료, AI스마트 전환"

  # 신규/증액 (예산·ROAS 포함)
  python3 log_ad_change.py --account 비코어랩 \
    --campaign "260621_캡슐표백제 매출최적화 (신규)" \
    --budget "30,000원" --roas "270.00%" \
    --comment "시장가 대비 높아 캠페인 새로 세팅"

옵션:
  --date YY.MM.DD   (기본: 오늘)
  --force           (같은 날짜+캠페인 중복이어도 강제 기록)
"""
import argparse, datetime, re, sys
import gspread
from google.oauth2.service_account import Credentials

SHEET_KEY = '1bmN5H7lB-kIr9Oo5vqUokXanTM0O7xeCMgHoP24WAJg'
TAB = '광고변경사항'
SA = '/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json'


def main():
    ap = argparse.ArgumentParser(description='광고변경사항 시트 한 줄 기록')
    ap.add_argument('--account', required=True, help='계정 (예: 비코어랩 / 채움컴퍼니 / 비코어랩(메타))')
    ap.add_argument('--campaign', required=True, help='캠페인명 (+ 변경요약, 예: "... — 캠페인 OFF")')
    ap.add_argument('--comment', default='', help='코멘트 (사유·맥락·추적포인트)')
    ap.add_argument('--budget', default='', help='예산 (예: "30,000원")')
    ap.add_argument('--roas', default='', help='ROAS (예: "270.00" 또는 "270.00퍼센트")')
    ap.add_argument('--date', default=datetime.datetime.now().strftime('%y.%m.%d'), help='YY.MM.DD (기본 오늘)')
    ap.add_argument('--force', action='store_true', help='중복이어도 강제 기록')
    a = ap.parse_args()

    creds = Credentials.from_service_account_file(SA, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_KEY)
    ws = sh.worksheet(TAB)
    v = ws.get_all_values()

    # 첫 데이터행 동적 감지 (헤더 줄 수가 바뀌어도 안전). [0]이 YY.MM.DD 패턴인 첫 행.
    data_row = None
    for i, r in enumerate(v):
        if r and re.match(r'\d{2}\.\d{2}\.\d{2}', str(r[0])):
            data_row = i + 1  # gspread는 1-based
            break
    if data_row is None:
        print('❌ 데이터 시작행(YY.MM.DD)을 못 찾음. 시트 구조 확인 필요.')
        sys.exit(2)

    # 중복 체크 (최근 6행 내 같은 날짜 + 캠페인 앞부분 일치)
    key = a.campaign[:15]
    for r in v[data_row - 1: data_row + 5]:
        if len(r) > 2 and r[0] == a.date and key and key in str(r[2]):
            if not a.force:
                print(f'⚠️ 이미 기록된 듯: {r[0]} / {str(r[2])[:34]}')
                print('   강제 기록하려면 --force')
                sys.exit(1)

    new = [a.date, a.account, a.campaign, a.budget, '', '', a.roas, a.comment]
    ws.insert_row(new, data_row, value_input_option='USER_ENTERED')

    # 새 행 좌정렬
    body = {'requests': [{'repeatCell': {
        'range': {'sheetId': ws.id, 'startRowIndex': data_row - 1, 'endRowIndex': data_row},
        'cell': {'userEnteredFormat': {'horizontalAlignment': 'LEFT'}},
        'fields': 'userEnteredFormat.horizontalAlignment'}}]}
    sh.batch_update(body)

    print(f'✅ 기록 완료 (row {data_row})')
    print(f'   {a.date} | {a.account} | {a.campaign}')
    if a.budget or a.roas:
        print(f'   예산 {a.budget or "-"} / ROAS {a.roas or "-"}')
    if a.comment:
        print(f'   💬 {a.comment[:60]}')


if __name__ == '__main__':
    main()
