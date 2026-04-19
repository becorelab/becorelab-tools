"""1688 제품 상세 조회 — Elimapi /v1/products/find"""
import json
import sys
import urllib.request
from pathlib import Path
from search_1688 import login, BASE_URL, _post_json


def find_product(product_id: str) -> dict:
    token = login()
    if not token:
        return {"error": "login failed"}

    body = {
        "id": product_id,
        "platform": "alibaba",
        "lang": "en",
    }
    return _post_json(f"{BASE_URL}/v1/products/find", body, token=token)


if __name__ == "__main__":
    pid = sys.argv[1] if len(sys.argv) > 1 else "987266748920"
    print(f"Finding product: {pid}\n")
    result = find_product(pid)

    if result.get("error"):
        print(f"Error: {json.dumps(result, ensure_ascii=False)}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2)[:5000])

    out = Path(__file__).parent / "1688_find_result.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out}")
