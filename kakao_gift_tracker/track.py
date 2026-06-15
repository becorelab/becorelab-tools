#!/usr/bin/env python3
"""
카카오 선물하기 경쟁사 추적 (고도화)
- 다중 키워드 × TOP N 상품의 재고/찜/리뷰/순위 일별 스냅샷
- 재고(stockQuantity) 차분 = 판매 추정. 단 "재고 신뢰 등급"으로 추정 가능 상품만 코어로.
- 찜/리뷰 증분 = 관심·구매 모멘텀(보조). 재고 증가는 '재입고(▲보충)'로 마킹(판매 누락 구간).

사용:  python3 track.py ["키워드1,키워드2,..."] [TOPN]
       인자 없으면 DEFAULT_KEYWORDS 전체 추적.
매일 1회 실행 → snapshots/YYYY-MM-DD.json 누적. 2회차부터 전일 대비 증분.
"""
import requests, json, os, re, sys, time, urllib.parse
from datetime import datetime

BASE = "https://gift.kakao.com/a"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
H = {"User-Agent": UA, "Accept": "application/json"}

# 에어밤 = 고체 탈취제. 직접 경쟁 시장만 집중 추적(인접 카테고리는 노이즈라 제외).
# 신뢰 재고 상품이 부족하면 인접 키워드(섬유 탈취제 등) 추가 고려.
DEFAULT_KEYWORDS = ["고체 탈취제"]
REQUEST_DELAY = 0.3  # API 호출 간 간격(차단 완화)

_arg_kw = sys.argv[1] if len(sys.argv) > 1 else ""
KEYWORDS = [k.strip() for k in _arg_kw.split(",") if k.strip()] or DEFAULT_KEYWORDS
TOPN = int(sys.argv[2]) if len(sys.argv) > 2 else 30

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
    """옵션별 재고 합. 무제한이면 '무제한'(추적불가). 실패 None."""
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
            return "무제한", unlimited
        return sum(stocks), len(stocks)
    except Exception:
        return None, 0


def stock_grade(stock):
    """재고 신뢰 등급 — 판매 추정에 쓸 수 있는지."""
    if stock == "무제한":
        return "추적불가·무제한"
    if stock is None:
        return "추적불가·미상"
    if isinstance(stock, int):
        return "추적불가·품절(0)" if stock == 0 else "신뢰·유한재고"
    return "추적불가·미상"


def snapshot(date_str):
    """키워드별 TOP N 수집 → 상품 id 기준 중복 제거(최고 순위·등장 키워드 보존)."""
    seen, order = {}, []
    for kw in KEYWORDS:
        try:
            prods = search(kw, "searchPopular")[:TOPN]
        except Exception as e:
            print(f"  ⚠️ '{kw}' 검색 실패: {e}")
            continue
        for rank, p in enumerate(prods, 1):
            pid = p.get("id")
            if not pid:
                continue
            if pid in seen:  # 다른 키워드에서 이미 본 상품 → 키워드만 추가, 재고 재조회 안 함
                if kw not in seen[pid]["keywords"]:
                    seen[pid]["keywords"].append(kw)
                seen[pid]["bestRank"] = min(seen[pid]["bestRank"], rank)
                continue
            stock, nopt = total_stock(pid)
            time.sleep(REQUEST_DELAY)
            rev = p.get("review") or {}
            price = p.get("price") or {}
            seen[pid] = {
                "id": pid,
                "name": str(p.get("name", ""))[:50],
                "seller": (p.get("moment") or {}).get("sellerName", ""),
                "keywords": [kw],
                "bestRank": rank,
                "price": price.get("sellingPrice") or price.get("basicPrice"),
                "wishCount": (p.get("wish") or {}).get("wishCount"),
                "reviewCount": rev.get("reviewCount"),
                "positiveRate": rev.get("positiveReviewRate"),
                "totalStock": stock,
                "optionCount": nopt,
                "stockGrade": stock_grade(stock),
            }
            order.append(pid)
    rows = sorted((seen[pid] for pid in order), key=lambda r: r["bestRank"])
    return {"date": date_str, "keywords": KEYWORDS, "topn": TOPN, "rows": rows}


def load_prev(date_str):
    files = sorted(f for f in os.listdir(SNAPDIR) if f.endswith(".json") and f[:10] < date_str)
    if not files:
        return None
    with open(os.path.join(SNAPDIR, files[-1]), encoding="utf-8") as fp:
        return json.load(fp)


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    snap = snapshot(today)
    prev = load_prev(today)
    prev_map = {r["id"]: r for r in prev["rows"]} if prev else {}

    path = os.path.join(SNAPDIR, f"{today}.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(snap, fp, ensure_ascii=False, indent=2)

    n_core = sum(1 for r in snap["rows"] if r["stockGrade"].startswith("신뢰"))
    print(f"\n📡 카카오 선물하기 추적 — {KEYWORDS} TOP{TOPN}  ({today})")
    print(f"   상품 {len(snap['rows'])}개 · 재고추정 신뢰 {n_core}개 (나머지는 찜·리뷰로 추세 판단)")
    print(f"{'순위':<4}{'브랜드':<13}{'가격':>8}{'찜':>7}{'리뷰':>6}{'총재고':>10}{'판매추정':>10}{'찜Δ':>6}  등급")
    print("-" * 102)
    for r in snap["rows"]:
        pv = prev_map.get(r["id"])
        sale_est, de = "", ""
        if pv:
            a, b = pv.get("totalStock"), r["totalStock"]
            if isinstance(a, int) and isinstance(b, int):
                d = a - b
                if d > 0:
                    sale_est = f"{d}↓판매"
                elif d < 0:
                    sale_est = f"+{-d}▲보충"  # 재고 증가 = 재입고(그 사이 판매는 누락)
                else:
                    sale_est = "0"
            if pv.get("wishCount") is not None and r["wishCount"] is not None:
                w = r["wishCount"] - pv["wishCount"]
                de = f"+{w}" if w else "0"
        nm = (r["seller"] or "")[:12]
        ts = r["totalStock"]
        stock = f"{ts:,}" if isinstance(ts, int) else (ts or "N/A")
        print(f"{r['bestRank']:<4}{nm:<13}{str(r['price'] or '-'):>8}{str(r['wishCount']):>7}{str(r['reviewCount']):>6}{stock:>10}{sale_est:>10}{de:>6}  {r['stockGrade']}")

    if not prev:
        print("\n첫 스냅샷(고도화) — 내일부터 판매추정·찜Δ 표시.")
    else:
        print(f"\n전일({prev['date']}) 대비 증분. '신뢰·유한재고' 등급만 판매추정 신뢰도가 높아요.")
    print(f"저장: {path}")


if __name__ == "__main__":
    main()
