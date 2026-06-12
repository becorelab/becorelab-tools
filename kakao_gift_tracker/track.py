#!/usr/bin/env python3
"""
카카오 선물하기 경쟁사 추적 프로토타입
- 키워드(기본: 고체 탈취제) 인기순 TOP N 상품의 재고/찜/리뷰/순위를 일별 스냅샷으로 적재
- 재고(stockQuantity) 차분 = 판매량 직접 추정 (네이버 스마트데이터 방식 이식)
- 찜 증분 = 관심 모멘텀 (보조 지표)

사용:  python3 track.py ["키워드"] [TOPN]
매일 1회 실행 → snapshots/YYYY-MM-DD.json 누적. 2회차부터 전일 대비 증분 출력.
"""
import requests, json, os, re, sys, urllib.parse
from datetime import datetime, timedelta

BASE = "https://gift.kakao.com/a"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
H = {"User-Agent": UA, "Accept": "application/json"}

KEYWORD = sys.argv[1] if len(sys.argv) > 1 else "고체 탈취제"
TOPN = int(sys.argv[2]) if len(sys.argv) > 2 else 10

DIR = os.path.dirname(os.path.abspath(__file__))
SNAPDIR = os.path.join(DIR, "snapshots")
os.makedirs(SNAPDIR, exist_ok=True)


def _find_list(o):
    if isinstance(o, list) and o and isinstance(o[0], dict):
        return o
    if isinstance(o, dict):
        for v in o.values():
            r = _find_list(v)
            if r:
                return r
    return None


def search(keyword, sort="searchPopular"):
    q = urllib.parse.quote(keyword)
    url = f"{BASE}/gift-explorer/v1/search/products?query={q}&sort={sort}"
    r = requests.get(url, headers=H, timeout=15)
    r.raise_for_status()
    return _find_list(r.json()) or []


def total_stock(pid):
    """옵션별 재고 합. 무제한 세팅(unlimitedStockQuantity:true)이면 '무제한' 반환(추적불가)."""
    try:
        r = requests.get(f"{BASE}/product-detail/v1/products/{pid}/options", headers=H, timeout=15)
        r.raise_for_status()
        flat = json.dumps(r.json())
        stocks = [int(x) for x in re.findall(r'"stockQuantity":\s*(\d+)', flat)]
        n = len(stocks)
        if n and n % 2 == 0 and stocks[: n // 2] == stocks[n // 2:]:
            stocks = stocks[: n // 2]
        unlimited = len(re.findall(r'"unlimitedStockQuantity":\s*true', flat))
        if not stocks and unlimited:
            return "무제한", unlimited  # 추적 불가 (셀러가 재고 무제한 세팅)
        return sum(stocks), len(stocks)
    except Exception:
        return None, 0


def snapshot(date_str):
    prods = search(KEYWORD, "searchPopular")[:TOPN]
    rows = []
    for rank, p in enumerate(prods, 1):
        pid = p.get("id")
        wish = (p.get("wish") or {}).get("wishCount")
        rev = (p.get("review") or {})
        seller = (p.get("moment") or {}).get("sellerName", "")
        price = p.get("price") or {}
        stock, nopt = total_stock(pid)
        rows.append({
            "rank": rank,
            "id": pid,
            "name": str(p.get("name", ""))[:50],
            "seller": seller,
            "price": price.get("sellingPrice") or price.get("basicPrice"),
            "wishCount": wish,
            "reviewCount": rev.get("reviewCount"),
            "positiveRate": rev.get("positiveReviewRate"),
            "totalStock": stock,
            "optionCount": nopt,
        })
    return {"date": date_str, "keyword": KEYWORD, "rows": rows}


def load_prev(date_str):
    """가장 최근(오늘 이전) 스냅샷 로드."""
    files = sorted(f for f in os.listdir(SNAPDIR) if f.endswith(".json") and f[:10] < date_str)
    if not files:
        return None
    with open(os.path.join(SNAPDIR, files[-1]), encoding="utf-8") as fp:
        return json.load(fp)


def main():
    today = datetime.now().strftime("%Y-%m-%d") if False else None
    # Date.now 회피: 파일 기준이 아닌 시스템 날짜 필요 → 환경 날짜 사용
    today = datetime.now().strftime("%Y-%m-%d")
    snap = snapshot(today)
    prev = load_prev(today)
    prev_map = {r["id"]: r for r in prev["rows"]} if prev else {}

    path = os.path.join(SNAPDIR, f"{today}.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(snap, fp, ensure_ascii=False, indent=2)

    print(f"\n📡 카카오 선물하기 추적 — '{KEYWORD}' TOP{TOPN}  ({today})")
    print(f"{'순위':<4}{'상품(브랜드)':<30}{'가격':>8}{'찜':>8}{'리뷰':>6}{'총재고':>10}{'재고Δ':>8}{'찜Δ':>7}")
    print("-" * 84)
    for r in snap["rows"]:
        pv = prev_map.get(r["id"])
        ds = de = ""
        if pv:
            a, b = pv.get("totalStock"), r["totalStock"]
            if isinstance(a, int) and isinstance(b, int):
                d = a - b  # 재고 감소 = 판매 추정
                ds = f"▼{d}" if d > 0 else (f"+{-d}" if d < 0 else "0")
            if pv.get("wishCount") is not None and r["wishCount"] is not None:
                w = r["wishCount"] - pv["wishCount"]
                de = f"+{w}" if w else "0"
        nm = (r["seller"] or "")[:12]
        ts = r["totalStock"]
        stock = f"{ts:,}" if isinstance(ts, int) else (ts if ts else "N/A")
        print(f"{r['rank']:<4}{nm:<30}{str(r['price'] or '-'):>8}{str(r['wishCount']):>8}{str(r['reviewCount']):>6}{stock:>10}{ds:>8}{de:>7}")

    if not prev:
        print("\n첫 스냅샷 — 내일부터 재고Δ(판매 추정)·찜Δ가 표시됩니다.")
    else:
        print(f"\n전일 스냅샷({prev['date']}) 대비 증분 표시 완료.")
    print(f"저장: {path}")


if __name__ == "__main__":
    main()
