#!/usr/bin/env python3
"""고체 탈취제 40개 상품 전체 리뷰 수집 (Wing 브라우저 사용)"""

import json, os, time, sys, requests

API = "http://localhost:8090"
OUTPUT_DIR = "/Users/macmini_ky/ClaudeAITeam/sourcing/review_output/고체탈취제"
SCAN_ID = 6026

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_products():
    r = requests.get(f"{API}/api/scan/{SCAN_ID}")
    data = r.json()
    products = []
    for p in data["products"]:
        url = p["product_url"]
        pid = url.split("/products/")[1].split("?")[0]
        products.append({
            "pid": pid,
            "name": p["product_name"],
            "review_count": p.get("review_count", 0),
            "ranking": p["ranking"],
            "url": url,
        })
    products.sort(key=lambda x: x["review_count"])
    return products

def collect_one(product):
    pid = product["pid"]
    out_file = os.path.join(OUTPUT_DIR, f"{pid}.json")

    if os.path.exists(out_file):
        with open(out_file) as f:
            existing = json.load(f)
        cnt = existing.get("collected_count", len(existing.get("reviews", [])))
        if cnt > 0:
            print(f"  → 이미 수집됨 ({cnt}건), 스킵")
            return cnt

    url = f"https://www.coupang.com/vp/products/{pid}"
    try:
        r = requests.post(
            f"{API}/api/reviews/download",
            json={"url": url, "max_reviews": 9999},
            timeout=600,
        )
        data = r.json()
        if not data.get("success") and not data.get("data"):
            print(f"  → 에러: {data.get('error', 'unknown')}")
            return 0

        result = data.get("data", data)
        reviews = result.get("reviews", [])
        collected = len(reviews)

        save_data = {
            "product_id": pid,
            "product_title": product["name"],
            "review_count_listed": product["review_count"],
            "collected_count": collected,
            "rating_summary": result.get("rating_summary", {}),
            "reviews": reviews,
        }

        with open(out_file, "w") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=1)

        return collected

    except Exception as e:
        print(f"  → 예외: {e}")
        return 0

def main():
    products = get_products()
    print(f"=== 고체 탈취제 리뷰 수집 시작 ({len(products)}개 상품) ===\n")

    total_collected = 0
    for i, p in enumerate(products):
        print(f"[{i+1}/{len(products)}] #{p['ranking']} {p['name'][:35]} (리뷰 {p['review_count']}건)")
        collected = collect_one(p)
        total_collected += collected
        print(f"  → 수집: {collected}건 (누적 {total_collected}건)")

        if i < len(products) - 1:
            time.sleep(1)

    print(f"\n=== 완료! 총 {total_collected}건 수집 ===")

    summary = {"total_products": len(products), "total_collected": total_collected, "products": []}
    for p in sorted(products, key=lambda x: x["ranking"]):
        out_file = os.path.join(OUTPUT_DIR, f"{p['pid']}.json")
        cnt = 0
        if os.path.exists(out_file):
            with open(out_file) as f:
                d = json.load(f)
            cnt = d.get("collected_count", 0)
        summary["products"].append({"ranking": p["ranking"], "pid": p["pid"], "name": p["name"], "listed": p["review_count"], "collected": cnt})

    with open(os.path.join(OUTPUT_DIR, "_summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
