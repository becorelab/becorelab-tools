#!/usr/bin/env python3
"""iLBiA 자사 제품 리뷰 수집 파이프라인 — 상품ID 직접 지정"""

import json, os, time, requests, sys

API = "http://localhost:8090"
BASE_DIR = "/Users/macmini_ky/ClaudeAITeam/sourcing/review_output"

ILBIA_PRODUCTS = {
    "일비아 건조기시트": [
        {"pid": "6513489331", "name": "일비아 일반용 건조기 퍼퓸 시트 섬유유연제 코튼 블루 본품", "review_count": 6396},
        {"pid": "8830156709", "name": "일비아 건조기 퍼퓸 시트 섬유유연제 바이올렛 머스크 본품", "review_count": 457},
        {"pid": "6513479888", "name": "일비아 일반용 건조기 퍼퓸 시트 베이비 크림 향 본품", "review_count": 1965},
    ],
    "일비아 식기세척기 세제": [
        {"pid": "6930200724", "name": "일비아 하트 1종 식기세척기 세제 60개입", "review_count": 401},
        {"pid": "7759359124", "name": "일비아 올인원 식기세척기 세제 타블릿", "review_count": 287},
        {"pid": "9317848392", "name": "일비아 하트 식기세척기 세제 스페셜 에디션 패키지", "review_count": 2},
    ],
    "일비아 섬유탈취제": [
        {"pid": "8983381922", "name": "일비아 스타일링 섬유탈취제 코튼 블루 본품", "review_count": 510},
    ],
    "일비아 캡슐세제": [
        {"pid": "7704584177", "name": "일비아 고농축 캡슐세제 버블코튼향 액체 세탁세제", "review_count": 228},
    ],
    "일비아 캡슐표백제": [
        {"pid": "9454938820", "name": "일비아 과탄산소다 화이트버블 스팀 캡슐 표백제", "review_count": 169},
    ],
    "일비아 얼룩제거제": [
        {"pid": "7843041173", "name": "일비아 티트리 딥클린 얼룩제거제", "review_count": 160},
    ],
}

def collect_reviews(keyword, products):
    output_dir = os.path.join(BASE_DIR, keyword)
    os.makedirs(output_dir, exist_ok=True)

    total_collected = 0
    results = []

    for i, p in enumerate(products):
        pid = p["pid"]
        name = p["name"][:40]
        rc = p["review_count"]
        out_file = os.path.join(output_dir, f"{pid}.json")

        if os.path.exists(out_file):
            with open(out_file) as f:
                existing = json.load(f)
            cnt = existing.get("collected_count", len(existing.get("reviews", [])))
            if cnt > 0:
                print(f"  [{i+1}/{len(products)}] {name} — 이미 수집됨 ({cnt}건)")
                total_collected += cnt
                results.append({"pid": pid, "name": p["name"], "collected": cnt})
                continue

        if rc == 0:
            print(f"  [{i+1}/{len(products)}] {name} — 리뷰 없음, 스킵")
            results.append({"pid": pid, "name": p["name"], "collected": 0})
            continue

        print(f"  [{i+1}/{len(products)}] {name} (리뷰 {rc}건)")

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

        results.append({"pid": pid, "name": p["name"], "collected": collected})
        if i < len(products) - 1:
            time.sleep(1)

    summary = {
        "keyword": keyword,
        "total_products": len(products),
        "total_collected": total_collected,
        "products": results,
    }
    with open(os.path.join(output_dir, "_summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return total_collected, results

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None

    for keyword, products in ILBIA_PRODUCTS.items():
        if target and keyword != target:
            continue

        print(f"\n{'='*60}")
        print(f"  [{keyword}] 리뷰 수집 ({len(products)}개 상품)")
        print(f"{'='*60}\n")

        collected, results = collect_reviews(keyword, products)
        print(f"\n  ✅ [{keyword}] 완료! 총 {collected}건 수집\n")

    print("\n=== iLBiA 전체 수집 완료 ===")

if __name__ == "__main__":
    main()
