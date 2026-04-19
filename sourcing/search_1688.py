"""
1688 제품 검색 — Elimapi 연동
사용법: python search_1688.py "배수구트랩"
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = "https://openapi.elim.asia"

ELIMAPI_EMAIL = os.environ.get("ELIMAPI_EMAIL", "info@becorelab.kr")
ELIMAPI_PASSWORD = os.environ.get("ELIMAPI_PASSWORD", "becolab@2026!!")

SORT_OPTIONS = {
    "sales": "SALE_QTY_DESC",
    "price_low": "PRICE_ASC",
    "price_high": "PRICE_DESC",
    "retention": "RETENTION_DESC",
}

TOKEN_CACHE = Path(__file__).parent / ".elimapi_token.json"


def _post_json(url: str, body: dict, token: str = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:1000]
        return {"error": True, "status": e.code, "body": err_body}


def login() -> str:
    """Elimapi 로그인 → access_token 반환. 캐시 파일 사용."""
    if TOKEN_CACHE.exists():
        cached = json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))
        if cached.get("access_token"):
            return cached["access_token"]

    result = _post_json(f"{BASE_URL}/v1/auth/login", {
        "email": ELIMAPI_EMAIL,
        "password": ELIMAPI_PASSWORD,
    })

    if result.get("error"):
        print(f"로그인 실패: {json.dumps(result, ensure_ascii=False)}")
        return ""

    token = result.get("access_token", "")
    if token:
        TOKEN_CACHE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return token


def search_1688(keyword: str, page: int = 1, sort: str = "sales",
                size: int = 20, lang: str = "en") -> dict:
    token = login()
    if not token:
        return {"error": "Elimapi 로그인 실패 — 이메일/비밀번호 확인 필요"}

    body = {
        "q": keyword,
        "platform": "alibaba",
        "page": page,
        "size": size,
        "lang": lang,
        "sort": SORT_OPTIONS.get(sort, sort),
    }

    result = _post_json(f"{BASE_URL}/v1/products/search", body, token=token)

    if result.get("error") and result.get("status") == 401:
        TOKEN_CACHE.unlink(missing_ok=True)
        token = login()
        if token:
            result = _post_json(f"{BASE_URL}/v1/products/search", body, token=token)

    if result.get("error"):
        return {
            "error": f"검색 실패 (HTTP {result.get('status', '?')})",
            "detail": result.get("body", ""),
        }

    return {
        "success": True,
        "keyword": keyword,
        "page": page,
        "data": result,
    }


def format_results(result: dict) -> str:
    if result.get("error"):
        return f"오류: {result['error']}\n{json.dumps(result, ensure_ascii=False, indent=2)}"

    data = result.get("data", {})
    items = (data.get("items") or data.get("data") or
             data.get("results") or data.get("products") or [])
    if isinstance(data, list):
        items = data

    if not isinstance(items, list):
        return f"응답 수신 (구조 확인 필요):\n{json.dumps(data, ensure_ascii=False, indent=2)[:3000]}"

    lines = [f"1688 검색 결과: '{result['keyword']}' ({len(items)}건)\n"]
    for i, item in enumerate(items[:20], 1):
        title = item.get("title", item.get("name", ""))
        price = item.get("price", item.get("promotion_price", ""))
        seller = item.get("seller", item.get("shop", item.get("seller_name", "")))
        if isinstance(seller, dict):
            seller = seller.get("name", seller.get("shop_name", str(seller)))
        sales = item.get("sales", item.get("sale_qty", item.get("monthSold", "")))
        url = item.get("url", item.get("product_url", item.get("link", "")))
        pid = item.get("id", item.get("product_id", ""))

        lines.append(f"  {i}. {title[:70]}")
        if price:
            lines.append(f"     price: Y{price}")
        if seller:
            lines.append(f"     seller: {seller}")
        if sales:
            lines.append(f"     sales: {sales}")
        if pid:
            lines.append(f"     id: {pid}")
        if url:
            lines.append(f"     url: {url[:100]}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search_1688.py <keyword> [page] [sort]")
        print("Sort: sales, price_low, price_high, retention")
        print("Ex: python search_1688.py 배수구트랩")
        sys.exit(1)

    kw = sys.argv[1]
    pg = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    st = sys.argv[3] if len(sys.argv) > 3 else "sales"

    print(f"1688 search: '{kw}' (page={pg}, sort={st})")
    print(f"   API: Elimapi (free 200/month)")
    print()

    result = search_1688(kw, page=pg, sort=st)
    print(format_results(result))

    out_path = Path(__file__).parent / "1688_last_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRaw response saved: {out_path}")
