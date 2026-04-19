"""1688 이미지 검색 — Elimapi search-img"""
import json
import sys
import urllib.request
from pathlib import Path
from search_1688 import login, BASE_URL

def search_by_image(img_url: str, page: int = 1, size: int = 20) -> dict:
    token = login()
    if not token:
        return {"error": "login failed"}

    body = {
        "img_url": img_url,
        "platform": "alibaba",
        "page": page,
        "size": size,
        "lang": "en",
    }

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/v1/products/search-img",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode("utf-8"))


if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else (
        "https://cbu01.alicdn.com/img/ibank/O1CN01BuTOr71DtXeY02xhz_"
        "!!2208280790274-0-cib.jpg"
    )
    print(f"Image search: {img[:80]}...\n")
    result = search_by_image(img)

    items = result.get("items", [])
    print(f"Results: {len(items)}\n")
    for i, item in enumerate(items[:15], 1):
        title = item.get("title", "")
        price = item.get("price", "")
        link = item.get("link", "")
        sales = item.get("sales_volume", "")
        print(f"{i}. {title[:70]}")
        print(f"   Y{price} | sales: {sales} | {link}")
        print()

    out = Path(__file__).parent / "1688_img_result.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {out}")
