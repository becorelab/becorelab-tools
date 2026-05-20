#!/usr/bin/env python3
"""6개 카테고리 전체 리뷰 수집 파이프라인"""

import json, os, time, requests, sys

API = "http://localhost:8090"
BASE_DIR = "/Users/macmini_ky/ClaudeAITeam/sourcing/review_output"

KEYWORDS = {
    "캡슐표백제": {"scan_id": 6025},
    "건조기시트": {"scan_id": 6032},
    "얼룩제거제": {"scan_id": 6009},
    "식기세척기 세제": {"scan_id": 6034},
    "캡슐세제": {"scan_id": 6035},
    "섬유탈취제": {"scan_id": 6036},
}

def get_products(scan_id):
    """스캔에서 상품 목록 가져오기"""
    r = requests.get(f"{API}/api/scan/{scan_id}", timeout=30)
    data = r.json()
    products = data.get("products", [])
    result = []
    for p in products:
        url = p.get("product_url", "")
        if not url:
            continue
        pid = url.split("/products/")[1].split("?")[0] if "/products/" in url else ""
        if not pid:
            continue
        result.append({
            "pid": pid,
            "name": p.get("product_name", ""),
            "review_count": p.get("review_count", 0),
            "ranking": p.get("ranking", 0),
            "url": url,
        })
    result.sort(key=lambda x: x["ranking"])
    return result[:40]

def collect_reviews(keyword, scan_id):
    """한 카테고리의 전체 리뷰 수집"""
    output_dir = os.path.join(BASE_DIR, keyword)
    os.makedirs(output_dir, exist_ok=True)

    products = get_products(scan_id)
    if not products:
        print(f"  ⚠️ 상품 목록이 비어있음 (scan #{scan_id})")
        return 0, []

    print(f"  → {len(products)}개 상품 리뷰 수집 시작\n")
    total_collected = 0
    results = []

    for i, p in enumerate(products):
        pid = p["pid"]
        name = p["name"][:35]
        rc = p["review_count"]
        out_file = os.path.join(output_dir, f"{pid}.json")

        if os.path.exists(out_file):
            with open(out_file) as f:
                existing = json.load(f)
            cnt = existing.get("collected_count", len(existing.get("reviews", [])))
            if cnt > 0:
                print(f"  [{i+1}/{len(products)}] #{p['ranking']} {name} — 이미 수집됨 ({cnt}건)")
                total_collected += cnt
                results.append({"ranking": p["ranking"], "pid": pid, "name": p["name"], "collected": cnt})
                continue

        print(f"  [{i+1}/{len(products)}] #{p['ranking']} {name} (리뷰 {rc}건)")

        try:
            url = f"https://www.coupang.com/vp/products/{pid}"
            r = requests.post(
                f"{API}/api/reviews/download",
                json={"url": url, "max_reviews": 9999},
                timeout=600,
            )
            data = r.json()
            result_data = data.get("data", data)
            reviews = result_data.get("reviews", [])
            collected = len(reviews)

            if collected > 0:
                save_data = {
                    "product_id": pid,
                    "product_title": p["name"],
                    "review_count_listed": rc,
                    "collected_count": collected,
                    "rating_summary": result_data.get("rating_summary", {}),
                    "reviews": reviews,
                }
                with open(out_file, "w") as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=1)

                total_collected += collected
                print(f"    → {collected}건 수집 (누적 {total_collected}건)")
            else:
                print(f"    → 수집 실패 또는 리뷰 없음")
                collected = 0

        except Exception as e:
            print(f"    → 예외: {e}")
            collected = 0

        results.append({"ranking": p["ranking"], "pid": pid, "name": p["name"], "collected": collected})
        if i < len(products) - 1:
            time.sleep(1)

    summary = {
        "keyword": keyword,
        "scan_id": scan_id,
        "total_products": len(products),
        "total_collected": total_collected,
        "products": sorted(results, key=lambda x: x["ranking"]),
    }
    with open(os.path.join(output_dir, "_summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return total_collected, results

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None

    for keyword, info in KEYWORDS.items():
        if target and keyword != target:
            continue

        print(f"\n{'='*60}")
        print(f"  [{keyword}] 리뷰 수집")
        print(f"{'='*60}\n")

        scan_id = info["scan_id"]
        collected, results = collect_reviews(keyword, scan_id)
        print(f"\n  ✅ [{keyword}] 완료! 총 {collected}건 수집\n")

    print("\n=== 전체 완료 ===")

if __name__ == "__main__":
    main()
