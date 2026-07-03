#!/usr/bin/env python3
"""
카카오 선물하기 베스트 랭킹 추적 — "잘 팔리는 선물" 포착 + 신제품 기획 빈자리 발굴
(2026-07-03 신설. track.py=재고차분 추적 / 이 파일=랭킹·주문수 기반 시장 서열)

핵심 발견 (실호출 검증 2026-07-03):
- 랭킹 API는 무인증 GET/POST로 깨끗한 JSON. 매시간 갱신(updatedAt).
- 트렌딩 탭 상품에 fomoBadge.orderCount(주문수) 노출 ⭐ — 판매량 직접 프록시(6/17 "직접지표 없음" 결론 갱신).
- navId는 required-data에서 실시간 확보(고정탭 11000/11001 섞임, 값 변동 대비).

수집 대상 (우리 향·탈취 자산과 직결되는 리빙 + 트렌딩 시장):
- 카테고리: 리빙(5)>캔들디퓨저·인센스(111)·차량용방향제(429)·생필품(115)
- 트렌딩: 위시TOP(10002)·신상(12)·단독(10003)

사용:  python3 rank_track.py [TOPN]   (기본 40)
매일 실행 → rank_snapshots/YYYY-MM-DD.json 누적. 2회차부터 순위변동·신규진입·찜Δ·주문Δ.
"""
import requests, json, os, sys, time
from datetime import datetime

BASE = "https://gift.kakao.com/a/rank/v1/gift-rank"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
H = {"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"}
REQUEST_DELAY = 0.4

# (탭종류, navId, subNavId, 표시명) — subNavId=None이면 카테고리 전체 or 트렌딩
TARGETS = [
    ("category-tab", 5, 111, "리빙>캔들디퓨저·인센스"),
    ("category-tab", 5, 429, "리빙>차량용방향제"),
    ("category-tab", 5, 115, "리빙>생필품"),
    ("trending-tab", 10002, None, "트렌딩>위시TOP"),
    ("trending-tab", 12, None, "트렌딩>신상"),
    ("trending-tab", 10003, None, "트렌딩>단독"),
]

TOPN = int(sys.argv[1]) if len(sys.argv) > 1 else 40
DIR = os.path.dirname(os.path.abspath(__file__))
SNAPDIR = os.path.join(DIR, "rank_snapshots")
os.makedirs(SNAPDIR, exist_ok=True)


def fetch_rank(tab, nav_id, sub_nav_id, size):
    body = {"navId": nav_id, "page": 0, "size": size}
    if sub_nav_id is not None:
        body["subNavId"] = sub_nav_id
    r = requests.post(f"{BASE}/ranking-tab/{tab}/search", headers=H, json=body, timeout=15)
    r.raise_for_status()
    return r.json()


def parse_product(p, rank):
    price = p.get("price") or {}
    brand = p.get("brand") or {}
    wish = p.get("wish") or {}
    fomo = p.get("fomoBadge") or {}
    rev = p.get("review") or {}
    return {
        "rank": rank,
        "id": p.get("id"),
        "name": str(p.get("name", ""))[:60],
        "brand": brand.get("name", "") if isinstance(brand, dict) else str(brand),
        "price": price.get("sellingPrice") or price.get("basicPrice"),
        "discountRate": price.get("discountRate", 0),
        "wishCount": wish.get("wishCount"),
        "orderCount": fomo.get("orderCount"),   # ⭐ 주문수(판매 프록시) — 트렌딩탭 위주로 노출
        "viewCount": fomo.get("viewCount"),
        "reviewCount": rev.get("reviewCount"),
        "stamp": p.get("stamp"),                # ON_SALE 등
        "freeDelivery": bool((p.get("displayDeliveryFee") or {}).get("free")),
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
        tabs[label] = {
            "tab": tab, "navId": nav_id, "subNavId": sub_nav_id,
            "updatedAt": data.get("updatedAt"), "rows": rows,
        }
        time.sleep(REQUEST_DELAY)
    return {"date": date_str, "topn": TOPN, "tabs": tabs}


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
    prev_tabs = prev.get("tabs", {}) if prev else {}

    path = os.path.join(SNAPDIR, f"{today}.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(snap, fp, ensure_ascii=False, indent=2)

    print(f"\n🎁 카카오 선물하기 베스트 랭킹 — {today} (TOP{TOPN})")
    for label, tab in snap["tabs"].items():
        rows = tab["rows"]
        pmap = {r["id"]: r for r in prev_tabs.get(label, {}).get("rows", [])}
        has_order = any(r["orderCount"] is not None for r in rows)
        print(f"\n■ {label}  ({tab['updatedAt']}, {len(rows)}개)"
              + ("  📦주문수有" if has_order else ""))
        print(f"  {'순위':<4}{'브랜드':<12}{'가격':>8}{'할인':>5}{'찜':>8}{'주문':>7}  변동")
        for r in rows[:12]:
            pv = pmap.get(r["id"])
            mv = "🆕신규"
            if pv:
                dr = pv["rank"] - r["rank"]
                mv = f"▲{dr}" if dr > 0 else (f"▼{-dr}" if dr < 0 else "―")
                dw = (r["wishCount"] or 0) - (pv["wishCount"] or 0)
                if dw:
                    mv += f" 찜{'+' if dw>0 else ''}{dw}"
                do = (r["orderCount"] or 0) - (pv["orderCount"] or 0)
                if do:
                    mv += f" 주문{'+' if do>0 else ''}{do}"
            br = (r["brand"] or "")[:11]
            dc = f"{r['discountRate']}%" if r["discountRate"] else ""
            oc = str(r["orderCount"]) if r["orderCount"] is not None else "-"
            print(f"  {r['rank']:<4}{br:<12}{str(r['price'] or '-'):>8}{dc:>5}"
                  f"{str(r['wishCount'] or '-'):>8}{oc:>7}  {mv}")

    tail = "첫 스냅샷 — 내일부터 순위변동·찜Δ·주문Δ 표시." if not prev else f"전일({prev['date']}) 대비 증분."
    print("\n" + tail)
    print(f"※ 주문수(orderCount)=판매 직접 프록시(트렌딩탭 노출). 찜=관심 모멘텀. 저장: {path}")


if __name__ == "__main__":
    main()
