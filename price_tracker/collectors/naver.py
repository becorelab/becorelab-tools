"""네이버 쇼핑 수집기 — 키워드 검색 결과에서 등록 제품 매칭.

네이버는 상품 직접조회 API가 없어 '키워드 검색 → 상품명 부분일치'로 추적한다.
반환: price, review_count, ranking, url (평점/옵션은 네이버 검색으론 미제공).
"""
import importlib.util

# competitor_analyzer/collectors/naver_shopping.py 를 직접 로드(패키지명 'collectors' 충돌 회피)
_NS_PATH = "/Users/macmini_ky/ClaudeAITeam/marketing/competitor_analyzer/collectors/naver_shopping.py"
_spec = importlib.util.spec_from_file_location("ca_naver_shopping", _NS_PATH)
_ns_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ns_mod)
NaverShoppingCollector = _ns_mod.NaverShoppingCollector

_collector = None


def _get():
    global _collector
    if _collector is None:
        _collector = NaverShoppingCollector()
    return _collector


def search_keyword(keyword, count=40):
    """키워드 검색 → 상품 리스트(rank/product_name/price/review_count/url/mall_name)."""
    try:
        return _get().search(keyword, count=count) or []
    except Exception as e:
        print(f"  [naver] 검색 실패({keyword}): {e}")
        return []


def _norm(s):
    return "".join((s or "").lower().split())


def match_product(items, match_name=None, url=None):
    """검색 결과에서 등록 제품 1개를 매칭. URL 우선, 없으면 상품명 부분일치."""
    if url:
        for p in items:
            if p.get("url") and (url in p["url"] or p["url"] in url):
                return p
    if match_name:
        key = _norm(match_name)
        # 1) 완전 포함
        for p in items:
            if key and key in _norm(p.get("product_name", "")):
                return p
        # 2) 토큰 다수 일치(공백 분리 키워드 2개 이상 포함)
        toks = [t for t in (match_name or "").lower().split() if len(t) >= 2]
        if toks:
            best, best_hit = None, 0
            for p in items:
                nm = _norm(p.get("product_name", ""))
                hit = sum(1 for t in toks if _norm(t) in nm)
                if hit > best_hit:
                    best, best_hit = p, hit
            if best and best_hit >= max(2, len(toks) // 2):
                return best
    return None


def collect(product):
    """등록 제품(dict) → 스냅샷 필드. 매칭 실패 시 None."""
    items = search_keyword(product.get("keyword") or product.get("label"), count=40)
    if not items:
        return None
    hit = match_product(items, product.get("match_name"), product.get("product_url"))
    if not hit:
        return None
    return {
        "price": hit.get("price") or None,
        "review_count": hit.get("review_count") or None,
        "ranking": hit.get("rank") or None,
        "rating": None,
        "revenue_monthly": hit.get("estimated_revenue") or None,
        "sales_monthly": hit.get("purchase_count") or None,
        "options": None,
        "raw": {
            "product_name": hit.get("product_name"),
            "mall_name": hit.get("mall_name"),
            "url": hit.get("url"),
        },
    }
