#!/usr/bin/env python3
"""
카카오 선물하기 베스트 랭킹 추적 — "잘 팔리는 선물" 포착 + 신제품 기획 인사이트
(2026-07-03 신설·개편. track.py=재고차분 추적 / 이 파일=랭킹·판매신호 기반 시장 서열)

═══════════════════════════════════════════════════════════════════════
■ 다음 개발자(오퍼스 등)를 위한 맥락 — 이거 먼저 읽으세요
═══════════════════════════════════════════════════════════════════════
목적: 카카오 선물하기 베스트 랭킹을 매일 수집·누적해서 "무슨 제품이 잘 팔리나 →
      비코어랩이 만들 신제품 빈자리"를 도출한다. ERP "선물 트렌드" 탭에서 직원과 공유.

판매량 측정의 진실 (실호출 검증 완료):
- 카카오는 '주문수(orderCount)'를 카테고리 탭에 안 준다. 트렌딩 탭 일부 상품에만
  fomoBadge.orderCount로 노출(마케팅 배지). → 전체 판매지표로 못 씀.
- 그래서 판매 신호를 다중으로 잡는다 (정확도순):
  ① 리뷰 증분(reviewTotal Δ) — 실제 산 사람이 남김. 주문수 대체 최선. 상세 API 필요.
  ② 찜 증분(wishCount Δ) — 관심(안 사도 찜 가능). 표본 큼.
  ③ 순위 변동(rank Δ) — 종합 결과.
  ④ 주문수(orderCount) — 트렌딩 일부 보너스.
- 절대량 아닌 '증분 추세'로 봐야. 에어밤(자사 고체탈취제 7/13 런칭) 카카오 판매 후
  우리 실판매(판매자센터)↔리뷰증분 캘리브레이션하면 경쟁사 판매량 추정 가능.

데이터 흐름: 이 스크립트 → rank_snapshots/YYYY-MM-DD.json → ERP app.py /api/kakao/rank
             → static/js/app.js loadKakao() 카드 렌더 + 인사이트 탭.
크론: run_tracking.sh(track.py + 이 파일) → launchd com.becorelab.kakao-gift-tracker 매일 9:50.

수집 카테고리(대표님 확정 2026-07-03): 리빙 전체 12개 + 유아동 물티슈 + 트렌딩 3개.
  → 향(캔들디퓨저)에 한정 안 함. 비코어랩=생활·리빙(세제/생필품) 브랜드라 리빙 전체가 본진.
navId는 required-data(GET)에서 실시간 확인 가능. 아래 TARGETS는 2026-07-03 확인값.
═══════════════════════════════════════════════════════════════════════

사용:  python3 rank_track.py [TOPN]   (기본 40)
"""
import requests, json, os, sys, time
from datetime import datetime

BASE = "https://gift.kakao.com/a"
RANK = f"{BASE}/rank/v1/gift-rank"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
H = {"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"}
REQUEST_DELAY = 0.35        # API 간격(차단 완화)
REVIEW_DETAIL_TOPN = 20     # 리뷰 증분용 상세 호출은 각 탭 상위 N개만(부하 제한). 카드도 상위 위주.

# (탭종류, navId, subNavId, 표시명). subNavId=None이면 트렌딩(카테고리 하위 아님).
# 리빙(navId 5) 전체 하위 + 유아동(3) 물티슈 + 트렌딩. required-data에서 갱신 가능.
TARGETS = [
    ("category-tab", 5, 115, "리빙>생필품"),          # ⭐ 세제·청소 = 자사 주력
    ("category-tab", 5, 110, "리빙>주방·수입주방"),      # 식기세척기세제
    ("category-tab", 5, 116, "리빙>수납·생활"),
    ("category-tab", 5, 185, "리빙>침구·패브릭"),        # 건조기시트·섬유
    ("category-tab", 5, 111, "리빙>캔들디퓨저·인센스"),   # 섬유탈취제·향
    ("category-tab", 5, 429, "리빙>차량용방향제"),        # 탈취
    ("category-tab", 5, 114, "리빙>인테리어"),
    ("category-tab", 5, 112, "리빙>가구·DIY"),
    ("category-tab", 5, 113, "리빙>조명·무드등"),
    ("category-tab", 5, 109, "리빙>식물·꽃배달"),
    ("category-tab", 5, 286, "리빙>문구·취미"),
    ("category-tab", 5, 329, "리빙>팬시·캐릭터"),
    ("category-tab", 3, 142, "유아동>기저귀·물티슈"),     # 생활소모품(간 보기 — 대표님 2026-07-03)
    ("trending-tab", 10002, None, "트렌딩>위시TOP"),
    ("trending-tab", 12, None, "트렌딩>신상"),
    ("trending-tab", 10003, None, "트렌딩>단독"),
]

HOURLY = "--hourly" in sys.argv    # 시간대 실측 모드: 리뷰상세 생략(랭킹만 ~10초) + 파일명에 시각(HHMM)
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
TOPN = int(_args[0]) if _args else 40
if HOURLY:
    REVIEW_DETAIL_TOPN = 0         # 리뷰는 구매 며칠 뒤 작성 → 시간단위론 안 변함. 시간대 측정엔 찜·주문수 증분만.
DIR = os.path.dirname(os.path.abspath(__file__))
SNAPDIR = os.path.join(DIR, "rank_snapshots", "hourly") if HOURLY else os.path.join(DIR, "rank_snapshots")
os.makedirs(SNAPDIR, exist_ok=True)

_review_cache = {}  # pid → reviewTotal (같은 상품 여러 탭 등장 시 상세 1회만 호출)


def fetch_rank(tab, nav_id, sub_nav_id, size):
    body = {"navId": nav_id, "page": 0, "size": size}
    if sub_nav_id is not None:
        body["subNavId"] = sub_nav_id
    r = requests.post(f"{RANK}/ranking-tab/{tab}/search", headers=H, json=body, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_review_total(pid):
    """상품 상세에서 리뷰 총 개수. 리뷰=실구매자 작성이라 판매 프록시(주문수 대체).
    실패해도 랭킹 수집은 계속돼야 하므로 None 반환하고 넘어감(best-effort)."""
    if pid in _review_cache:
        return _review_cache[pid]
    val = None
    try:
        r = requests.get(f"{BASE}/product-detail/v3/products/{pid}", headers=H, timeout=12)
        if r.ok:
            val = (r.json().get("review") or {}).get("totalCount")
    except Exception:
        pass
    _review_cache[pid] = val
    time.sleep(REQUEST_DELAY)
    return val


def parse_product(p, rank):
    price = p.get("price") or {}
    brand = p.get("brand") or {}
    wish = p.get("wish") or {}
    fomo = p.get("fomoBadge") or {}
    return {
        "rank": rank,
        "id": p.get("id"),
        "name": str(p.get("name", ""))[:60],
        "brand": brand.get("name", "") if isinstance(brand, dict) else str(brand),
        "price": price.get("sellingPrice") or price.get("basicPrice"),
        "discountRate": price.get("discountRate", 0),
        "wishCount": wish.get("wishCount"),
        "orderCount": fomo.get("orderCount"),   # 트렌딩 일부만
        "reviewTotal": None,                    # 아래 상세 호출로 채움(상위 N개)
        "stamp": p.get("stamp"),
        "freeDelivery": bool((p.get("displayDeliveryFee") or {}).get("free")),
        "imageUrl": (p.get("image") or {}).get("imageUrl"),
        "productUrl": f"https://gift.kakao.com/product/{p.get('productId') or p.get('id')}",
    }


def snapshot(date_str):
    tabs = {}
    for tab, nav_id, sub_nav_id, label in TARGETS:
        try:
            data = fetch_rank(tab, nav_id, sub_nav_id, TOPN)
        except Exception as e:
            print(f"  ⚠️ '{label}' 수집 실패: {e}")
            continue
        rows = [parse_product(p, i) for i, p in enumerate(data.get("products", []), 1)]
        # 리뷰 증분용 상세: 각 탭 상위 REVIEW_DETAIL_TOPN개만(부하 제한, 캐시로 중복 방지)
        for r in rows[:REVIEW_DETAIL_TOPN]:
            if r["id"]:
                r["reviewTotal"] = fetch_review_total(r["id"])
        tabs[label] = {
            "tab": tab, "navId": nav_id, "subNavId": sub_nav_id,
            "updatedAt": data.get("updatedAt"), "rows": rows,
        }
        time.sleep(REQUEST_DELAY)
        print(f"  ✓ {label}: {len(rows)}개")
    return {"date": date_str, "topn": TOPN, "reviewTopn": REVIEW_DETAIL_TOPN, "tabs": tabs}


def load_prev(cur_key):
    # cur_key: daily=YYYY-MM-DD, hourly=YYYY-MM-DD_HHMM. 파일명(확장자 제외)이 더 이른 것 중 최신 = 직전 스냅샷.
    files = sorted(f for f in os.listdir(SNAPDIR) if f.endswith(".json") and f[:-5] < cur_key)
    if not files:
        return None
    with open(os.path.join(SNAPDIR, files[-1]), encoding="utf-8") as fp:
        return json.load(fp)


def main():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    stamp = now.strftime("%Y-%m-%d_%H%M") if HOURLY else today
    mode = "시간대 실측(리뷰생략)" if HOURLY else "일일(리뷰포함)"
    print(f"\n🎁 카카오 선물하기 랭킹 수집 — {stamp} [{mode}] (TOP{TOPN}, {len(TARGETS)}개 탭)")
    snap = snapshot(stamp)
    prev = load_prev(stamp)
    prev_tabs = prev.get("tabs", {}) if prev else {}

    path = os.path.join(SNAPDIR, f"{stamp}.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(snap, fp, ensure_ascii=False, indent=2)

    # 요약 출력 (판매신호 상위)
    print(f"\n📊 수집 완료: {len(snap['tabs'])}개 탭")
    for label, tab in snap["tabs"].items():
        rows = tab["rows"]
        pmap = {r["id"]: r for r in prev_tabs.get(label, {}).get("rows", [])}
        top = rows[0] if rows else None
        if not top:
            continue
        extra = ""
        if not prev:
            extra = " (첫 수집)"
        print(f"  {label:<22} 1위 {top['brand']:<12} 찜{top['wishCount']:>7}{extra}")

    tail = "첫 스냅샷 — 내일부터 순위·찜·리뷰 증분 표시." if not prev else f"전일({prev['date']}) 대비 증분 계산 가능."
    print("\n" + tail)
    print(f"※ 판매신호=리뷰증분(실구매)>찜증분(관심)>순위변동. 주문수는 트렌딩 일부. 저장: {path}")


if __name__ == "__main__":
    main()
