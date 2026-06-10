"""스냅샷 수집 + 변동 감지 엔진.

run_snapshot(): active 제품 전체를 수집 → snapshots 저장 → 전일 대비 변동을 alerts에 기록.
crontab/launchd 에서 매일 1회 호출한다.
"""
import sys
import json
from datetime import date

sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/price_tracker")
import db  # noqa: E402
from collectors import naver as naver_col  # noqa: E402
from collectors import coupang as coupang_col  # noqa: E402

# 변동 임계치
REVIEW_SURGE_PCT = 3.0     # 리뷰수 +3% 이상이면 급증
REVIEW_SURGE_ABS = 50      # 또는 +50건 이상


def _fmt_won(v):
    try:
        return f"{int(v):,}원"
    except Exception:
        return str(v)


def detect_changes(product, cur, prev):
    """전일 대비 변동 → alert dict 리스트."""
    if not prev:
        return []
    alerts = []
    label = product["label"]
    d = cur["snap_date"]

    # 가격
    cp, pp = cur.get("price"), prev.get("price")
    if cp and pp and cp != pp:
        diff = cp - pp
        pct = diff / pp * 100
        if diff < 0:
            alerts.append(("price_drop",
                           f"💰 [{label}] 가격 인하 {_fmt_won(pp)}→{_fmt_won(cp)} ({pct:+.1f}%)",
                           diff))
        else:
            alerts.append(("price_up",
                           f"📈 [{label}] 가격 인상 {_fmt_won(pp)}→{_fmt_won(cp)} ({pct:+.1f}%)",
                           diff))

    # 리뷰수 급증
    cr, pr = cur.get("review_count"), prev.get("review_count")
    if cr and pr and cr > pr:
        diff = cr - pr
        pct = diff / pr * 100 if pr else 0
        if diff >= REVIEW_SURGE_ABS or pct >= REVIEW_SURGE_PCT:
            alerts.append(("review_surge",
                           f"🔥 [{label}] 리뷰 급증 +{diff:,}건 ({pct:+.1f}%) → 판매 활발",
                           diff))

    # 순위 변동
    ck, pk = cur.get("ranking"), prev.get("ranking")
    if ck and pk and ck != pk:
        diff = ck - pk
        if diff < 0:
            alerts.append(("rank_up",
                           f"⬆️ [{label}] 순위 상승 {pk}위→{ck}위", diff))
        else:
            alerts.append(("rank_down",
                           f"⬇️ [{label}] 순위 하락 {pk}위→{ck}위", diff))

    # 평점 변동
    cg, pg = cur.get("rating"), prev.get("rating")
    if cg and pg and abs(cg - pg) >= 0.05:
        alerts.append(("rating_change",
                       f"⭐ [{label}] 평점 {pg:.2f}→{cg:.2f}", cg - pg))

    # 옵션 구성 변경
    try:
        co = {o["name"] for o in json.loads(cur.get("options_json") or "[]")}
        po = {o["name"] for o in json.loads(prev.get("options_json") or "[]")}
        added = co - po
        removed = po - co
        if added or removed:
            parts = []
            if added:
                parts.append("신규: " + ", ".join(list(added)[:3]))
            if removed:
                parts.append("삭제: " + ", ".join(list(removed)[:3]))
            alerts.append(("option_change",
                           f"🧩 [{label}] 옵션 구성 변경 — " + " / ".join(parts), None))
    except Exception:
        pass

    return alerts


def run_snapshot(snap_date=None, with_reviews=False, only_ref=None):
    """전체(또는 단일) 제품 스냅샷 수집 + 변동 감지.

    only_ref: 특정 product id 만 수집(수동 새로고침용).
    """
    db.init_db()
    snap_date = snap_date or date.today().isoformat()
    products = db.list_products(active_only=True)
    if only_ref:
        products = [p for p in products if p["id"] == only_ref]

    ok, fail, n_alerts = 0, 0, 0
    for p in products:
        try:
            if p["platform"] == "coupang":
                data = coupang_col.collect(p, with_reviews=with_reviews)
            else:
                data = naver_col.collect(p)
        except Exception as e:
            print(f"  ❌ [{p['label']}] 수집오류: {e}")
            data = None

        if not data:
            fail += 1
            print(f"  ⚠️  [{p['label']}] 매칭 실패(스킵)")
            continue

        db.save_snapshot(
            p["id"], snap_date,
            price=data.get("price"), review_count=data.get("review_count"),
            rating=data.get("rating"), ranking=data.get("ranking"),
            revenue_monthly=data.get("revenue_monthly"),
            sales_monthly=data.get("sales_monthly"),
            options=data.get("options"), raw=data.get("raw"),
        )
        cur, prev = db.latest_two(p["id"])
        for typ, msg, delta in detect_changes(p, cur, prev):
            db.add_alert(p["id"], snap_date, typ, msg, delta)
            n_alerts += 1
            print(f"    🔔 {msg}")
        ok += 1
        price = data.get("price")
        print(f"  ✅ [{p['label']}] 가격 {_fmt_won(price) if price else '-'} "
              f"리뷰 {data.get('review_count') or '-'}")

    print(f"\n📊 스냅샷 {snap_date}: 성공 {ok} / 실패 {fail} / 알림 {n_alerts}건")
    return {"date": snap_date, "ok": ok, "fail": fail, "alerts": n_alerts}


if __name__ == "__main__":
    wr = "--reviews" in sys.argv
    run_snapshot(with_reviews=wr)
