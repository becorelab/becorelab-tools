"""1688 SKU 가격 필터 — 타겟 단가 기준 정리 → 구글 시트"""
import json
import time
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from search_1688 import login, BASE_URL, _post_json

SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"
SHEET_NAME = "1688 SKU 비교"
KEY_PATH = (
    r"C:\Users\info\claudeaiteam\sourcing\analyzer"
    r"\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TARGET_CNY = 2.92  # $0.4 × 7.3

HEADERS = [
    "제품#", "제품명(영문)", "판매자유형", "총판매량", "재구매율", "총점",
    "SKU 옵션", "SKU 가격(¥)", "타겟이하?", "재고",
    "1688 링크",
]

# 대표님 노란색 표시 = 정확히 일치하는 제품 (2,6,8,9,10번)
PRODUCT_IDS = [
    ("755625545032", True),    # 2번 ★
    ("823356873827", True),    # 6번 ★
    ("984657287237", True),    # 8번 ★
    ("858054829289", True),    # 9번 ★
    ("987266748920", True),    # 10번 ★ (원본)
]


def find_product(pid: str, token: str) -> dict:
    body = {"id": pid, "platform": "alibaba", "lang": "en"}
    return _post_json(f"{BASE_URL}/v1/products/find", body, token=token)


def main():
    token = login()
    if not token:
        print("Login failed")
        return

    creds = Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(SHEET_ID)

    try:
        ws = ss.worksheet(SHEET_NAME)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=SHEET_NAME, rows=500, cols=len(HEADERS))

    ws.append_row(HEADERS)
    ws.format("1", {"textFormat": {"bold": True}})

    all_rows = []

    for idx, (pid, is_match) in enumerate(PRODUCT_IDS, 1):
        print(f"[{idx}/{len(PRODUCT_IDS)}] {pid} {'★' if is_match else ''}")
        data = find_product(pid, token)
        if data.get("error"):
            print(f"  skip")
            continue

        title = data.get("titleEn", "")[:80]
        review = data.get("review", {})
        sold = data.get("sold", "")
        retention = f"{review.get('retention_rate', 0)*100:.1f}%" if review.get('retention_rate') else ""
        total_score = review.get("total_score", "")
        seller_type = data.get("seller_type", "")
        link = f"https://detail.1688.com/offer/{pid}.html"

        skus = data.get("skus", [])
        for s in skus:
            opts = s.get("options", [])
            opt_name = opts[0].get("valueEn", opts[0].get("value", "")) if opts else ""
            price = s.get("price", 0)
            stock = s.get("quantity", "")
            under_target = "O" if price <= TARGET_CNY else ""

            all_rows.append([
                idx, title, seller_type, sold, retention, total_score,
                opt_name[:80], price, under_target, stock,
                link,
            ])

        time.sleep(0.5)

    if all_rows:
        ws.append_rows(all_rows, value_input_option="USER_ENTERED")

    # 타겟 이하 셀 초록색 하이라이트
    for i, row in enumerate(all_rows, 2):  # row 2부터 (header=1)
        if row[8] == "O":  # 타겟이하 컬럼
            ws.format(f"H{i}", {"backgroundColor": {"red": 0.85, "green": 1, "blue": 0.85}})
            ws.format(f"I{i}", {"backgroundColor": {"red": 0.85, "green": 1, "blue": 0.85}})

    target_count = sum(1 for r in all_rows if r[8] == "O")
    print(f"\n전체 SKU {len(all_rows)}개 중 타겟(¥{TARGET_CNY}) 이하: {target_count}개")
    print(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == "__main__":
    main()
