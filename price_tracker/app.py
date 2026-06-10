"""경쟁사 레이더 — FastAPI 백엔드 (포트 8091).

지정 경쟁사 제품의 가격/리뷰/평점/순위/옵션 변화를 추적하는 대시보드.
ERP(8085)와 동일한 디자인 시스템.
실행: python app.py  →  http://localhost:8091
"""
import os
import sys
import json
from typing import Optional

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))
import db  # noqa: E402
import snapshot as snap  # noqa: E402

BASE = os.path.dirname(__file__)
app = FastAPI(title="경쟁사 레이더")
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---------- 제품 ----------
class ProductIn(BaseModel):
    platform: str
    label: str
    keyword: Optional[str] = None
    match_name: Optional[str] = None
    product_id: Optional[str] = None
    product_url: Optional[str] = None
    brand: Optional[str] = None
    is_mine: int = 0


def _change(cur, prev, key):
    if not cur or not prev:
        return None
    a, b = cur.get(key), prev.get(key)
    if a is None or b is None:
        return None
    return a - b


@app.get("/api/products")
def api_products():
    out = []
    for p in db.list_products():
        cur, prev = db.latest_two(p["id"])
        snaps = db.get_snapshots(p["id"], limit=30)
        spark = [{"d": s["snap_date"], "price": s["price"],
                  "review_count": s["review_count"]} for s in snaps]
        out.append({
            **p,
            "current": cur,
            "price": cur.get("price") if cur else None,
            "review_count": cur.get("review_count") if cur else None,
            "rating": cur.get("rating") if cur else None,
            "ranking": cur.get("ranking") if cur else None,
            "price_change": _change(cur, prev, "price"),
            "review_change": _change(cur, prev, "review_count"),
            "rank_change": _change(cur, prev, "ranking"),
            "snap_count": len(snaps),
            "spark": spark,
        })
    return out


@app.post("/api/products")
def api_add_product(p: ProductIn):
    pid = db.add_product(
        platform=p.platform, label=p.label, keyword=p.keyword,
        match_name=p.match_name, product_id=p.product_id,
        product_url=p.product_url, brand=p.brand, is_mine=p.is_mine)
    return {"id": pid, "ok": True}


@app.put("/api/products/{pid}")
def api_update_product(pid: int, body: dict):
    db.update_product(pid, **body)
    return {"ok": True}


@app.delete("/api/products/{pid}")
def api_delete_product(pid: int):
    db.delete_product(pid)
    return {"ok": True}


@app.get("/api/products/{pid}")
def api_product_detail(pid: int):
    p = db.get_product(pid)
    if not p:
        return JSONResponse({"error": "not found"}, status_code=404)
    snaps = db.get_snapshots(pid, limit=90)
    for s in snaps:
        s["options"] = json.loads(s["options_json"]) if s.get("options_json") else None
    alerts = [a for a in db.list_alerts(limit=200) if a["product_ref"] == pid]
    latest_opts = None
    for s in reversed(snaps):
        if s.get("options"):
            latest_opts = s["options"]
            break
    return {"product": p, "snapshots": snaps, "alerts": alerts,
            "latest_options": latest_opts}


# ---------- 수집 ----------
@app.post("/api/products/{pid}/refresh")
def api_refresh_one(pid: int, with_reviews: bool = False):
    res = snap.run_snapshot(with_reviews=with_reviews, only_ref=pid)
    return res


@app.post("/api/products/{pid}/reviews")
def api_analyze_reviews(pid: int):
    """쿠팡 리뷰 다운로드 → 평점/옵션 보강 (느림, on-demand)."""
    res = snap.run_snapshot(with_reviews=True, only_ref=pid)
    return res


@app.post("/api/snapshot")
def api_snapshot_all(background: BackgroundTasks, with_reviews: bool = False):
    res = snap.run_snapshot(with_reviews=with_reviews)
    return res


# ---------- 알림 ----------
@app.get("/api/alerts")
def api_alerts(unseen_only: bool = False):
    return db.list_alerts(limit=80, unseen_only=unseen_only)


@app.post("/api/alerts/seen")
def api_alerts_seen():
    db.mark_alerts_seen()
    return {"ok": True}


@app.get("/api/summary")
def api_summary():
    prods = db.list_products()
    mine = [p for p in prods if p["is_mine"]]
    comp = [p for p in prods if not p["is_mine"]]
    alerts = db.list_alerts(limit=200)
    from datetime import date
    today = date.today().isoformat()
    today_alerts = [a for a in alerts if (a.get("snap_date") or "") == today]

    def avg_price(group):
        vals = []
        for p in group:
            cur, _ = db.latest_two(p["id"])
            if cur and cur.get("price"):
                vals.append(cur["price"])
        return round(sum(vals) / len(vals)) if vals else None

    return {
        "total": len(prods),
        "mine": len(mine),
        "competitors": len(comp),
        "naver": len([p for p in prods if p["platform"] == "naver"]),
        "coupang": len([p for p in prods if p["platform"] == "coupang"]),
        "today_alerts": len(today_alerts),
        "total_alerts": len(alerts),
        "avg_price_mine": avg_price(mine),
        "avg_price_competitors": avg_price(comp),
    }


if __name__ == "__main__":
    import uvicorn
    db.init_db()
    print("🛰️  경쟁사 레이더 → http://localhost:8091")
    uvicorn.run(app, host="0.0.0.0", port=8091)
