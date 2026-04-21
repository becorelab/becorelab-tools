"""1688 검색 결과 → 구글 시트 업로드"""

import json
import sys
from pathlib import Path
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"
SHEET_NAME = "1688 검색"
KEY_PATH = (
    r"C:\Users\User\claudeaiteam\sourcing\analyzer"
    r"\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "번호", "키워드", "제품명(중문)", "제품명(영문)", "가격(¥)",
    "판매량", "재구매율", "판매자유형", "평점",
    "1688 링크", "이미지", "검색일시",
]


def get_sheet():
    creds = Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(SHEET_ID)

    try:
        ws = ss.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=SHEET_NAME, rows=200, cols=len(HEADERS))
        ws.append_row(HEADERS)
        ws.format("1", {"textFormat": {"bold": True}})

    return ws


def upload_results(result_path: str = None):
    if result_path is None:
        result_path = str(Path(__file__).parent / "1688_last_result.json")

    data = json.loads(Path(result_path).read_text(encoding="utf-8"))
    if not data.get("success"):
        print(f"결과 파일에 에러: {data.get('error', 'unknown')}")
        return

    keyword = data.get("keyword", "")
    items = data.get("data", {}).get("items", [])
    if not items:
        print("검색 결과 없음")
        return

    ws = get_sheet()
    existing = ws.get_all_values()
    next_num = len(existing)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for i, item in enumerate(items, 1):
        rows.append([
            next_num + i - 1,
            keyword,
            item.get("title", ""),
            item.get("titleEn", ""),
            item.get("price", ""),
            item.get("sales_volume", ""),
            item.get("retention_rate", ""),
            item.get("seller_type", ""),
            item.get("level", ""),
            item.get("link", ""),
            item.get("img_url", ""),
            now,
        ])

    ws.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"구글 시트 업로드 완료! {len(rows)}건 → '{SHEET_NAME}' 워크시트")
    print(f"시트: https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    upload_results(path)
