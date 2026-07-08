#!/usr/bin/env python3
"""
카카오 선물하기 — 시간대별 트래픽 실측 분석
(2026-07-08 신설. rank_track.py --hourly 스냅샷을 시간구간별 증분으로 집계)

목적: "언제 사람이 몰리나?"를 우리 리빙/유아 카테고리 데이터로 실측한다.
      → 에어밤 등 프로모션/광고 타이밍 근거.

지표 (시간단위로 실제 변하는 것만):
  ① 찜 증분(wishΔ)   — 관심 신호. 표본 큼. 시간대 트래픽의 주 지표.
  ② 주문수 증분(orderΔ) — 트렌딩 탭 일부 상품만(fomoBadge). 있으면 실구매 프록시로 최강.
  ③ 순위 상승 상품 수  — 종합 활발도 보조.
  ※ 리뷰는 시간단위로 안 변해서 제외(일일 크론이 담당).

데이터: rank_snapshots/hourly/YYYY-MM-DD_HHMM.json  (연속 시각 쌍의 증분 = 그 구간 활발도)

사용:
  python3 hourly_analyze.py            # 최근 수집분 전체 요일×시간 집계
  python3 hourly_analyze.py 2026-07-08 # 특정 날짜만
"""
import json, os, sys
from collections import defaultdict
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
SNAPDIR = os.path.join(DIR, "rank_snapshots", "hourly")
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def load_snaps(day_filter=None):
    """hourly 스냅샷 전부 로드 → [(dt, snap)] 시각순."""
    out = []
    if not os.path.isdir(SNAPDIR):
        return out
    for f in sorted(os.listdir(SNAPDIR)):
        if not f.endswith(".json"):
            continue
        key = f[:-5]  # YYYY-MM-DD_HHMM
        if day_filter and not key.startswith(day_filter):
            continue
        try:
            dt = datetime.strptime(key, "%Y-%m-%d_%H%M")
        except ValueError:
            continue
        with open(os.path.join(SNAPDIR, f), encoding="utf-8") as fp:
            out.append((dt, json.load(fp)))
    return out


def flatten(snap):
    """스냅샷 → {product_id: {'wish':, 'order':, 'rank':}} (모든 탭 합침, 최소 순위 채택)."""
    m = {}
    for tab in snap.get("tabs", {}).values():
        for r in tab.get("rows", []):
            pid = r.get("id")
            if pid is None:
                continue
            cur = m.get(pid)
            if cur is None or (r.get("rank") or 999) < cur["rank"]:
                m[pid] = {"wish": r.get("wishCount"), "order": r.get("orderCount"),
                          "rank": r.get("rank") or 999, "name": r.get("name"), "brand": r.get("brand")}
    return m


def interval_delta(prev_snap, cur_snap):
    """직전→현재 구간의 총 증분."""
    a, b = flatten(prev_snap), flatten(cur_snap)
    wish_d = order_d = rank_up = 0
    movers = []  # (wishΔ, name)
    for pid, cur in b.items():
        prev = a.get(pid)
        if not prev:
            continue
        if cur["wish"] is not None and prev["wish"] is not None:
            d = cur["wish"] - prev["wish"]
            if d > 0:
                wish_d += d
                movers.append((d, cur["name"], cur["brand"]))
        if cur["order"] is not None and prev["order"] is not None:
            od = cur["order"] - prev["order"]
            if od > 0:
                order_d += od
        if cur["rank"] < prev["rank"]:
            rank_up += 1
    movers.sort(reverse=True)
    return {"wish": wish_d, "order": order_d, "rank_up": rank_up, "movers": movers[:5]}


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else None
    snaps = load_snaps(day)
    if len(snaps) < 2:
        print(f"⏳ 시간대 스냅샷이 아직 {len(snaps)}개예요. 2개 이상 쌓여야 구간 증분을 볼 수 있어요.")
        print(f"   (수집 폴더: {SNAPDIR})")
        print(f"   크론이 하루 여러 번 돌면 며칠 뒤 시간대 패턴이 나와요 🥰")
        return

    print(f"\n🕐 카카오 선물하기 시간대 트래픽 실측 — 스냅샷 {len(snaps)}개")
    print("=" * 64)

    # 구간별 상세 (연속 쌍)
    slot_wish = defaultdict(list)   # "시작시~끝시" → [wishΔ...] 여러 날 누적
    slot_order = defaultdict(list)
    print("\n▸ 구간별 활발도 (찜 증분 = 관심 트래픽)")
    for (pd, ps), (cd, cs) in zip(snaps, snaps[1:]):
        # 날 경계 넘어가면 구간 아님(밤→다음날 아침 사이 공백)
        gap_h = (cd - pd).total_seconds() / 3600
        if gap_h > 6:
            continue
        d = interval_delta(ps, cs)
        label = f"{pd.strftime('%m/%d(%a) %H시')}→{cd.strftime('%H시')}"
        slot = f"{pd.hour:02d}~{cd.hour:02d}시"
        slot_wish[slot].append(d["wish"])
        slot_order[slot].append(d["order"])
        top = d["movers"][0] if d["movers"] else None
        top_s = f" · 최고 {top[2]} 찜+{top[0]}" if top else ""
        print(f"  {label:<22} 찜+{d['wish']:>6,}  주문+{d['order']:>4,}  순위상승 {d['rank_up']:>2}개{top_s}")

    # 시간대 슬롯 평균 (여러 날 누적되면 패턴)
    if any(len(v) > 1 for v in slot_wish.values()):
        print("\n▸ 시간대 슬롯 평균 (여러 날 누적 — 진짜 피크)")
        rows = [(sum(v) / len(v), slot, len(v)) for slot, v in slot_wish.items()]
        rows.sort(reverse=True)
        for avg, slot, n in rows:
            bar = "█" * min(40, int(avg / max(1, rows[0][0]) * 40))
            print(f"  {slot:<8} 찜+{avg:>7,.0f}/구간 (n={n}) {bar}")
        print(f"\n🎯 피크 구간: {rows[0][1]} (평균 찜+{rows[0][0]:,.0f})")
    else:
        print("\n(하루치만 있어요 — 며칠 더 쌓이면 '시간대 슬롯 평균'으로 진짜 피크가 나와요)")


if __name__ == "__main__":
    main()
