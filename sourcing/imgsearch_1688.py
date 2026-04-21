"""1688 이미지 검색 — 업로드 후 img_id로 검색"""
import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path
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


def download_image(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def upload_image(img_bytes: bytes, token: str) -> str:
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="product.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + img_bytes + f"\r\n--{boundary}\r\n".encode("utf-8") + (
        f'Content-Disposition: form-data; name="platform"\r\n\r\n'
        f"1688\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/v1/products/upload-image",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result.get("img_id", result.get("id", ""))


def search_by_img_id(img_id: str, token: str, page: int = 1, size: int = 30) -> dict:
    body = {
        "img_id": img_id,
        "platform": "alibaba",
        "page": page,
        "size": size,
        "lang": "en",
    }
    return _post_json(f"{BASE_URL}/v1/products/search-img", body, token=token)


def search_by_img_url(img_url: str, token: str, page: int = 1, size: int = 30) -> dict:
    body = {
        "img_url": img_url,
        "platform": "alibaba",
        "page": page,
        "size": size,
        "lang": "en",
    }
    return _post_json(f"{BASE_URL}/v1/products/search-img", body, token=token)


def find_product(product_id: str, token: str) -> dict:
    body = {"id": str(product_id), "platform": "alibaba", "lang": "en"}
    return _post_json(f"{BASE_URL}/v1/products/find", body, token=token)


def summarize_skus(skus: list) -> tuple:
    if not skus:
        return ("", "", "")
    prices = [s.get("price", 0) for s in skus if s.get("price")]
    price_range = f"¥{min(prices):.1f} ~ ¥{max(prices):.1f}" if prices else ""
    lines = []
    for s in skus[:8]:
        opts = s.get("options", [])
        val = opts[0].get("valueEn", opts[0].get("value", "")) if opts else ""
        p = s.get("price", "")
        q = s.get("quantity", "")
        lines.append(f"¥{p} (stock:{q}): {val[:70]}")
    return (price_range, "\n".join(lines), str(len(skus)))


HEADERS = [
    "번호", "제품명(영문)", "제품명(중문)",
    "최저가(¥)", "SKU 가격대", "SKU수", "MOQ",
    "총판매량", "재고", "재구매율",
    "판매자유형", "서비스", "물류", "총점",
    "SKU 상세 (실제가격)", "1688 링크", "이미지", "조회일시",
]


def main():
    ref_img = (
        "https://cbu01.alicdn.com/img/ibank/O1CN01BuTOr71DtXeY02xhz_"
        "!!2208280790274-0-cib.jpg"
    )

    token = login()
    if not token:
        print("Login failed")
        return

    # 1) 이미지 업로드 시도
    print("Uploading reference image...")
    try:
        img_bytes = download_image(ref_img)
        img_id = upload_image(img_bytes, token)
        print(f"  img_id: {img_id}")
        print("Searching by img_id...")
        search_result = search_by_img_id(img_id, token)
    except Exception as e:
        print(f"  Upload failed ({e}), trying img_url directly...")
        search_result = search_by_img_url(ref_img, token)

    if search_result.get("error"):
        print(f"Image search error: {json.dumps(search_result, ensure_ascii=False)}")
        return

    items = search_result.get("items", [])
    print(f"Found {len(items)} similar products\n")

    if not items:
        print("No results")
        return

    # 2) 상위 제품들 상세 조회
    top_ids = []
    seen = set()
    for item in items[:20]:
        pid = str(item.get("id", ""))
        if pid and pid not in seen:
            seen.add(pid)
            top_ids.append(pid)
        if len(top_ids) >= 10:
            break

    print(f"Fetching details for {len(top_ids)} products...")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []

    for i, pid in enumerate(top_ids, 1):
        print(f"  [{i}/{len(top_ids)}] {pid}")
        data = find_product(pid, token)
        if data.get("error"):
            print(f"    skip (error)")
            continue

        review = data.get("review", {})
        skus = data.get("skus", [])
        price_range_str, sku_detail, sku_count = summarize_skus(skus)

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
            sku_count,
            data.get("moq", ""),
            data.get("sold", ""),
            data.get("quantity", ""),
            f"{review.get('retention_rate', 0)*100:.1f}%" if review.get('retention_rate') else "",
            data.get("seller_type", ""),
            review.get("service_score", ""),
            review.get("logistics_score", ""),
            review.get("total_score", ""),
            sku_detail,
            f"https://detail.1688.com/offer/{pid}.html",
            img_url,
            now,
        ]
        rows.append(row)
        time.sleep(0.5)

    # 3) 시트 업로드
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

    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")

    print(f"\n{len(rows)}개 제품 업로드 완료!")
    print(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == "__main__":
    main()
