#!/usr/bin/env python3
"""쿠팡 광고 대시보드 구글시트 — 날짜 내림차순 정렬

모든 날짜 기반 워크시트를 최신→과거 순(내림차순)으로 정렬.
헤더(1행)는 유지, 데이터 행만 정렬.
좌정렬 유지.
"""
import warnings
warnings.filterwarnings('ignore')

import gspread
from google.oauth2.service_account import Credentials
import time

# ── 설정 ──────────────────────────────────────────────────────
SA_KEY = "/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json"
SHEET_ID = "1RqEKC5KT0O_aZWnsDH4UdX3grfYSpg68hqyJteRVmBw"

# 정렬 대상 워크시트 (키워드 TOP 제외 — 날짜 컬럼 아님)
SORT_WORKSHEETS = [
    "채움컴퍼니 요약",
    "채움컴퍼니 캠페인별",
    "채움컴퍼니 검색/비검색",
    "비코어랩 요약",
    "비코어랩 캠페인별",
    "비코어랩 검색/비검색",
]


def connect_sheet():
    creds = Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def sort_worksheet_descending(sh, ws_name):
    """워크시트를 날짜 내림차순으로 정렬 (Google Sheets API의 sortRange 사용)"""
    try:
        ws = sh.worksheet(ws_name)
    except gspread.WorksheetNotFound:
        print(f"  ⚠️ '{ws_name}' 워크시트 없음 — 건너뜀")
        return False

    # 데이터 행 수 확인
    all_values = ws.get_all_values()
    if len(all_values) <= 1:
        print(f"  ⏭️ '{ws_name}': 데이터 없음")
        return False

    # 이미 내림차순인지 확인
    dates = [r[0] for r in all_values[1:] if r[0].strip()]
    if dates and dates[0] >= dates[-1] and len(dates) > 1:
        # 추가 확인: 모든 날짜가 내림차순인지
        is_desc = all(dates[i] >= dates[i+1] for i in range(len(dates)-1))
        if is_desc:
            print(f"  ✅ '{ws_name}': 이미 내림차순 ({dates[0]} → {dates[-1]})")
            return True

    sheet_id = ws.id
    num_rows = len(all_values)
    num_cols = len(all_values[0])

    # Google Sheets API sortRange 요청 (헤더 제외: startRowIndex=1)
    request = {
        "sortRange": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,  # 헤더 스킵
                "endRowIndex": num_rows,
                "startColumnIndex": 0,
                "endColumnIndex": num_cols,
            },
            "sortSpecs": [
                {
                    "dimensionIndex": 0,  # A열 (날짜)
                    "sortOrder": "DESCENDING",
                }
            ],
        }
    }

    sh.batch_update({"requests": [request]})
    print(f"  ✅ '{ws_name}': 내림차순 정렬 완료 ({num_rows - 1}행)")

    # 좌정렬 적용
    align_request = {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": num_rows,
                "startColumnIndex": 0,
                "endColumnIndex": num_cols,
            },
            "cell": {
                "userEnteredFormat": {
                    "horizontalAlignment": "LEFT",
                }
            },
            "fields": "userEnteredFormat.horizontalAlignment",
        }
    }
    sh.batch_update({"requests": [align_request]})

    return True


def main():
    print("=== 쿠팡 광고 대시보드 날짜 내림차순 정렬 ===\n")
    sh = connect_sheet()
    print(f"시트: {sh.title}\n")

    success_count = 0
    for ws_name in SORT_WORKSHEETS:
        result = sort_worksheet_descending(sh, ws_name)
        if result:
            success_count += 1
        time.sleep(1)  # API rate limit

    print(f"\n✅ 완료! {success_count}/{len(SORT_WORKSHEETS)} 워크시트 정렬됨")


if __name__ == "__main__":
    main()
