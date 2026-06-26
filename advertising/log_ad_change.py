#!/usr/bin/env python3
"""광고변경사항 시트 기록 도구 (광고 하치 전용)

대표님 관리 시트 `1bmN5H7lB...` 의 '광고변경사항' 탭에 한 줄 기록.
매번 시트 구조를 다시 파악하지 않아도 되게 컬럼 매핑·삽입위치·좌정렬을 내장.

컬럼 매핑 (실측, 2026-06-26 정정 — 데이터는 B열부터, A열은 빈칸):
  [0]빈칸 [1]일자 [2]계정 [3]캠페인 [4]예산(전) [5]예산(후) [6]ROAS(전) [7]ROAS(후) [8]코멘트
  ※ 단일 변경값은 '변경후' 컬럼([5]예산후·[7]ROAS후)에 기록
삽입: 최신순(맨 위 데이터행 위에 insert) + 인접행 서식복사(배경색) + 좌정렬

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

# 캠페인별 배경색 (대표님 시트 색 규칙, 2026-06-27 확립). 순서=우선순위(구체적 먼저)
CAMP_COLORS = [
    ('캡슐표백제', (0.7058824, 0.36862746, 0.019607844)),  # 브라운
    ('세이랩',     (0.4, 0.78, 0.70)),                       # 청록(신규)
    ('얼룩',       (0.71, 0.84, 0.66)),                      # 초록
    ('베이비',     (1.0, 0.99, 0.80)),                       # 연노랑
    ('바이올렛',   (0.87, 0.58, 0.81)),                      # 분홍
    ('입테이프',   (1.0, 0.6, 1.0)), ('입벌림', (1.0, 0.6, 1.0)),  # 핑크
    ('코튼',       (0.76, 0.86, 0.96)),                      # 파랑
    ('260413',     (0.96, 0.8, 0.8)),                        # 살구 (채움 AI스마트)
    ('2024',       (1.0, 0.85, 0.4)),                        # 노랑 (비코어랩 로켓 스마트)
    ('섬유탈취',   (0.29, 0.53, 0.91)),                      # 파랑
    ('하트',       (0.92, 0.6, 0.6)), ('식세기', (0.92, 0.6, 0.6)),  # 빨강 (로켓 식세기)
]


def camp_color(campaign, account):
    """캠페인/계정명으로 배경색 매칭. 메타(별도 시트)·미매칭은 None(색 안 칠함)."""
    if '메타' in (account or ''):
        return None  # 메타는 별도 시트 관리 — 이 시트에선 색 안 입힘
    s = (campaign or '') + ' ' + (account or '')
    for kw, rgb in CAMP_COLORS:
        if kw in s:
            return {'red': rgb[0], 'green': rgb[1], 'blue': rgb[2]}
    return None


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

    # 첫 데이터행 동적 감지 (헤더 줄 수가 바뀌어도 안전). [1](B열)이 YY.MM.DD 패턴인 첫 행.
    data_row = None
    for i, r in enumerate(v):
        if len(r) > 1 and re.match(r'\d{2}\.\d{2}\.\d{2}', str(r[1])):
            data_row = i + 1  # gspread는 1-based
            break
    if data_row is None:
        print('❌ 데이터 시작행(YY.MM.DD)을 못 찾음. 시트 구조 확인 필요.')
        sys.exit(2)

    # 중복 체크 (최근 6행 내 같은 날짜 + 캠페인 앞부분 일치)
    key = a.campaign[:15]
    for r in v[data_row - 1: data_row + 5]:
        if len(r) > 3 and r[1] == a.date and key and key in str(r[3]):
            if not a.force:
                print(f'⚠️ 이미 기록된 듯: {r[0]} / {str(r[2])[:34]}')
                print('   강제 기록하려면 --force')
                sys.exit(1)

    # 데이터는 B열부터 (A열 빈칸). 단일 변경값은 변경후 컬럼([5]예산후·[7]ROAS후)에.
    new = ['', a.date, a.account, a.campaign, '', a.budget, '', a.roas, a.comment]
    ws.insert_row(new, data_row, value_input_option='USER_ENTERED')

    # 새 행 서식: 좌정렬 + 캠페인별 배경색 자동 적용 (메타·미매칭은 색 안 입힘)
    reqs = [{'repeatCell': {
        'range': {'sheetId': ws.id, 'startRowIndex': data_row - 1, 'endRowIndex': data_row},
        'cell': {'userEnteredFormat': {'horizontalAlignment': 'LEFT'}},
        'fields': 'userEnteredFormat.horizontalAlignment'}}]
    color = camp_color(a.campaign, a.account)
    if color:
        reqs.append({'repeatCell': {
            'range': {'sheetId': ws.id, 'startRowIndex': data_row - 1, 'endRowIndex': data_row, 'startColumnIndex': 1, 'endColumnIndex': 9},
            'cell': {'userEnteredFormat': {'backgroundColor': color}},
            'fields': 'userEnteredFormat.backgroundColor'}})
    sh.batch_update({'requests': reqs})
    print(f'   🎨 색: {"캠페인 매칭 적용" if color else "미매칭 → 흰색(수동 지정 필요)"}')

    print(f'✅ 기록 완료 (row {data_row})')
    print(f'   {a.date} | {a.account} | {a.campaign}')
    if a.budget or a.roas:
        print(f'   예산 {a.budget or "-"} / ROAS {a.roas or "-"}')
    if a.comment:
        print(f'   💬 {a.comment[:60]}')


if __name__ == '__main__':
    main()
