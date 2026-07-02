"""쿠팡 수집기 — 소싱콕(localhost:8090) 스캔 데이터 활용 (Akamai 우회).

쿠팡은 직접 크롤링 시 Akamai에 막히므로, 소싱콕이 브라우저 세션으로 긁어둔
스캔 데이터를 재활용한다.
  - 가격/리뷰수/순위/월매출/판매량  → /api/scan/<id> 의 products[]
  - 평점/옵션구성                    → /api/reviews/download (productId, on-demand)
"""
import os
import re
import json
import requests

API = "http://localhost:8090"
REVIEW_CACHE = "/Users/macmini_ky/ClaudeAITeam/sourcing/review_output"


def _pid(url):
    if not url:
        return ""
    m = re.search(r"/products/(\d+)", url)
    return m.group(1) if m else ""


def list_scans():
    try:
        r = requests.get(f"{API}/api/scans", timeout=15)
        return r.json().get("scans", [])
    except Exception as e:
        print(f"  [coupang] 스캔목록 실패: {e}")
        return []


def latest_scan_id(keyword, max_age_days=14):
    """키워드와 일치하는 가장 최근 스캔 id.

    신선도 가드(2026-07-02): 윙 로그인 고장으로 새 스캔이 안 생기던 6주간
    5/20 스캔을 매일 재사용하며 '성공'으로 위장했음 → 오래된 스캔은 실패로 처리해 드러냄.
    """
    from datetime import datetime, timedelta
    scans = [s for s in list_scans() if (s.get("keyword") or "") == keyword]
    if not scans:
        return None
    scans.sort(key=lambda s: s.get("scanned_at", ""), reverse=True)
    newest = scans[0]
    scanned_at = str(newest.get("scanned_at", ""))[:10]
    try:
        if scanned_at and datetime.strptime(scanned_at, "%Y-%m-%d") < datetime.now() - timedelta(days=max_age_days):
            print(f"  [coupang] '{keyword}' 최신 스캔이 {scanned_at}로 {max_age_days}일 초과 — 동결 데이터 재사용 거부 (새 스캔 필요)")
            return None
    except ValueError:
        pass
    return newest["id"]


def scan_products(scan_id):
    try:
        r = requests.get(f"{API}/api/scan/{scan_id}", timeout=30)
        return r.json().get("products", [])
    except Exception as e:
        print(f"  [coupang] 스캔조회 실패({scan_id}): {e}")
        return []


def _norm(s):
    return "".join((s or "").lower().split())


def match_product(products, product_id=None, match_name=None, url=None):
    """스캔 상품 목록에서 등록 제품 매칭. productId 우선 → URL → 상품명."""
    pid = product_id or _pid(url)
    if pid:
        for p in products:
            if _pid(p.get("product_url", "")) == pid:
                return p
    if url:
        for p in products:
            if p.get("product_url") and url.split("?")[0] in p["product_url"]:
                return p
    if match_name:
        key = _norm(match_name)
        for p in products:
            if key and key in _norm(p.get("product_name", "")):
                return p
    return None


def cached_reviews(product_id, keyword):
    """이미 수집해 둔 리뷰 캐시(review_output/<keyword>/<pid>.json) 읽기 — 즉시·안정."""
    if not product_id:
        return None
    # 1) 키워드 폴더 직접
    cands = []
    if keyword:
        cands.append(os.path.join(REVIEW_CACHE, keyword, f"{product_id}.json"))
    # 2) 전체 폴더 스캔(키워드 폴더명이 달라도)
    try:
        for d in os.listdir(REVIEW_CACHE):
            cands.append(os.path.join(REVIEW_CACHE, d, f"{product_id}.json"))
    except Exception:
        pass
    for path in cands:
        if os.path.exists(path):
            try:
                return json.load(open(path, encoding="utf-8"))
            except Exception:
                continue
    return None


def fetch_reviews(url_or_id, max_reviews=300, timeout=600):
    """소싱콕 리뷰 다운로드 → 평점요약 + 옵션 구성 (on-demand, 무거움). 캐시 없을 때만."""
    try:
        r = requests.post(f"{API}/api/reviews/download",
                          json={"url": url_or_id, "max_reviews": max_reviews},
                          timeout=timeout)
        return r.json()
    except Exception as e:
        print(f"  [coupang] 리뷰 다운로드 실패: {e}")
        return None


def _clean_option(opt):
    """'스너글...본품, 470ml, 3개' → '470ml · 3개' (용량/개수만 추출)."""
    parts = [p.strip() for p in (opt or "").split(",")]
    keep = [p for p in parts
            if re.search(r"\d", p) and re.search(r"(ml|L|g|kg|개|매|입|팩|병|회|장)", p, re.I)]
    return " · ".join(keep) if keep else (opt or "").strip()[:30]


def option_mix_from_reviews(reviews):
    """리뷰의 option 필드 → 구성별 점유율(%) 집계 (용량/개수로 정제)."""
    from collections import Counter
    cnt = Counter()
    for rv in reviews or []:
        opt = _clean_option(rv.get("option"))
        if opt:
            cnt[opt] += 1
    total = sum(cnt.values())
    if not total:
        return None
    return [{"name": k, "share": round(v / total * 100, 1), "count": v}
            for k, v in cnt.most_common(12)]


def _rating_avg(summary):
    if not summary:
        return None
    return (summary.get("averageRating") or summary.get("average")
            or summary.get("avg") or summary.get("rating"))


def collect(product, with_reviews=False):
    """등록 제품(dict) → 스냅샷 필드. 매칭 실패 시 None.

    with_reviews=True 면 평점/옵션까지 리뷰 다운로드로 보강(느림).
    """
    kw = product.get("keyword") or product.get("label")
    sid = latest_scan_id(kw)
    if not sid:
        return None
    products = scan_products(sid)
    hit = match_product(products, product.get("product_id"),
                        product.get("match_name"), product.get("product_url"))
    if not hit:
        return None

    out = {
        "price": hit.get("price") or None,
        "review_count": hit.get("review_count") or None,
        "ranking": hit.get("ranking") or None,
        "rating": hit.get("rating"),
        "revenue_monthly": hit.get("revenue_monthly") or None,
        "sales_monthly": hit.get("sales_monthly") or None,
        "options": None,
        "raw": {
            "product_name": hit.get("product_name"),
            "brand": hit.get("brand"),
            "url": hit.get("product_url"),
            "scan_id": sid,
        },
    }

    if with_reviews:
        pid = product.get("product_id") or _pid(product.get("product_url") or hit.get("product_url", ""))
        # 1) 캐시 우선(즉시) → 2) 없으면 소싱콕 다운로드(느림)
        rv = cached_reviews(pid, kw)
        src = "캐시"
        if not rv:
            rv = fetch_reviews(product.get("product_url") or hit.get("product_url"))
            src = "다운로드"
        if rv:
            summ = rv.get("rating_summary") or {}
            out["rating"] = _rating_avg(summ) or out["rating"]
            out["review_count"] = (rv.get("total_count") or rv.get("review_count_listed")
                                   or out["review_count"])
            out["options"] = option_mix_from_reviews(rv.get("reviews"))
            n = len(rv.get("reviews") or [])
            print(f"  [coupang] 리뷰 {src} {n}건 → 평점 {out['rating']} / 옵션 {len(out['options'] or [])}종")
    return out
