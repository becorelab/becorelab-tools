"""1688 유사 제품 비교 → 구글 시트 업로드"""
import json
import sys
import time
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from search_1688 import login, BASE_URL, _post_json

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
    "번호", "제품명(영문)", "제품명(중문)",
    "최저가(¥)", "SKU 가격대", "MOQ",
    "총판매량", "재고", "재구매율",
    "판매자유형", "서비스점수", "물류점수", "총점",
    "SKU 옵션 요약", "1688 링크", "이미지", "조회일시",
]


def find_product(product_id: str, token: str) -> dict:
    body = {"id": product_id, "platform": "alibaba", "lang": "en"}
    return _post_json(f"{BASE_URL}/v1/products/find", body, token=token)


def summarize_skus(skus: list) -> tuple:
    if not skus:
        return ("", "")
    prices = [s.get("price", 0) for s in skus if s.get("price")]
    price_range = f"¥{min(prices):.1f} ~ ¥{max(prices):.1f}" if prices else ""
    options = []
    for s in skus[:5]:
        opts = s.get("options", [])
        val = opts[0].get("valueEn", opts[0].get("value", "")) if opts else ""
        p = s.get("price", "")
        options.append(f"¥{p}: {val[:60]}")
    return (price_range, "\n".join(options))


def main():
    product_ids = [
        "987266748920",  # 원본 (배수구 트랩 40-138mm)
        "984457416994",  # 防臭地漏芯通用内芯
        "908742056608",  # 防虫浴室卫生间通用地漏防臭芯
        "854331463883",  # 防臭地漏芯 硅胶防虫
        "624762269308",  # 硅胶密封地漏防臭芯 50/40管
        "681097206531",  # 直排下水道卫生间防臭地漏芯
        "987716679572",  # 地漏防臭卫生间内芯 排水口
        "965772470092",  # 地漏防臭器通用内芯
    ]

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
        ws = ss.add_worksheet(title=SHEET_NAME, rows=200, cols=len(HEADERS))

    ws.append_row(HEADERS)
    ws.format("1", {"textFormat": {"bold": True}})

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []

    for i, pid in enumerate(product_ids, 1):
        print(f"[{i}/{len(product_ids)}] Fetching {pid}...")
        data = find_product(pid, token)

        if data.get("error"):
            print(f"  Error: {data}")
            continue

        review = data.get("review", {})
        skus = data.get("skus", [])
        price_range_str, sku_summary = summarize_skus(skus)

        price_ranges = data.get("price_range", [])
        min_price = ""
        if price_ranges:
            min_price = min(p.get("price", 999) for p in price_ranges)

        imgs = data.get("img_urls", [])
        img_url = imgs[0] if imgs else ""

        row = [
            i,
            data.get("titleEn", "")[:100],
            data.get("title", "")[:100],
            min_price,
            price_range_str,
            data.get("moq", ""),
            data.get("sold", ""),
            data.get("quantity", ""),
            f"{review.get('retention_rate', 0)*100:.1f}%" if review.get('retention_rate') else "",
            data.get("seller_type", ""),
            review.get("service_score", ""),
            review.get("logistics_score", ""),
            review.get("total_score", ""),
            sku_summary,
            f"https://detail.1688.com/offer/{pid}.html",
            img_url,
            now,
        ]
        rows.append(row)
        time.sleep(0.5)

    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"\n{len(rows)}개 제품 시트 업로드 완료!")
        print(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == "__main__":
    main()
