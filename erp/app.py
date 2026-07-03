"""비코어랩 ERP — FastAPI 메인 앱"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import get_db, init_db, DB_PATH

app = FastAPI(title="비코어랩 ERP", version="1.0")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

LOGISTICS_URL = "http://localhost:8082"

# ── 대한민국 공휴일 데이터 (2026~2027) ──
# 출처: superkts.com/day/holiday + 정부 임시공휴일 고시
# 음력 기반 공휴일은 천문연 월력요항 기준으로 확인
KR_HOLIDAYS = {
    # 2026년
    "2026-01-01": "신정",
    "2026-02-16": "설날 연휴",
    "2026-02-17": "설날",
    "2026-02-18": "설날 연휴",
    "2026-03-01": "3·1절",
    "2026-03-02": "대체공휴일(3·1절)",
    "2026-05-01": "노동절",
    "2026-05-05": "어린이날",
    "2026-05-24": "부처님 오신날",
    "2026-05-25": "대체공휴일(부처님 오신날)",
    "2026-06-03": "제9회 전국동시지방선거",
    "2026-06-06": "현충일",
    "2026-08-15": "광복절",
    "2026-08-17": "대체공휴일(광복절)",
    "2026-09-24": "추석 연휴",
    "2026-09-25": "추석",
    "2026-09-26": "추석 연휴",
    "2026-10-03": "개천절",
    "2026-10-05": "대체공휴일(개천절)",
    "2026-10-09": "한글날",
    "2026-12-25": "크리스마스",
    # 2027년
    "2027-01-01": "신정",
    "2027-02-06": "설날 연휴",
    "2027-02-07": "설날",
    "2027-02-08": "설날 연휴",
    "2027-02-09": "대체공휴일(설날)",
    "2027-03-01": "3·1절",
    "2027-05-01": "노동절",
    "2027-05-03": "대체공휴일(노동절)",
    "2027-05-05": "어린이날",
    "2027-05-13": "부처님 오신날",
    "2027-06-06": "현충일",
    "2027-08-15": "광복절",
    "2027-08-16": "대체공휴일(광복절)",
    "2027-09-14": "추석 연휴",
    "2027-09-15": "추석",
    "2027-09-16": "추석 연휴",
    "2027-10-03": "개천절",
    "2027-10-04": "대체공휴일(개천절)",
    "2027-10-09": "한글날",
    "2027-10-11": "대체공휴일(한글날)",
    "2027-12-25": "크리스마스",
    "2027-12-27": "대체공휴일(크리스마스)",
}


def get_holidays_in_range(start: str, end: str) -> list:
    """기간 내 공휴일 이벤트 목록 반환 (events 테이블에 저장하지 않고 조회 시 합성)"""
    result = []
    for date_str, name in KR_HOLIDAYS.items():
        if (not start or date_str >= start) and (not end or date_str <= end):
            result.append({
                "id": f"holiday-{date_str}",
                "title": f"🔴 {name}",
                "event_type": "holiday",
                "start_date": date_str,
                "end_date": None,
                "all_day": 1,
                "memo": f"대한민국 공휴일 — {name}",
                "source": "holiday",
                "source_id": date_str,
                "readonly": True,
            })
    return result


# ── 의존성 ──
def db():
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


# ── 메인 페이지 ──
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    resp = templates.TemplateResponse("index.html", {"request": request})
    # index.html은 절대 캐시 금지 — 항상 최신 app.js 버전을 물게 함(구버전 화면 고착 방지)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ── 인증 ──
@app.post("/api/auth/login")
async def login(request: Request, conn=Depends(db)):
    body = await request.json()
    pw_hash = hashlib.sha256(body["password"].encode()).hexdigest()
    user = conn.execute(
        "SELECT id, username, name, role FROM users WHERE username=? AND password_hash=? AND is_active=1",
        (body["username"], pw_hash),
    ).fetchone()
    if not user:
        raise HTTPException(400, "아이디 또는 비밀번호가 일치하지 않습니다")
    return dict(user)


# ── 대시보드 ──
@app.get("/api/dashboard")
async def dashboard(conn=Depends(db)):
    partners = conn.execute("SELECT COUNT(*) as cnt FROM partners WHERE is_active=1").fetchone()["cnt"]
    products = conn.execute("SELECT COUNT(*) as cnt FROM products WHERE is_active=1").fetchone()["cnt"]
    low_stock = conn.execute("SELECT COUNT(*) as cnt FROM stock s JOIN products p ON p.id=s.product_id WHERE s.qty_on_hand <= p.safety_stock AND p.is_active=1").fetchone()["cnt"]

    today = datetime.now().strftime("%Y-%m-%d")
    month_start = datetime.now().strftime("%Y-%m-01")
    today_sales = conn.execute(
        "SELECT COALESCE(SUM(total_amount),0) as total FROM sales WHERE sale_date=? AND status='confirmed'",
        (today,),
    ).fetchone()["total"]
    month_sales = conn.execute(
        "SELECT COALESCE(SUM(total_amount),0) as total FROM sales WHERE sale_date>=? AND status='confirmed'",
        (month_start,),
    ).fetchone()["total"]
    pending_po = conn.execute(
        "SELECT COUNT(*) as cnt FROM purchase_orders WHERE status IN ('draft','confirmed','partial')"
    ).fetchone()["cnt"]

    return {
        "partners": partners,
        "products": products,
        "low_stock": low_stock,
        "today_sales": today_sales,
        "month_sales": month_sales,
        "pending_po": pending_po,
    }


# ── 거래처 CRUD ──
@app.get("/api/partners")
async def list_partners(
    q: str = "", type: str = "", page: int = 1, size: int = 50, conn=Depends(db)
):
    where, params = ["is_active=1"], []
    if q:
        where.append("(name LIKE ? OR partner_code LIKE ? OR business_no LIKE ?)")
        params += [f"%{q}%"] * 3
    if type:
        where.append("type=?")
        params.append(type)
    w = " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) as cnt FROM partners WHERE {w}", params).fetchone()["cnt"]
    rows = conn.execute(
        f"SELECT * FROM partners WHERE {w} ORDER BY name LIMIT ? OFFSET ?",
        params + [size, (page - 1) * size],
    ).fetchall()
    return {"items": [dict(r) for r in rows], "total": total, "page": page, "size": size}


@app.get("/api/partners/{pid}")
async def get_partner(pid: int, conn=Depends(db)):
    row = conn.execute("SELECT * FROM partners WHERE id=?", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "거래처를 찾을 수 없습니다")
    return dict(row)


@app.post("/api/partners")
async def create_partner(request: Request, conn=Depends(db)):
    d = await request.json()
    try:
        cur = conn.execute(
            """INSERT INTO partners (partner_code,name,type,ceo_name,business_no,phone,mobile,email,address,bank_info,memo,ecount_code)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["partner_code"], d["name"], d.get("type", "supplier"), d.get("ceo_name"),
             d.get("business_no"), d.get("phone"), d.get("mobile"), d.get("email"),
             d.get("address"), d.get("bank_info"), d.get("memo"), d.get("ecount_code")),
        )
        conn.commit()
        return {"id": cur.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(400, "이미 존재하는 거래처 코드입니다")


@app.put("/api/partners/{pid}")
async def update_partner(pid: int, request: Request, conn=Depends(db)):
    d = await request.json()
    conn.execute(
        """UPDATE partners SET name=?,type=?,ceo_name=?,business_no=?,phone=?,mobile=?,
           email=?,address=?,bank_info=?,memo=?,ecount_code=?,updated_at=datetime('now','localtime')
           WHERE id=?""",
        (d["name"], d.get("type", "supplier"), d.get("ceo_name"), d.get("business_no"),
         d.get("phone"), d.get("mobile"), d.get("email"), d.get("address"),
         d.get("bank_info"), d.get("memo"), d.get("ecount_code"), pid),
    )
    conn.commit()
    return {"ok": True}


@app.delete("/api/partners/{pid}")
async def delete_partner(pid: int, conn=Depends(db)):
    conn.execute("UPDATE partners SET is_active=0, updated_at=datetime('now','localtime') WHERE id=?", (pid,))
    conn.commit()
    return {"ok": True}


# ── 품목 CRUD ──
@app.get("/api/products")
async def list_products(
    q: str = "", category: str = "", page: int = 1, size: int = 50, conn=Depends(db)
):
    where, params = ["p.is_active=1"], []
    if q:
        where.append("(p.name LIKE ? OR p.product_code LIKE ? OR p.ezadmin_code LIKE ?)")
        params += [f"%{q}%"] * 3
    if category:
        where.append("p.category=?")
        params.append(category)
    w = " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) as cnt FROM products p WHERE {w}", params).fetchone()["cnt"]
    rows = conn.execute(
        f"""SELECT p.*, s.qty_on_hand, s.qty_reserved, s.qty_available,
            sup.name as supplier_name
            FROM products p
            LEFT JOIN stock s ON s.product_id=p.id
            LEFT JOIN partners sup ON sup.id=p.primary_supplier_id
            WHERE {w} ORDER BY p.name LIMIT ? OFFSET ?""",
        params + [size, (page - 1) * size],
    ).fetchall()
    return {"items": [dict(r) for r in rows], "total": total, "page": page, "size": size}


@app.get("/api/products/{pid}")
async def get_product(pid: int, conn=Depends(db)):
    row = conn.execute(
        """SELECT p.*, s.qty_on_hand, s.qty_reserved, s.qty_available, sup.name as supplier_name
           FROM products p LEFT JOIN stock s ON s.product_id=p.id
           LEFT JOIN partners sup ON sup.id=p.primary_supplier_id
           WHERE p.id=?""",
        (pid,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "품목을 찾을 수 없습니다")
    return dict(row)


@app.post("/api/products")
async def create_product(request: Request, conn=Depends(db)):
    d = await request.json()
    try:
        cur = conn.execute(
            """INSERT INTO products (product_code,name,spec,unit,category,product_type,
               purchase_price,sell_price,safety_stock,lead_time_days,moq,
               primary_supplier_id,barcode,ecount_code,ezadmin_code)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["product_code"], d["name"], d.get("spec"), d.get("unit", "EA"),
             d.get("category"), d.get("product_type", "goods"),
             d.get("purchase_price", 0), d.get("sell_price", 0),
             d.get("safety_stock", 0), d.get("lead_time_days", 7), d.get("moq", 0),
             d.get("primary_supplier_id"), d.get("barcode"),
             d.get("ecount_code"), d.get("ezadmin_code")),
        )
        conn.commit()
        conn.execute(
            "INSERT INTO stock (product_id, qty_on_hand) VALUES (?, 0)", (cur.lastrowid,)
        )
        conn.commit()
        return {"id": cur.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(400, "이미 존재하는 품목 코드입니다")


@app.put("/api/products/{pid}")
async def update_product(pid: int, request: Request, conn=Depends(db)):
    d = await request.json()
    conn.execute(
        """UPDATE products SET name=?,spec=?,unit=?,category=?,product_type=?,
           purchase_price=?,sell_price=?,safety_stock=?,lead_time_days=?,moq=?,
           primary_supplier_id=?,barcode=?,ecount_code=?,ezadmin_code=?,
           updated_at=datetime('now','localtime') WHERE id=?""",
        (d["name"], d.get("spec"), d.get("unit", "EA"), d.get("category"),
         d.get("product_type", "goods"), d.get("purchase_price", 0),
         d.get("sell_price", 0), d.get("safety_stock", 0),
         d.get("lead_time_days", 7), d.get("moq", 0),
         d.get("primary_supplier_id"), d.get("barcode"),
         d.get("ecount_code"), d.get("ezadmin_code"), pid),
    )
    conn.commit()
    return {"ok": True}


# ── 재고 ──
@app.get("/api/stock")
async def list_stock(q: str = "", alert_only: bool = False, show_material: bool = False, conn=Depends(db)):
    where, params = ["p.is_active=1"], []
    if not show_material:
        where.append("p.product_type='goods'")
    if q:
        where.append("(p.name LIKE ? OR p.product_code LIKE ?)")
        params += [f"%{q}%"] * 2
    if alert_only:
        where.append("s.qty_on_hand <= p.safety_stock")
    w = " AND ".join(where)
    rows = conn.execute(
        f"""SELECT p.id, p.product_code, p.name, p.spec, p.unit, p.safety_stock,
            p.ezadmin_code, p.category, p.product_type, p.purchase_price, p.sell_price,
            p.lead_time_days, p.moq, p.barcode, p.ecount_code, p.is_discontinued,
            s.qty_on_hand, s.qty_reserved, s.qty_available, s.pending_inbound,
            s.last_synced_at,
            (SELECT MIN(po.delivery_date) FROM purchase_order_lines pol
             JOIN purchase_orders po ON po.id=pol.po_id
             WHERE pol.product_id=p.id AND po.status IN ('confirmed','partial')
             AND po.delivery_date IS NOT NULL) as next_inbound_date,
            COALESCE((SELECT SUM(sl.qty) FROM sale_lines sl JOIN sales sa ON sa.id=sl.sale_id
             WHERE sl.product_id=p.id AND sa.status='confirmed'
             AND sa.sale_date >= date('now', '-30 days', 'localtime')), 0) / 30.0 as avg_daily_out
            FROM products p LEFT JOIN stock s ON s.product_id=p.id
            WHERE {w} ORDER BY s.qty_on_hand ASC""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/stock/summary")
async def stock_summary(conn=Depends(db)):
    base = "FROM stock s JOIN products p ON p.id=s.product_id WHERE p.is_active=1 AND p.product_type='goods' AND COALESCE(p.is_discontinued,0)=0"
    normal = conn.execute(f"SELECT COUNT(*) as cnt {base} AND s.qty_on_hand > p.safety_stock").fetchone()["cnt"]
    low = conn.execute(f"SELECT COUNT(*) as cnt {base} AND s.qty_on_hand > 0 AND s.qty_on_hand <= p.safety_stock").fetchone()["cnt"]
    out = conn.execute(f"SELECT COUNT(*) as cnt {base} AND s.qty_on_hand <= 0").fetchone()["cnt"]
    disc = conn.execute(
        "SELECT COUNT(*) as cnt FROM stock s JOIN products p ON p.id=s.product_id WHERE p.is_active=1 AND p.product_type='goods' AND p.is_discontinued=1"
    ).fetchone()["cnt"]
    return {"normal": normal, "low": low, "out_of_stock": out, "total": normal + low + out, "discontinued": disc}


@app.get("/api/stock/outbound")
async def stock_outbound(preset: str = "", start: str = "", end: str = ""):
    """재고수불부 기간별 출고량 — 물류서버 outbound-history 프록시"""
    import aiohttp
    params = {}
    if preset:
        params["preset"] = preset
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{LOGISTICS_URL}/api/outbound-history", params=params) as resp:
            if resp.status != 200:
                raise HTTPException(502, "물류서버 연결 실패")
            return await resp.json()


@app.post("/api/stock/sync")
async def sync_stock(conn=Depends(db)):
    """이지어드민 캐시 데이터로 재고 동기화"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{LOGISTICS_URL}/api/cached-data") as resp:
            if resp.status != 200:
                raise HTTPException(502, "물류서버 연결 실패")
            data = await resp.json()

    inventory = (data.get("data") or data).get("inventory", {})  # 물류서버 응답이 {data:{inventory}} 로 중첩됨
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updated = 0

    for code, info in inventory.items():
        qty = info.get("stock", 0)
        product = conn.execute(
            "SELECT id FROM products WHERE product_code=? OR ezadmin_code=?", (code, code)
        ).fetchone()
        if product:
            existing = conn.execute("SELECT id, qty_on_hand FROM stock WHERE product_id=?", (product["id"],)).fetchone()
            if existing:
                old_qty = existing["qty_on_hand"]
                conn.execute(
                    "UPDATE stock SET qty_on_hand=?, last_synced_at=?, updated_at=datetime('now','localtime') WHERE product_id=?",
                    (qty, now, product["id"]),
                )
                if old_qty != qty:
                    conn.execute(
                        """INSERT INTO stock_transactions (product_id, tx_type, qty_change, qty_before, qty_after, ref_type, memo)
                           VALUES (?, 'adjust', ?, ?, ?, 'sync', '이지어드민 동기화')""",
                        (product["id"], qty - old_qty, old_qty, qty),
                    )
            else:
                conn.execute(
                    "INSERT INTO stock (product_id, qty_on_hand, last_synced_at) VALUES (?, ?, ?)",
                    (product["id"], qty, now),
                )
            updated += 1

    conn.commit()
    return {"synced": updated, "total_items": len(inventory), "timestamp": now}


@app.post("/api/stock/adjust")
async def adjust_stock(request: Request, conn=Depends(db)):
    d = await request.json()
    product_id = d["product_id"]
    qty_change = d["qty_change"]
    memo = d.get("memo", "")

    stock = conn.execute("SELECT qty_on_hand FROM stock WHERE product_id=?", (product_id,)).fetchone()
    if not stock:
        raise HTTPException(404, "재고 정보가 없습니다")
    old_qty = stock["qty_on_hand"]
    new_qty = old_qty + qty_change

    conn.execute("UPDATE stock SET qty_on_hand=?, updated_at=datetime('now','localtime') WHERE product_id=?",
                 (new_qty, product_id))
    conn.execute(
        """INSERT INTO stock_transactions (product_id, tx_type, qty_change, qty_before, qty_after, ref_type, memo)
           VALUES (?, 'adjust', ?, ?, ?, 'manual', ?)""",
        (product_id, qty_change, old_qty, new_qty, memo),
    )
    conn.commit()
    return {"product_id": product_id, "old_qty": old_qty, "new_qty": new_qty}


# ── 매출 ──
@app.get("/api/sales")
async def list_sales(
    date_from: str = "", date_to: str = "", channel: str = "",
    partner_id: int = 0, q: str = "", group: str = "",
    page: int = 1, size: int = 50, conn=Depends(db)
):
    where, params = ["1=1"], []
    if date_from:
        where.append("s.sale_date>=?")
        params.append(date_from)
    if date_to:
        where.append("s.sale_date<=?")
        params.append(date_to)
    if channel:
        where.append("s.channel LIKE ?")
        params.append(f"%{channel}%")
    if partner_id:
        where.append("s.partner_id=?")
        params.append(partner_id)
    if q:
        where.append("(s.recipient LIKE ? OR s.channel LIKE ?)")
        params += [f"%{q}%"] * 2
    w = " AND ".join(where)

    if group == "channel":
        # 검색 기간 전체를 채널별로 합산 (날짜 무시)
        total = conn.execute(
            f"SELECT COUNT(DISTINCT s.channel) as cnt FROM sales s WHERE {w}", params
        ).fetchone()["cnt"]
        rows = conn.execute(
            f"""SELECT s.channel, COUNT(*) as item_count,
                MIN(s.sale_date) as date_from, MAX(s.sale_date) as date_to,
                SUM(s.total_supply) as total_supply, SUM(s.total_tax) as total_tax,
                SUM(s.total_amount) as total_amount
                FROM sales s WHERE {w}
                GROUP BY s.channel
                ORDER BY total_amount DESC
                LIMIT ? OFFSET ?""",
            params + [size, (page - 1) * size],
        ).fetchall()
        items = []
        for r in rows:
            rd = dict(r)
            factor = CHANNEL_ADJUSTMENT.get(rd["channel"], 1.0)
            rd["total_supply"] = round(rd["total_supply"] * factor)
            rd["total_tax"] = round(rd["total_tax"] * factor)
            rd["total_amount"] = round(rd["total_amount"] * factor)
            items.append(rd)
        adj_amount, adj_supply = _calc_sales_total(conn, date_from, date_to)
        return {
            "items": items, "total": total, "page": page, "size": size,
            "sum_amount": adj_amount, "sum_supply": adj_supply,
            "grouped": True,
        }

    total = conn.execute(f"SELECT COUNT(*) as cnt FROM sales s WHERE {w}", params).fetchone()["cnt"]
    adj_amount, adj_supply = _calc_sales_total(conn, date_from, date_to)
    rows = conn.execute(
        f"""SELECT s.*, p.name as partner_name
            FROM sales s LEFT JOIN partners p ON p.id=s.partner_id
            WHERE {w} ORDER BY s.sale_date DESC, s.id DESC LIMIT ? OFFSET ?""",
        params + [size, (page - 1) * size],
    ).fetchall()
    return {
        "items": [dict(r) for r in rows], "total": total, "page": page, "size": size,
        "sum_amount": adj_amount, "sum_supply": adj_supply,
    }


@app.get("/api/sales/channels")
async def list_sales_channels(conn=Depends(db)):
    rows = conn.execute(
        """SELECT channel, SUM(total_amount) as total
           FROM sales
           WHERE channel IS NOT NULL AND channel != ''
           AND sale_date >= date('now', '-365 days', 'localtime')
           AND LENGTH(channel) > 1
           AND channel NOT GLOB '[0-9]*'
           GROUP BY channel
           HAVING total > 0
           ORDER BY total DESC"""
    ).fetchall()
    return [r["channel"] for r in rows]


@app.get("/api/sales/summary")
async def sales_summary(
    date_from: str = "", date_to: str = "",
    group_by: str = "daily", channel: str = "",
    conn=Depends(db),
):
    where, params = ["s.status='confirmed'"], []
    if date_from:
        where.append("s.sale_date>=?")
        params.append(date_from)
    if date_to:
        where.append("s.sale_date<=?")
        params.append(date_to)
    if channel:
        where.append("s.channel LIKE ?")
        params.append(f"%{channel}%")
    w = " AND ".join(where)

    if group_by == "channel":
        if not channel:
            ch_data = _get_summary_by_channel(conn, date_from, date_to)
            grand_total = sum(c["total"] for c in ch_data)
            return {"items": ch_data, "grand_total": grand_total}
        rows = conn.execute(
            f"""SELECT s.channel as label, SUM(sl.qty) as qty,
                SUM(s.total_supply) as supply, SUM(s.total_tax) as tax, SUM(s.total_amount) as total, COUNT(DISTINCT s.id) as cnt
                FROM sales s LEFT JOIN sale_lines sl ON sl.sale_id=s.id
                WHERE {w} GROUP BY s.channel ORDER BY total DESC""",
            params,
        ).fetchall()
        result = []
        for r in rows:
            rd = dict(r)
            factor = CHANNEL_ADJUSTMENT.get(rd["label"], 1.0)
            rd["supply"] = round(rd["supply"] * factor)
            rd["tax"] = round(rd["tax"] * factor)
            rd["total"] = round(rd["total"] * factor)
            result.append(rd)
        return {"items": result, "grand_total": sum(r["total"] for r in result)}
    elif group_by == "product":
        rows = conn.execute(
            f"""SELECT sl.product_name as label, SUM(sl.qty) as qty,
                SUM(sl.supply_amount) as supply, SUM(sl.tax_amount) as tax, SUM(sl.line_total) as total
                FROM sale_lines sl JOIN sales s ON s.id=sl.sale_id
                WHERE {w} GROUP BY sl.product_name ORDER BY total DESC""",
            params,
        ).fetchall()
        # 채널 지정 드릴다운이면 그 채널 상품 합이 곧 채널 매출.
        # 전체 품목별이면 정산 기반 total(_calc_sales_total)로 정확 집계.
        if channel:
            grand_total = sum((r["total"] or 0) for r in rows)
        else:
            grand_total, _ = _calc_sales_total(conn, date_from, date_to)
        return {"items": [dict(r) for r in rows], "grand_total": grand_total}
    elif group_by == "weekly":
        ch_rows = conn.execute(
            f"""SELECT s.channel, strftime('%Y-W%W', s.sale_date) as week,
                SUM(s.total_supply) as supply, SUM(s.total_tax) as tax, SUM(s.total_amount) as total
                FROM sales s WHERE {w} GROUP BY s.channel, week""",
            params,
        ).fetchall()
        weekly = {}
        for r in ch_rows:
            factor = CHANNEL_ADJUSTMENT.get(r["channel"], 1.0)
            wk = r["week"]
            if wk not in weekly:
                weekly[wk] = {"label": wk, "supply": 0, "tax": 0, "total": 0, "cnt": 0}
            weekly[wk]["supply"] += round(r["supply"] * factor)
            weekly[wk]["tax"] += round(r["tax"] * factor)
            weekly[wk]["total"] += round(r["total"] * factor)
        cnt_rows = conn.execute(
            f"""SELECT strftime('%Y-W%W', s.sale_date) as label, COUNT(*) as cnt
                FROM sales s WHERE {w} GROUP BY label""",
            params,
        ).fetchall()
        for cr in cnt_rows:
            if cr["label"] in weekly:
                weekly[cr["label"]]["cnt"] = cr["cnt"]
        grand_total, _ = _calc_sales_total(conn, date_from, date_to)
        return {"items": sorted(weekly.values(), key=lambda x: x["label"], reverse=True), "grand_total": grand_total}
    else:
        ch_rows = conn.execute(
            f"""SELECT s.channel, s.sale_date,
                SUM(s.total_supply) as supply, SUM(s.total_tax) as tax, SUM(s.total_amount) as total
                FROM sales s WHERE {w} GROUP BY s.channel, s.sale_date""",
            params,
        ).fetchall()
        daily = {}
        for r in ch_rows:
            factor = CHANNEL_ADJUSTMENT.get(r["channel"], 1.0)
            dt = r["sale_date"]
            if dt not in daily:
                daily[dt] = {"label": dt, "supply": 0, "tax": 0, "total": 0, "cnt": 0}
            daily[dt]["supply"] += round(r["supply"] * factor)
            daily[dt]["tax"] += round(r["tax"] * factor)
            daily[dt]["total"] += round(r["total"] * factor)
        cnt_rows = conn.execute(
            f"""SELECT s.sale_date as label, COUNT(*) as cnt
                FROM sales s WHERE {w} GROUP BY s.sale_date""",
            params,
        ).fetchall()
        for cr in cnt_rows:
            if cr["label"] in daily:
                daily[cr["label"]]["cnt"] = cr["cnt"]
        grand_total, _ = _calc_sales_total(conn, date_from, date_to)
        return {"items": sorted(daily.values(), key=lambda x: x["label"], reverse=True), "grand_total": grand_total}

    return {"items": [dict(r) for r in rows], "grand_total": 0}


@app.get("/api/sales/adjusted-summary")
async def adjusted_sales_summary(
    start: str = "", end: str = "", conn=Depends(db)
):
    """매출 요약 — 정산 확정 데이터 우선, 미확정 월은 보정계수 적용"""
    if not start:
        start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    if not end:
        end = datetime.now().strftime("%Y-%m-%d")

    start_ym = start[:7]
    end_ym = end[:7]

    settled = conn.execute(
        """SELECT year_month, channel, amount FROM settlement_monthly
           WHERE year_month BETWEEN ? AND ? ORDER BY year_month, amount DESC""",
        (start_ym, end_ym),
    ).fetchall()

    settled_months = {}
    for r in settled:
        ym = r["year_month"]
        if ym not in settled_months:
            settled_months[ym] = []
        settled_months[ym].append({"channel": r["channel"], "amount": r["amount"]})

    channels = []
    total_adjusted = 0
    total_raw = 0

    # 월별·채널별: ~FULLY_SETTLED_THROUGH 는 정산만(기존동작), 이후는 정산채널+이지어드민(보정)
    ch_map = {}

    def _acc(ch, raw, adjusted, cnt, settled):
        c = ch_map.get(ch)
        if not c:
            c = {"channel": ch, "count": 0, "raw_amount": 0, "adjusted_amount": 0,
                 "factor": 1.0, "_settled": False, "_est": False}
            ch_map[ch] = c
        c["raw_amount"] += raw
        c["adjusted_amount"] += adjusted
        c["count"] += cnt
        if settled:
            c["_settled"] = True
        else:
            c["_est"] = True

    cur = datetime.strptime(start_ym, "%Y-%m")
    end_dt = datetime.strptime(end_ym, "%Y-%m")
    while cur <= end_dt:
        ym = cur.strftime("%Y-%m")
        nxt = cur.replace(year=cur.year + 1, month=1) if cur.month == 12 else cur.replace(month=cur.month + 1)
        m_start = max(start, f"{ym}-01")
        m_end = min(end, (nxt - timedelta(days=1)).strftime("%Y-%m-%d"))
        use_settlement_only = (ym <= FULLY_SETTLED_THROUGH and ym in settled_months)
        settled_ch = set()
        for item in settled_months.get(ym, []):
            settled_ch.add(item["channel"])
            _acc(item["channel"], item["amount"], item["amount"], 0, True)
        for _sc in list(settled_ch):
            settled_ch.update(SETTLEMENT_EZADMIN_ALIAS.get(_sc, []))
        if not use_settlement_only:
            rows = conn.execute(
                """SELECT channel, COUNT(*) cnt, SUM(total_amount) amount
                   FROM sales WHERE sale_date BETWEEN ? AND ? GROUP BY channel""",
                (m_start, m_end),
            ).fetchall()
            for r in rows:
                ch = r["channel"]
                if ch in settled_ch:
                    continue
                raw = r["amount"] or 0
                factor = CHANNEL_ADJUSTMENT.get(ch, 1.0)
                _acc(ch, raw, round(raw * factor), r["cnt"], False)
        cur = nxt

    for ch, c in ch_map.items():
        total_raw += c["raw_amount"]
        total_adjusted += c["adjusted_amount"]
        status = "confirmed" if (c["_settled"] and not c["_est"]) else ("mixed" if c["_settled"] else "estimated")
        channels.append({
            "channel": ch, "count": c["count"], "raw_amount": c["raw_amount"],
            "factor": c["factor"], "adjusted_amount": c["adjusted_amount"], "status": status,
        })

    channels.sort(key=lambda x: -x["adjusted_amount"])

    return {
        "start": start, "end": end,
        "total_raw": total_raw, "total_adjusted": total_adjusted,
        "settled_months": list(settled_months.keys()),
        "channels": channels,
    }


@app.get("/api/sales/{sid}")
async def get_sale(sid: int, conn=Depends(db)):
    sale = conn.execute(
        "SELECT s.*, p.name as partner_name FROM sales s LEFT JOIN partners p ON p.id=s.partner_id WHERE s.id=?",
        (sid,),
    ).fetchone()
    if not sale:
        raise HTTPException(404, "매출 전표를 찾을 수 없습니다")
    lines = conn.execute(
        """SELECT sl.*, pr.product_code, pr.ezadmin_code
           FROM sale_lines sl LEFT JOIN products pr ON pr.id=sl.product_id
           WHERE sl.sale_id=?""",
        (sid,),
    ).fetchall()
    return {"sale": dict(sale), "lines": [dict(l) for l in lines]}


@app.post("/api/sales")
async def create_sale(request: Request, conn=Depends(db)):
    d = await request.json()
    cur = conn.execute(
        """INSERT INTO sales (sale_date, partner_id, channel, channel_order_no,
           total_supply, total_tax, total_amount, status, recipient, memo, created_by)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (d["sale_date"], d.get("partner_id"), d.get("channel"), d.get("channel_order_no"),
         d.get("total_supply", 0), d.get("total_tax", 0), d.get("total_amount", 0),
         d.get("status", "confirmed"), d.get("recipient"), d.get("memo"), d.get("created_by")),
    )
    sale_id = cur.lastrowid
    for line in d.get("lines", []):
        conn.execute(
            """INSERT INTO sale_lines (sale_id, product_id, product_name, qty, unit_price,
               supply_amount, tax_amount, line_total)
               VALUES (?,?,?,?,?,?,?,?)""",
            (sale_id, line.get("product_id"), line.get("product_name"), line["qty"],
             line.get("unit_price", 0), line.get("supply_amount", 0),
             line.get("tax_amount", 0), line.get("line_total", 0)),
        )
    conn.commit()
    return {"id": sale_id}


# ── 매출 동기화 (물류서버) ──
@app.post("/api/sales/sync")
async def sync_sales(request: Request, conn=Depends(db)):
    """물류서버에서 일별 매출 가져와서 저장 (여러 날짜 한번에 가능)"""
    import aiohttp
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    days = body.get("days", 30)

    synced_total = 0
    errors = []

    async with aiohttp.ClientSession() as session:
        for i in range(days):
            date = (datetime.now() - timedelta(days=i + 1)).strftime("%Y-%m-%d")

            existing_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM sales WHERE sale_date=?", (date,)
            ).fetchone()["cnt"]
            if existing_count > 0:
                continue

            try:
                async with session.get(f"{LOGISTICS_URL}/api/sales-daily-orders?date={date}") as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()

                orders = data.get("by_option", [])
                if not orders:
                    continue

                for order in orders:
                    code = order.get("code", "")
                    product_name = order.get("nameOpt") or order.get("name", "")
                    total_qty = order.get("qty", 0)
                    total_settlement = order.get("settlement", 0)

                    product = conn.execute(
                        "SELECT id FROM products WHERE product_code=? OR ezadmin_code=?", (code, code)
                    ).fetchone()
                    product_id = product["id"] if product else None

                    channels = order.get("channels", {})
                    for ch_name, ch_data in channels.items():
                        ch_qty = ch_data.get("qty", 0)
                        ch_settlement = ch_data.get("settlement", 0)
                        if ch_qty == 0 and ch_settlement == 0:
                            continue

                        supply = round(ch_settlement / 1.1)
                        tax = ch_settlement - supply

                        partner = conn.execute(
                            "SELECT id FROM partners WHERE name=?", (ch_name,)
                        ).fetchone()
                        partner_id = partner["id"] if partner else None

                        cur = conn.execute(
                            """INSERT INTO sales (sale_date, partner_id, channel, channel_order_no,
                               total_supply, total_tax, total_amount, status, recipient)
                               VALUES (?,?,?,?,?,?,?,'confirmed',?)""",
                            (date, partner_id, ch_name, code, supply, tax, ch_settlement, product_name),
                        )
                        sale_id = cur.lastrowid
                        conn.execute(
                            """INSERT INTO sale_lines (sale_id, product_id, product_name, qty, unit_price,
                               supply_amount, tax_amount, line_total)
                               VALUES (?,?,?,?,?,?,?,?)""",
                            (sale_id, product_id, product_name, ch_qty,
                             round(ch_settlement / ch_qty) if ch_qty else 0,
                             supply, tax, ch_settlement),
                        )
                        synced_total += 1

                conn.commit()
            except Exception as e:
                errors.append(f"{date}: {str(e)}")

    return {"synced": synced_total, "days": days, "errors": errors[:5]}


@app.post("/api/sales/resync")
async def resync_sales(request: Request, conn=Depends(db)):
    """특정 기간 매출 재동기화 (날짜별 멱등: 원본에 데이터 있는 날만 삭제 후 재입력).
    ⚠️ 과거엔 기간을 통째로 먼저 삭제했는데, 그러면 물류서버가 일시 장애로 빈응답일 때
    그 날짜 매출이 0으로 날아갔음. → 날짜별로 '원본 데이터 있을 때만' 삭제하도록 변경.
    덕분에 최근 7일 등 넓은 윈도우로 매일 돌려도 안전 (취소/환불/지연주문 매일 보정)."""
    import aiohttp
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    date_from = body.get("date_from", "2026-01-01")
    date_to = body.get("date_to", datetime.now().strftime("%Y-%m-%d"))

    deleted_total = 0
    synced_total = 0
    errors = []
    current = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d")

    async with aiohttp.ClientSession() as session:
        while current <= end:
            date = current.strftime("%Y-%m-%d")
            current += timedelta(days=1)
            try:
                async with session.get(f"{LOGISTICS_URL}/api/sales-daily-orders?date={date}") as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                orders = data.get("by_option", [])
                if not orders:
                    continue  # 빈응답 → 기존 데이터 보존 (삭제 안 함)
                # ⚠️ 이지어드민이 제공하는 채널만 삭제/재입력 — 로켓1P(쿠팡 로켓배송)·그로스 등
                # 다른 소스로 별도 적재한 매출은 보존해야 함. 과거엔 sale_date 전체를 삭제해
                # 로켓·그로스 매출이 날아가는 버그가 있었음(2026-06-29).
                ez_channels = {ch for o in orders for ch in o.get("channels", {})}
                if not ez_channels:
                    continue
                ph = ",".join("?" * len(ez_channels))
                params = [date, *ez_channels]
                deleted_total += conn.execute(
                    f"SELECT COUNT(*) as cnt FROM sales WHERE sale_date=? AND channel IN ({ph})", params
                ).fetchone()["cnt"]
                conn.execute(
                    f"DELETE FROM sale_lines WHERE sale_id IN "
                    f"(SELECT id FROM sales WHERE sale_date=? AND channel IN ({ph}))", params)
                conn.execute(f"DELETE FROM sales WHERE sale_date=? AND channel IN ({ph})", params)
                for order in orders:
                    code = order.get("code", "")
                    product_name = order.get("nameOpt") or order.get("name", "")
                    channels = order.get("channels", {})
                    product = conn.execute(
                        "SELECT id FROM products WHERE product_code=? OR ezadmin_code=?", (code, code)
                    ).fetchone()
                    product_id = product["id"] if product else None
                    for ch_name, ch_data in channels.items():
                        ch_qty = ch_data.get("qty", 0)
                        ch_settlement = ch_data.get("settlement", 0)
                        if ch_qty == 0 and ch_settlement == 0:
                            continue
                        supply = round(ch_settlement / 1.1)
                        tax = ch_settlement - supply
                        partner = conn.execute("SELECT id FROM partners WHERE name=?", (ch_name,)).fetchone()
                        partner_id = partner["id"] if partner else None
                        cur = conn.execute(
                            """INSERT INTO sales (sale_date, partner_id, channel, channel_order_no,
                               total_supply, total_tax, total_amount, status, recipient)
                               VALUES (?,?,?,?,?,?,?,'confirmed',?)""",
                            (date, partner_id, ch_name, code, supply, tax, ch_settlement, product_name))
                        sale_id = cur.lastrowid
                        conn.execute(
                            """INSERT INTO sale_lines (sale_id, product_id, product_name, qty, unit_price,
                               supply_amount, tax_amount, line_total)
                               VALUES (?,?,?,?,?,?,?,?)""",
                            (sale_id, product_id, product_name, ch_qty,
                             round(ch_settlement / ch_qty) if ch_qty else 0, supply, tax, ch_settlement))
                        synced_total += 1
                conn.commit()
            except Exception as e:
                errors.append(f"{date}: {str(e)}")

    return {"deleted": deleted_total, "synced": synced_total, "date_from": date_from, "date_to": date_to,
            "errors": errors[:5]}


# ── 매출 자동 동기화 (서버 시작 시 백그라운드 스케줄러) ──
import asyncio
import threading

async def _sync_sales_day(conn, session, date):
    """원본에서 하루치 매출을 받아 해당 날짜를 삭제 후 재삽입 (멱등). 향(nameOpt) 보존."""
    async with session.get(f"{LOGISTICS_URL}/api/sales-daily-orders?date={date}") as resp:
        if resp.status != 200:
            return 0
        data = await resp.json()
    orders = data.get("by_option", [])
    if not orders:
        return 0
    # 멱등: 이지어드민이 제공하는 채널만 삭제 후 재삽입 (로켓1P·그로스 등 타 소스 보존).
    # ⚠️ 과거엔 sale_date 전체를 삭제해 로켓·그로스 매출이 날아갔음(2026-06-29).
    ez_channels = {ch for o in orders for ch in o.get("channels", {})}
    if not ez_channels:
        return 0
    ph = ",".join("?" * len(ez_channels))
    params = [date, *ez_channels]
    conn.execute(
        f"DELETE FROM sale_lines WHERE sale_id IN "
        f"(SELECT id FROM sales WHERE sale_date=? AND channel IN ({ph}))", params)
    conn.execute(f"DELETE FROM sales WHERE sale_date=? AND channel IN ({ph})", params)
    synced = 0
    for order in orders:
        code = order.get("code", "")
        product_name = order.get("nameOpt") or order.get("name", "")  # 향 보존
        channels = order.get("channels", {})
        product = conn.execute("SELECT id FROM products WHERE product_code=? OR ezadmin_code=?", (code, code)).fetchone()
        product_id = product["id"] if product else None
        for ch_name, ch_data in channels.items():
            ch_qty = ch_data.get("qty", 0)
            ch_settlement = ch_data.get("settlement", 0)
            if ch_qty == 0 and ch_settlement == 0:
                continue
            supply = round(ch_settlement / 1.1)
            tax = ch_settlement - supply
            partner = conn.execute("SELECT id FROM partners WHERE name=?", (ch_name,)).fetchone()
            partner_id = partner["id"] if partner else None
            cur = conn.execute(
                """INSERT INTO sales (sale_date, partner_id, channel, channel_order_no,
                   total_supply, total_tax, total_amount, status, recipient)
                   VALUES (?,?,?,?,?,?,?,'confirmed',?)""",
                (date, partner_id, ch_name, code, supply, tax, ch_settlement, product_name))
            sale_id = cur.lastrowid
            conn.execute(
                """INSERT INTO sale_lines (sale_id, product_id, product_name, qty, unit_price,
                   supply_amount, tax_amount, line_total)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (sale_id, product_id, product_name, ch_qty,
                 round(ch_settlement / ch_qty) if ch_qty else 0, supply, tax, ch_settlement))
            synced += 1
    conn.commit()
    return synced


async def _auto_sync_sales():
    """매일 09:30에 최근 10일 매출 재동기화 (물류 9:00 수집 직후 → 전일 매출 완전 반영)"""
    import aiohttp
    while True:
        now = datetime.now()
        target = (now + timedelta(days=1)).replace(hour=9, minute=30, second=0, microsecond=0)
        if now.hour < 9 or (now.hour == 9 and now.minute < 30):
            target = now.replace(hour=9, minute=30, second=0, microsecond=0)
        wait_sec = (target - now).total_seconds()
        await asyncio.sleep(wait_sec)

        try:
            conn = get_db()
            async with aiohttp.ClientSession() as session:
                for i in range(1, 11):  # 어제 ~ 10일 전 재동기화
                    date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                    try:
                        await _sync_sales_day(conn, session, date)
                    except Exception:
                        pass
            conn.close()
        except Exception:
            pass


async def _auto_sync_stock():
    """매일 10:30 (물류서버 이지어드민 수집 10:00 직후) 재고 자동 동기화"""
    import aiohttp
    while True:
        now = datetime.now()
        target = now.replace(hour=10, minute=30, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{LOGISTICS_URL}/api/cached-data") as resp:
                    payload = await resp.json() if resp.status == 200 else {}
            inventory = (payload.get("data") or payload).get("inventory", {})
            if inventory:
                conn = get_db()
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for code, info in inventory.items():
                    qty = info.get("stock", 0)
                    product = conn.execute(
                        "SELECT id FROM products WHERE product_code=? OR ezadmin_code=?", (code, code)).fetchone()
                    if not product:
                        continue
                    ex = conn.execute("SELECT id, qty_on_hand FROM stock WHERE product_id=?", (product["id"],)).fetchone()
                    if ex:
                        if ex["qty_on_hand"] != qty:
                            conn.execute(
                                "UPDATE stock SET qty_on_hand=?, last_synced_at=?, updated_at=datetime('now','localtime') WHERE product_id=?",
                                (qty, now, product["id"]))
                            conn.execute(
                                """INSERT INTO stock_transactions (product_id, tx_type, qty_change, qty_before, qty_after, ref_type, memo)
                                   VALUES (?, 'adjust', ?, ?, ?, 'sync', '자동 동기화')""",
                                (product["id"], qty - ex["qty_on_hand"], ex["qty_on_hand"], qty))
                        else:
                            conn.execute("UPDATE stock SET last_synced_at=? WHERE product_id=?", (now, product["id"]))
                    else:
                        conn.execute("INSERT INTO stock (product_id, qty_on_hand, last_synced_at) VALUES (?,?,?)",
                                     (product["id"], qty, now))
                conn.commit()
                conn.close()
        except Exception:
            pass


@app.on_event("startup")
async def start_auto_sync():
    asyncio.create_task(_auto_sync_sales())
    asyncio.create_task(_auto_sync_stock())


# 이 월(포함)까지는 "완전 정산월" = settlement_monthly만 사용 (기존 동작 보존).
# 이후 월은 "채널별 정산" = 정산 있는 채널은 settlement, 나머지는 이지어드민+보정.
# (로켓그로스 등 일부 채널만 정산되는 부분정산월 대응)
FULLY_SETTLED_THROUGH = "2026-04"

# 정산 채널명 ↔ 이지어드민 채널명 별칭 (정산 있으면 같은 이지어드민 채널은 중복계상 방지로 스킵)
SETTLEMENT_EZADMIN_ALIAS = {
    "쿠팡 그로스": ["채움컴퍼니", "비코어랩 쿠팡 채움(자동)"],
    "쿠팡(로켓배송)": ["쿠팡 로켓배송"],
    "스마트스토어": ["비코어랩 일비아 스스"],
    "지마켓": ["비코어랩 G마켓"],
    "11번가": ["비코어랩 11번가"],
    "옥션": ["비코어랩 옥션"],
    "오늘의집": ["비코어랩 오늘의집"],
    "신세계몰 (에스에스지닷컴)": ["비코어랩 신세계"],
    "GS샵": ["비코어랩 GS샵"],
    "쿠팡": ["비코어랩 쿠팡(자동)"],
    "에이블리": ["비코어랩 에이블리"],
}

# ── 채널별 보정계수 (DEPRECATED 2026-06-29) ──
# [폐기 이유] 과거엔 이지어드민 집계가 부정확(DS00 그리드 4~7배 중복 합산·발주일 기준·
#   취소 미반영)해서, 정산 대비 평균계수를 사후에 곱해 땜질했음.
#   2026-06-29 scrape_sales를 "완전동일행 dedup + 정산금액(supply) + 주문일(order_id 8자리)"
#   로 교정 → 주력채널 집계가 정산과 ±4% 일치(스스 -3%/카페24 +4%). 여기에 계수까지 곱하면
#   이중집계가 됨. 그래서 전부 1.0(무보정)으로 비움. (정산 확정월은 settlement_monthly 사용)
# ⚠️ 계수가 컸던 채널(G마켓 2.32·옥션 1.57·11번가 1.04↑·신세계 0.87)은 이지어드민의
#   "구조적 과소/과대 수집"을 가려온 것 → 계수 제거 시 그 편차가 노출됨. 수집 자체 점검 필요(별도).
# 기존값 보존: 카페24 0.86 / 스스 1.11 / 11번가 1.04 / G마켓 2.32 / 옥션 1.57 / 신세계 0.87 / GS샵 0.89
CHANNEL_ADJUSTMENT = {}  # .get(ch, 1.0) → 전 채널 무보정


def _calc_sales_total(conn, date_from: str, date_to: str):
    """정산 확정월은 settlement_monthly, 미확정월은 이지어드민+보정계수로 합산"""
    if not date_from or not date_to:
        return 0, 0
    start_ym = date_from[:7]
    end_ym = date_to[:7]

    settled_set = set()
    settled_rows = conn.execute(
        "SELECT DISTINCT year_month FROM settlement_monthly WHERE year_month BETWEEN ? AND ?",
        (start_ym, end_ym),
    ).fetchall()
    for r in settled_rows:
        settled_set.add(r["year_month"])

    total_amount = 0
    total_supply = 0

    cur = datetime.strptime(date_from[:7] + "-01", "%Y-%m-%d")
    end_dt = datetime.strptime(date_to[:7] + "-01", "%Y-%m-%d")
    while cur <= end_dt:
        ym = cur.strftime("%Y-%m")
        m_start = f"{ym}-01"
        if cur.month == 12:
            nxt = cur.replace(year=cur.year + 1, month=1)
        else:
            nxt = cur.replace(month=cur.month + 1)
        m_end = (nxt - timedelta(days=1)).strftime("%Y-%m-%d")
        actual_start = max(date_from, m_start)
        actual_end = min(date_to, m_end)
        full_month = (actual_start == m_start and actual_end == m_end)

        use_settlement_only = (ym <= FULLY_SETTLED_THROUGH and ym in settled_set and full_month)
        settled_ch = set()
        if ym in settled_set and full_month:
            for r in conn.execute(
                "SELECT channel, amount FROM settlement_monthly WHERE year_month=?", (ym,)
            ).fetchall():
                settled_ch.add(r["channel"])
                total_amount += r["amount"]
                total_supply += round(r["amount"] / 1.1)
        for _sc in list(settled_ch):
            settled_ch.update(SETTLEMENT_EZADMIN_ALIAS.get(_sc, []))
        if not use_settlement_only:
            # 부분 정산월: 정산 안 된 채널만 이지어드민+보정으로 채움
            ch_sums = conn.execute(
                "SELECT channel, SUM(total_amount) as t, SUM(total_supply) as s FROM sales WHERE sale_date>=? AND sale_date<=? GROUP BY channel",
                (actual_start, actual_end),
            ).fetchall()
            for r in ch_sums:
                if r["channel"] in settled_ch:
                    continue
                factor = CHANNEL_ADJUSTMENT.get(r["channel"], 1.0)
                total_amount += round(r["t"] * factor)
                total_supply += round(r["s"] * factor)

        cur = nxt

    return total_amount, total_supply


def _get_summary_by_channel(conn, date_from: str, date_to: str):
    """채널별 요약 — 정산 확정월은 settlement, 미확정은 이지어드민+보정"""
    if not date_from or not date_to:
        return []
    start_ym = date_from[:7]
    end_ym = date_to[:7]

    settled_set = set()
    settled_rows = conn.execute(
        "SELECT DISTINCT year_month FROM settlement_monthly WHERE year_month BETWEEN ? AND ?",
        (start_ym, end_ym),
    ).fetchall()
    for r in settled_rows:
        settled_set.add(r["year_month"])

    ch_totals = {}

    cur = datetime.strptime(date_from[:7] + "-01", "%Y-%m-%d")
    end_dt = datetime.strptime(date_to[:7] + "-01", "%Y-%m-%d")
    while cur <= end_dt:
        ym = cur.strftime("%Y-%m")
        m_start = f"{ym}-01"
        if cur.month == 12:
            nxt = cur.replace(year=cur.year + 1, month=1)
        else:
            nxt = cur.replace(month=cur.month + 1)
        m_end = (nxt - timedelta(days=1)).strftime("%Y-%m-%d")
        actual_start = max(date_from, m_start)
        actual_end = min(date_to, m_end)
        full_month = (actual_start == m_start and actual_end == m_end)

        use_settlement_only = (ym <= FULLY_SETTLED_THROUGH and ym in settled_set and full_month)
        settled_ch = set()
        if ym in settled_set and full_month:
            rows = conn.execute(
                "SELECT channel, amount FROM settlement_monthly WHERE year_month=?", (ym,)
            ).fetchall()
            for r in rows:
                ch = r["channel"]
                settled_ch.add(ch)
                if ch not in ch_totals:
                    ch_totals[ch] = {"label": ch, "supply": 0, "tax": 0, "total": 0, "cnt": 0, "qty": 0}
                ch_totals[ch]["total"] += r["amount"]
                ch_totals[ch]["supply"] += round(r["amount"] / 1.1)
                ch_totals[ch]["tax"] += r["amount"] - round(r["amount"] / 1.1)
        for _sc in list(settled_ch):
            settled_ch.update(SETTLEMENT_EZADMIN_ALIAS.get(_sc, []))
        if not use_settlement_only:
            rows = conn.execute(
                """SELECT s.channel, COUNT(DISTINCT s.id) as cnt, SUM(s.total_supply) as supply,
                   SUM(s.total_tax) as tax, SUM(s.total_amount) as total
                   FROM sales s WHERE s.status='confirmed' AND s.sale_date>=? AND s.sale_date<=?
                   GROUP BY s.channel""",
                (actual_start, actual_end),
            ).fetchall()
            for r in rows:
                ch = r["channel"]
                if ch in settled_ch:
                    continue
                factor = CHANNEL_ADJUSTMENT.get(ch, 1.0)
                if ch not in ch_totals:
                    ch_totals[ch] = {"label": ch, "supply": 0, "tax": 0, "total": 0, "cnt": 0, "qty": 0}
                ch_totals[ch]["total"] += round(r["total"] * factor)
                ch_totals[ch]["supply"] += round(r["supply"] * factor)
                ch_totals[ch]["tax"] += round(r["tax"] * factor)
                ch_totals[ch]["cnt"] += r["cnt"]

        cur = nxt

    return sorted(ch_totals.values(), key=lambda x: -x["total"])


@app.post("/api/sales/sync-supplyhub")
async def sync_supplyhub(request: Request, conn=Depends(db)):
    """서플라이허브 데이터를 ERP에 동기화 (쿠팡 로켓배송 채널)"""
    import aiohttp
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    date_from = body.get("date_from", (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))
    date_to = body.get("date_to", date_from)

    deleted = conn.execute(
        "SELECT COUNT(*) cnt FROM sales WHERE sale_date BETWEEN ? AND ? AND channel='쿠팡 로켓배송'",
        (date_from, date_to),
    ).fetchone()["cnt"]
    conn.execute(
        "DELETE FROM sale_lines WHERE sale_id IN "
        "(SELECT id FROM sales WHERE sale_date BETWEEN ? AND ? AND channel='쿠팡 로켓배송')",
        (date_from, date_to),
    )
    conn.execute(
        "DELETE FROM sales WHERE sale_date BETWEEN ? AND ? AND channel='쿠팡 로켓배송'",
        (date_from, date_to),
    )
    conn.commit()

    synced = 0
    errors = []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{LOGISTICS_URL}/api/supplyhub-data",
                params={"date_from": date_from, "date_to": date_to},
            ) as resp:
                if resp.status != 200:
                    return {"error": f"물류서버 응답 오류: {resp.status}"}
                data = await resp.json()

        items = data.get("items", [])
        date_groups = {}
        for item in items:
            d = item.get("입고/반출일자", "")[:10]
            if d < date_from or d > date_to:
                continue
            if d not in date_groups:
                date_groups[d] = []
            date_groups[d].append(item)

        partner = conn.execute("SELECT id FROM partners WHERE name LIKE '%쿠팡%로켓%'").fetchone()
        if not partner:
            cur = conn.execute(
                "INSERT INTO partners (name, business_no) VALUES ('쿠팡 로켓배송', '')"
            )
            partner_id = cur.lastrowid
        else:
            partner_id = partner["id"]

        for sale_date, day_items in date_groups.items():
            for item in day_items:
                sku_name = item.get("SKU명", "")
                qty = int(str(item.get("수량", "0")).replace(",", "") or 0)
                total_unit = int(str(item.get("총단가", "0")).replace(",", "") or 0)
                supply = int(str(item.get("총공급가액", "0")).replace(",", "") or 0)
                vat = int(str(item.get("총세액", "0")).replace(",", "") or 0)
                sku_no = item.get("SKU번호", "")

                cur = conn.execute(
                    """INSERT INTO sales (sale_date, partner_id, channel, channel_order_no,
                       total_supply, total_tax, total_amount, status, recipient, source)
                       VALUES (?,?,'쿠팡 로켓배송',?,?,?,?,'confirmed',?,'supplyhub')""",
                    (sale_date, partner_id, sku_no, supply, vat, total_unit, sku_name),
                )
                sale_id = cur.lastrowid

                product = conn.execute(
                    "SELECT id FROM products WHERE product_code=? OR ezadmin_code=?",
                    (sku_no, sku_no),
                ).fetchone()
                product_id = product["id"] if product else None

                unit_price = round(total_unit / qty) if qty else 0
                conn.execute(
                    """INSERT INTO sale_lines (sale_id, product_id, product_name, qty, unit_price,
                       supply_amount, tax_amount, line_total)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (sale_id, product_id, sku_name, qty, unit_price, supply, vat, total_unit),
                )
                synced += 1

        conn.commit()
    except Exception as e:
        errors.append(str(e))

    return {
        "deleted": deleted, "synced": synced,
        "date_from": date_from, "date_to": date_to,
        "errors": errors[:5],
    }


@app.post("/api/sales/confirm-monthly")
async def confirm_monthly_sales(request: Request, conn=Depends(db)):
    """월말 정산 확정 — 잠정매출을 확정 데이터로 덮어쓰기"""
    body = await request.json()
    month = body.get("month")
    channel = body.get("channel")
    confirmed_amount = body.get("confirmed_amount")

    if not month or not channel:
        return {"error": "month와 channel 필수"}

    date_from = f"{month}-01"
    y, m = month.split("-")
    if int(m) == 12:
        date_to = f"{int(y)+1}-01-01"
    else:
        date_to = f"{y}-{int(m)+1:02d}-01"

    current = conn.execute(
        """SELECT SUM(total_amount) amount FROM sales
           WHERE sale_date >= ? AND sale_date < ? AND channel=?""",
        (date_from, date_to, channel),
    ).fetchone()
    current_amount = current["amount"] or 0

    return {
        "month": month, "channel": channel,
        "current_amount": current_amount,
        "confirmed_amount": confirmed_amount,
        "difference": confirmed_amount - current_amount if confirmed_amount else None,
        "note": "월말 확정 기능은 정산 하치와 연동하여 구현 예정",
    }


# ── 발주 CRUD ──
@app.get("/api/purchase-orders")
async def list_po(
    status: str = "", supplier_id: int = 0, q: str = "",
    date_from: str = "", date_to: str = "",
    sort: str = "date_desc",
    page: int = 1, size: int = 50, conn=Depends(db)
):
    where, params = ["1=1"], []
    if status:
        where.append("po.status=?")
        params.append(status)
    if supplier_id:
        where.append("po.supplier_id=?")
        params.append(supplier_id)
    if q:
        where.append("(sup.name LIKE ? OR po.po_number LIKE ?)")
        params += [f"%{q}%"] * 2
    if date_from:
        where.append("po.po_date>=?")
        params.append(date_from)
    if date_to:
        where.append("po.po_date<=?")
        params.append(date_to)
    w = " AND ".join(where)
    sort_map = {
        "date_desc": "po.po_date DESC",
        "date_asc": "po.po_date ASC",
        "amount_desc": "po.total_amount DESC",
        "amount_asc": "po.total_amount ASC",
        "supplier": "sup.name ASC, po.po_date DESC",
    }
    order_clause = sort_map.get(sort, "po.po_date DESC")
    total = conn.execute(
        f"SELECT COUNT(*) as cnt FROM purchase_orders po LEFT JOIN partners sup ON sup.id=po.supplier_id WHERE {w}", params
    ).fetchone()["cnt"]
    sum_row = conn.execute(
        f"SELECT COALESCE(SUM(po.total_amount),0) as sum_amount FROM purchase_orders po LEFT JOIN partners sup ON sup.id=po.supplier_id WHERE {w}", params
    ).fetchone()
    rows = conn.execute(
        f"""SELECT po.*, sup.name as supplier_name,
            (SELECT GROUP_CONCAT(pol.product_name, ' / ')
             FROM purchase_order_lines pol WHERE pol.po_id=po.id) as items_summary
            FROM purchase_orders po LEFT JOIN partners sup ON sup.id=po.supplier_id
            WHERE {w} ORDER BY {order_clause} LIMIT ? OFFSET ?""",
        params + [size, (page - 1) * size],
    ).fetchall()
    items = [dict(r) for r in rows]
    # 발주 총수량: 같은 품목(옵션/공정 [] 제거한 base)은 최대 수량만 합산 → 공정형(같은 용기를
    # 성형·코팅·인쇄 3줄로 입력) 중복 합산 방지. 예) 용기 5,000개 ×3공정 → 15,000이 아닌 5,000.
    if items:
        import re as _re
        from collections import defaultdict as _dd
        po_ids = [it["id"] for it in items]
        ph = ",".join("?" * len(po_ids))
        lines = conn.execute(
            f"SELECT po_id, product_name, qty_ordered FROM purchase_order_lines WHERE po_id IN ({ph})",
            po_ids,
        ).fetchall()
        grp = _dd(lambda: _dd(int))
        for ln in lines:
            b = _re.sub(r"\s*\[[^\]]*\]\s*$", "", ln["product_name"] or "").strip()
            grp[ln["po_id"]][b] = max(grp[ln["po_id"]][b], ln["qty_ordered"] or 0)
        for it in items:
            it["total_qty"] = sum(grp.get(it["id"], {}).values())
    return {"items": items, "total": total, "page": page, "size": size, "sum_amount": sum_row["sum_amount"]}


@app.get("/api/purchase-orders/{po_id}")
async def get_po(po_id: int, conn=Depends(db)):
    po = conn.execute(
        """SELECT po.*, sup.name as supplier_name, sup.email as supplier_email, sup.phone as supplier_phone
           FROM purchase_orders po LEFT JOIN partners sup ON sup.id=po.supplier_id WHERE po.id=?""",
        (po_id,),
    ).fetchone()
    if not po:
        raise HTTPException(404, "발주서를 찾을 수 없습니다")
    lines = conn.execute(
        """SELECT pol.*, p.product_code, p.name as product_name_ref
           FROM purchase_order_lines pol LEFT JOIN products p ON p.id=pol.product_id
           WHERE pol.po_id=?""",
        (po_id,),
    ).fetchall()
    return {"po": dict(po), "lines": [dict(l) for l in lines]}


@app.post("/api/purchase-orders")
async def create_po(request: Request, conn=Depends(db)):
    d = await request.json()
    po_number = d.get("po_number") or f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    cur = conn.execute(
        """INSERT INTO purchase_orders (po_number, po_date, supplier_id, delivery_date,
           total_amount, status, memo, created_by)
           VALUES (?,?,?,?,?,?,?,?)""",
        (po_number, d["po_date"], d["supplier_id"], d.get("delivery_date"),
         d.get("total_amount", 0), d.get("status", "draft"), d.get("memo"), d.get("created_by")),
    )
    po_id = cur.lastrowid
    total = 0
    for line in d.get("lines", []):
        amount = line.get("qty_ordered", 0) * line.get("unit_price", 0)
        total += amount
        conn.execute(
            """INSERT INTO purchase_order_lines (po_id, product_id, product_name, qty_ordered, unit_price, amount)
               VALUES (?,?,?,?,?,?)""",
            (po_id, line["product_id"], line.get("product_name"), line["qty_ordered"],
             line.get("unit_price", 0), amount),
        )
    conn.execute("UPDATE purchase_orders SET total_amount=? WHERE id=?", (total, po_id))
    conn.commit()
    return {"id": po_id, "po_number": po_number}


@app.put("/api/purchase-orders/{po_id}")
async def update_po(po_id: int, request: Request, conn=Depends(db)):
    d = await request.json()
    status = d.get("status")
    if status is None:  # 상태 미지정 시 기존 상태 유지 (수정 시 status 날아가는 것 방지)
        row = conn.execute("SELECT status FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
        status = row["status"] if row else "draft"
    conn.execute(
        """UPDATE purchase_orders SET po_date=?, supplier_id=?, delivery_date=?,
           status=?, memo=?, updated_at=datetime('now','localtime') WHERE id=?""",
        (d.get("po_date"), d.get("supplier_id"), d.get("delivery_date"),
         status, d.get("memo"), po_id),
    )
    if "lines" in d:
        conn.execute("DELETE FROM purchase_order_lines WHERE po_id=?", (po_id,))
        total = 0
        for line in d["lines"]:
            amount = line.get("qty_ordered", 0) * line.get("unit_price", 0)
            total += amount
            conn.execute(
                """INSERT INTO purchase_order_lines (po_id, product_id, product_name, qty_ordered, unit_price, amount)
                   VALUES (?,?,?,?,?,?)""",
                (po_id, line["product_id"], line.get("product_name"), line["qty_ordered"],
                 line.get("unit_price", 0), amount),
            )
        conn.execute("UPDATE purchase_orders SET total_amount=? WHERE id=?", (total, po_id))
    conn.commit()
    return {"ok": True}


@app.put("/api/purchase-orders/{po_id}/status")
async def update_po_status(po_id: int, request: Request, conn=Depends(db)):
    d = await request.json()
    conn.execute(
        "UPDATE purchase_orders SET status=?, updated_at=datetime('now','localtime') WHERE id=?",
        (d["status"], po_id),
    )
    conn.commit()
    return {"ok": True}


@app.post("/api/purchase-orders/{po_id}/copy")
async def copy_po(po_id: int, conn=Depends(db)):
    po = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
    if not po:
        raise HTTPException(404, "발주서를 찾을 수 없습니다")
    new_number = f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    today = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        """INSERT INTO purchase_orders (po_number, po_date, supplier_id, delivery_date,
           total_amount, status, memo, created_by)
           VALUES (?,?,?,?,?,?,?,?)""",
        (new_number, today, po["supplier_id"], None, po["total_amount"], "draft",
         f"[복사] {po['po_number']}", po["created_by"]),
    )
    new_id = cur.lastrowid
    lines = conn.execute("SELECT * FROM purchase_order_lines WHERE po_id=?", (po_id,)).fetchall()
    for l in lines:
        conn.execute(
            """INSERT INTO purchase_order_lines (po_id, product_id, product_name, qty_ordered, unit_price, amount)
               VALUES (?,?,?,?,?,?)""",
            (new_id, l["product_id"], l["product_name"], l["qty_ordered"], l["unit_price"], l["amount"]),
        )
    conn.commit()
    return {"id": new_id, "po_number": new_number}


@app.get("/api/purchase-orders/{po_id}/pdf")
async def download_po_pdf(po_id: int, conn=Depends(db)):
    from fastapi.responses import Response
    from fpdf import FPDF

    po_row = conn.execute(
        """SELECT po.*, sup.name as supplier_name, sup.phone as supplier_phone,
           sup.business_no as supplier_biz_no, sup.ceo_name as supplier_ceo
           FROM purchase_orders po LEFT JOIN partners sup ON sup.id=po.supplier_id WHERE po.id=?""",
        (po_id,),
    ).fetchone()
    if not po_row:
        raise HTTPException(404, "발주서를 찾을 수 없습니다")
    po = dict(po_row)
    lines_raw = conn.execute(
        """SELECT pol.*, p.product_code, p.unit FROM purchase_order_lines pol
           LEFT JOIN products p ON p.id=pol.product_id WHERE pol.po_id=?""",
        (po_id,),
    ).fetchall()
    lines = [dict(l) for l in lines_raw]

    total_qty = sum(l["qty_ordered"] for l in lines)
    total_supply = sum(l["amount"] for l in lines)
    total_vat = round(total_supply * 0.1)
    total_with_vat = total_supply + total_vat

    def kr_amount(n):
        units = ["", "만", "억", "조"]
        if n == 0:
            return "영"
        n = int(n)
        result = []
        for u in units:
            n, r = divmod(n, 10000)
            if r > 0:
                result.append(f"{r:,}{u}")
            if n == 0:
                break
        return "".join(reversed(result)) + "원"

    FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("gothic", "", FONT_PATH)
    pdf.add_font("gothic", "B", FONT_PATH)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pw = pdf.w - pdf.l_margin - pdf.r_margin

    BG = (245, 240, 232)
    BORDER_C = (153, 153, 153)

    def draw_cell(x, y, w, h, txt, align="L", bold=False, bg=None, font_size=9):
        pdf.set_xy(x, y)
        if bg:
            pdf.set_fill_color(*bg)
        pdf.set_draw_color(*BORDER_C)
        pdf.set_font("gothic", "B" if bold else "", font_size)
        pdf.cell(w, h, txt, border=1, fill=bool(bg), align=align)

    pdf.set_font("gothic", "B", 18)
    pdf.cell(pw, 12, "발 주 서", align="C")
    pdf.ln(16)

    half = pw / 2 - 2
    y0 = pdf.get_y()
    lbl_w, val_w = 28, half - 28
    rh = 7

    left_data = [
        ("일련번호", po["po_number"]),
        ("수 신", po.get("supplier_name") or "-"),
        ("TEL", po.get("supplier_phone") or "-"),
        ("납기일자", po.get("delivery_date") or "-"),
    ]
    for i, (lbl, val) in enumerate(left_data):
        draw_cell(pdf.l_margin, y0 + i * rh, lbl_w, rh, f" {lbl}", bold=True, bg=BG, font_size=8)
        draw_cell(pdf.l_margin + lbl_w, y0 + i * rh, val_w, rh, f" {val}", font_size=9)

    rx = pdf.l_margin + half + 4
    logo_path = os.path.join(os.path.dirname(__file__), "static", "images", "becorelab_logo.png")
    if os.path.exists(logo_path):
        logo_h = 5
        logo_w = logo_h * (3147 / 718)
        pdf.image(logo_path, x=rx + half - logo_w, y=y0 - 6, w=logo_w, h=logo_h)

    right_data = [
        ("사업자번호", "483-81-01727"),
        ("회사명/대표", "주식회사 비코어랩 / 정건양"),
        ("주 소", "서울 성동구 아차산로17길 48, 1104호"),
        ("담당/연락처", "정건양 / 070-8894-1716"),
    ]
    rlbl_w = 25
    rval_w = half - rlbl_w
    for i, (lbl, val) in enumerate(right_data):
        draw_cell(rx, y0 + i * rh, rlbl_w, rh, f" {lbl}", bold=True, bg=BG, font_size=7)
        draw_cell(rx + rlbl_w, y0 + i * rh, rval_w, rh, f" {val}", font_size=8)

    pdf.set_y(y0 + len(left_data) * rh + 4)

    pdf.set_fill_color(*BG)
    pdf.set_draw_color(*BORDER_C)
    pdf.set_font("gothic", "B", 10)
    pdf.cell(pw, 8, f"  금 액 : ₩{total_with_vat:,.0f}원 / VAT포함",
             border=1, fill=True, align="L")
    pdf.ln(10)

    cols = [
        ("품목코드", 25, "C"),
        ("품목명", pw - 25 - 20 - 25 - 30 - 25, "L"),
        ("수량", 20, "R"),
        ("단가", 25, "R"),
        ("공급가액", 30, "R"),
        ("부가세", 25, "R"),
    ]
    pdf.set_font("gothic", "B", 8)
    pdf.set_fill_color(*BG)
    for name, w, _ in cols:
        pdf.cell(w, 7, name, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("gothic", "", 8)
    for l in lines:
        unit = l.get("unit") or "EA"
        supply = l["amount"]
        vat = round(supply * 0.1)
        row_data = [
            (l.get("product_code") or "", cols[0][1], "C"),
            (l.get("product_name") or "", cols[1][1], "L"),
            (f"{l['qty_ordered']:,} {unit}", cols[2][1], "R"),
            (f"{l['unit_price']:,.0f}", cols[3][1], "R"),
            (f"{supply:,.0f}", cols[4][1], "R"),
            (f"{vat:,.0f}", cols[5][1], "R"),
        ]
        for txt, w, align in row_data:
            pdf.cell(w, 7, f" {txt} ", border=1, align=align)
        pdf.ln()

    pdf.set_font("gothic", "B", 8)
    pdf.set_fill_color(*BG)
    sum_cols = [
        ("수량", 25), (f"{total_qty:,}", 20),
        ("공급가액", 25), (f"{total_supply:,.0f}", 30),
        ("VAT", 20), (f"{total_vat:,.0f}", 25),
        ("합계", 20), (f"{total_with_vat:,.0f}", pw - 25 - 20 - 25 - 30 - 20 - 25 - 20),
    ]
    for i, (txt, w) in enumerate(sum_cols):
        pdf.cell(w, 7, f" {txt} ", border=1, fill=(i % 2 == 0), align="R" if i % 2 else "R")
    pdf.ln()

    pdf.ln(10)
    pdf.set_font("gothic", "", 8)
    pdf.set_text_color(136, 136, 136)
    pdf.cell(pw, 6, "— 주식회사 비코어랩 · info@becorelab.kr —", align="C")

    pdf_bytes = pdf.output()
    filename = f"PO_{po['po_number']}.pdf"
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/purchase-orders/{po_id}/email")
async def email_po(po_id: int, request: Request, conn=Depends(db)):
    d = await request.json()
    _to = d.get("to")
    to_list = [e for e in (_to if isinstance(_to, list) else [_to]) if e]
    if not to_list:
        raise HTTPException(400, "수신 이메일을 입력해주세요")
    cc_req = d.get("cc")
    cc_req = [e for e in cc_req if e] if isinstance(cc_req, list) else None
    po_row = conn.execute(
        """SELECT po.*, sup.name as supplier_name, sup.phone as supplier_phone, sup.email as supplier_email
           FROM purchase_orders po LEFT JOIN partners sup ON sup.id=po.supplier_id WHERE po.id=?""",
        (po_id,),
    ).fetchone()
    if not po_row:
        raise HTTPException(404, "발주서를 찾을 수 없습니다")
    po = dict(po_row)
    lines_raw = conn.execute(
        """SELECT pol.*, p.product_code, p.unit FROM purchase_order_lines pol
           LEFT JOIN products p ON p.id=pol.product_id WHERE pol.po_id=?""",
        (po_id,),
    ).fetchall()
    lines = [dict(l) for l in lines_raw]

    cc_list = []
    if po.get("supplier_id"):
        contacts = conn.execute(
            "SELECT name, email, contact_type FROM partner_contacts WHERE partner_id=? AND is_active=1 ORDER BY contact_type",
            (po["supplier_id"],),
        ).fetchall()
        cc_list = [dict(c) for c in contacts]

    import smtplib
    from email.mime.text import MIMEText

    total_qty = sum(l["qty_ordered"] for l in lines)
    total_supply = sum(l["amount"] for l in lines)
    total_vat = round(total_supply * 0.1)
    total_with_vat = total_supply + total_vat

    def kr_amount(n):
        units = ["", "만", "억", "조"]
        if n == 0:
            return "영"
        n = int(n)
        result = []
        for u in units:
            n, r = divmod(n, 10000)
            if r > 0:
                result.append(f"{r:,}{u}")
            if n == 0:
                break
        return "".join(reversed(result)) + "원"

    rows_html = ""
    for l in lines:
        unit = l.get("unit") or "EA"
        supply = l["amount"]
        vat = round(supply * 0.1)
        rows_html += f"""<tr>
            <td style="border:1px solid #999;padding:6px 8px;font-size:12px">{l.get('product_code') or ''}</td>
            <td style="border:1px solid #999;padding:6px 8px;font-size:12px">{l.get('product_name') or ''}</td>
            <td style="border:1px solid #999;padding:6px 8px;text-align:right;font-size:12px">{l['qty_ordered']:,}<br><span style="color:#666;font-size:10px">{unit}</span></td>
            <td style="border:1px solid #999;padding:6px 8px;text-align:right;font-size:12px">{l['unit_price']:,.0f}</td>
            <td style="border:1px solid #999;padding:6px 8px;text-align:right;font-size:12px">{supply:,.0f}</td>
            <td style="border:1px solid #999;padding:6px 8px;text-align:right;font-size:12px">{vat:,.0f}</td>
        </tr>"""

    body = f"""<html><body style="font-family:'Malgun Gothic','맑은 고딕',sans-serif;color:#333;max-width:700px;margin:0 auto">
<h2 style="text-align:center;border-bottom:2px solid #333;padding-bottom:8px;margin-bottom:16px">발 주 서</h2>
<table style="width:100%;border-collapse:collapse;margin-bottom:12px">
<tr>
  <td style="width:50%;vertical-align:top">
    <table style="width:100%;border-collapse:collapse;border:1px solid #999">
      <tr><td style="border:1px solid #999;padding:4px 8px;background:#f5f0e8;font-weight:bold;width:80px;font-size:12px">일련번호</td>
          <td style="border:1px solid #999;padding:4px 8px;font-size:12px">{po['po_number']}</td></tr>
      <tr><td style="border:1px solid #999;padding:4px 8px;background:#f5f0e8;font-weight:bold;font-size:12px">수 신</td>
          <td style="border:1px solid #999;padding:4px 8px;font-size:12px">{po.get('supplier_name') or '-'}</td></tr>
      <tr><td style="border:1px solid #999;padding:4px 8px;background:#f5f0e8;font-weight:bold;font-size:12px">TEL</td>
          <td style="border:1px solid #999;padding:4px 8px;font-size:12px">{po.get('supplier_phone') or '-'}</td></tr>
      <tr><td style="border:1px solid #999;padding:4px 8px;background:#f5f0e8;font-weight:bold;font-size:12px">납기일자</td>
          <td style="border:1px solid #999;padding:4px 8px;font-size:12px">{po.get('delivery_date') or '-'}</td></tr>
    </table>
  </td>
  <td style="width:50%;vertical-align:top;padding-left:12px">
    <div style="text-align:right;margin-bottom:8px">
      <strong style="font-size:18px;letter-spacing:2px">becorelab</strong>
    </div>
    <table style="width:100%;border-collapse:collapse;border:1px solid #999">
      <tr><td style="border:1px solid #999;padding:4px 8px;background:#f5f0e8;font-weight:bold;font-size:11px;width:80px">사업자등록번호</td>
          <td style="border:1px solid #999;padding:4px 8px;font-size:12px">483-81-01727</td></tr>
      <tr><td style="border:1px solid #999;padding:4px 8px;background:#f5f0e8;font-weight:bold;font-size:11px">회사명/대표</td>
          <td style="border:1px solid #999;padding:4px 8px;font-size:12px">주식회사 비코어랩 / 정건양</td></tr>
      <tr><td style="border:1px solid #999;padding:4px 8px;background:#f5f0e8;font-weight:bold;font-size:11px">주 소</td>
          <td style="border:1px solid #999;padding:4px 8px;font-size:12px">서울특별시 성동구 아차산로17길 48, 1104호 (성수 SK V1 CENTER I)</td></tr>
      <tr><td style="border:1px solid #999;padding:4px 8px;background:#f5f0e8;font-weight:bold;font-size:11px">담당/연락처</td>
          <td style="border:1px solid #999;padding:4px 8px;font-size:12px">정건양 / 070-8894-1716</td></tr>
    </table>
  </td>
</tr>
</table>

<div style="background:#f5f0e8;padding:8px 12px;border:1px solid #999;margin-bottom:12px;font-size:13px">
  <strong>금 액 : ₩{total_with_vat:,.0f}원 / VAT포함</strong>
</div>

<table style="width:100%;border-collapse:collapse;margin-bottom:12px">
<thead>
<tr style="background:#f5f0e8">
  <th style="border:1px solid #999;padding:6px 8px;font-size:12px">품목코드</th>
  <th style="border:1px solid #999;padding:6px 8px;font-size:12px">품목명[규격]</th>
  <th style="border:1px solid #999;padding:6px 8px;font-size:12px">수량<br>(단위포함)</th>
  <th style="border:1px solid #999;padding:6px 8px;font-size:12px">단가</th>
  <th style="border:1px solid #999;padding:6px 8px;font-size:12px">공급가액</th>
  <th style="border:1px solid #999;padding:6px 8px;font-size:12px">부가세</th>
</tr>
</thead>
<tbody>{rows_html}</tbody>
</table>

<table style="width:100%;border-collapse:collapse;border:1px solid #999">
<tr style="background:#f5f0e8;font-weight:bold;font-size:12px">
  <td style="border:1px solid #999;padding:6px 8px;width:80px">수량</td>
  <td style="border:1px solid #999;padding:6px 8px;text-align:right">{total_qty:,}</td>
  <td style="border:1px solid #999;padding:6px 8px;width:80px">공급가액</td>
  <td style="border:1px solid #999;padding:6px 8px;text-align:right">{total_supply:,.0f}</td>
  <td style="border:1px solid #999;padding:6px 8px;width:50px">VAT</td>
  <td style="border:1px solid #999;padding:6px 8px;text-align:right">{total_vat:,.0f}</td>
  <td style="border:1px solid #999;padding:6px 8px;width:50px">합계</td>
  <td style="border:1px solid #999;padding:6px 8px;text-align:right;font-weight:bold">{total_with_vat:,.0f}</td>
</tr>
</table>

<p style="color:#888;margin-top:24px;font-size:11px;text-align:center">— 주식회사 비코어랩 · info@becorelab.kr —</p>
</body></html>"""

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = f"[비코어랩] 발주서 {po['po_number']}"
    msg["From"] = "info@becorelab.kr"
    msg["To"] = ", ".join(to_list)

    if cc_req is not None:
        cc_emails = cc_req
    else:
        cc_emails = [c["email"] for c in cc_list if c["contact_type"] == "cc" and c["email"]]
    cc_emails = [e for e in cc_emails if e not in to_list]  # To 중복 제거
    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)

    try:
        mail_pw = os.environ.get("NAVERWORKS_PASSWORD", "")
        if not mail_pw:
            try:
                import config as _cfg
                mail_pw = getattr(_cfg, "NAVERWORKS_PASSWORD", "")
            except Exception:
                mail_pw = ""
        if not mail_pw:
            raise HTTPException(500, "메일 비밀번호 미설정 — config.py에 NAVERWORKS_PASSWORD를 넣어주세요 (네이버웍스 SMTP 앱 비밀번호)")
        smtp = smtplib.SMTP_SSL("smtp.worksmobile.com", 465)  # 네이버웍스는 465 SSL (587 STARTTLS 아님)
        smtp.login("info@becorelab.kr", mail_pw)
        all_recipients = to_list + cc_emails
        smtp.sendmail("info@becorelab.kr", all_recipients, msg.as_string())
        smtp.quit()
    except smtplib.SMTPException as e:
        raise HTTPException(500, f"메일 발송 실패: {e}")

    conn.execute("UPDATE purchase_orders SET email_sent_at=datetime('now','localtime') WHERE id=?", (po_id,))
    conn.commit()
    return {"ok": True, "to": to_list, "cc": cc_emails}


# ── 입고 ──
@app.post("/api/receiving")
async def create_receiving(request: Request, conn=Depends(db)):
    d = await request.json()
    product_id = d["product_id"]
    qty = d["qty_received"]

    cur = conn.execute(
        """INSERT INTO receiving_records (po_id, po_line_id, product_id, recv_date, qty_received, memo, created_by)
           VALUES (?,?,?,?,?,?,?)""",
        (d.get("po_id"), d.get("po_line_id"), product_id, d["recv_date"], qty,
         d.get("memo"), d.get("created_by")),
    )

    stock = conn.execute("SELECT qty_on_hand FROM stock WHERE product_id=?", (product_id,)).fetchone()
    old_qty = stock["qty_on_hand"] if stock else 0
    new_qty = old_qty + qty

    if stock:
        conn.execute("UPDATE stock SET qty_on_hand=?, updated_at=datetime('now','localtime') WHERE product_id=?",
                     (new_qty, product_id))
    else:
        conn.execute("INSERT INTO stock (product_id, qty_on_hand) VALUES (?,?)", (product_id, new_qty))

    conn.execute(
        """INSERT INTO stock_transactions (product_id, tx_type, qty_change, qty_before, qty_after, ref_type, ref_id, memo)
           VALUES (?, 'inbound', ?, ?, ?, 'purchase_order', ?, ?)""",
        (product_id, qty, old_qty, new_qty, d.get("po_id"), d.get("memo", "입고")),
    )

    if d.get("po_line_id"):
        conn.execute(
            "UPDATE purchase_order_lines SET qty_received = qty_received + ? WHERE id=?",
            (qty, d["po_line_id"]),
        )
        po_line = conn.execute("SELECT po_id FROM purchase_order_lines WHERE id=?", (d["po_line_id"],)).fetchone()
        if po_line:
            all_lines = conn.execute(
                "SELECT qty_ordered, qty_received FROM purchase_order_lines WHERE po_id=?",
                (po_line["po_id"],),
            ).fetchall()
            if all(l["qty_received"] >= l["qty_ordered"] for l in all_lines):
                conn.execute("UPDATE purchase_orders SET status='completed' WHERE id=?", (po_line["po_id"],))
            else:
                conn.execute("UPDATE purchase_orders SET status='partial' WHERE id=?", (po_line["po_id"],))

    conn.commit()
    return {"id": cur.lastrowid, "new_qty": new_qty}


# ── 재고 이력 ──
@app.get("/api/stock/history/{product_id}")
async def stock_history(product_id: int, conn=Depends(db)):
    rows = conn.execute(
        """SELECT st.*, u.name as user_name FROM stock_transactions st
           LEFT JOIN users u ON u.id=st.created_by
           WHERE st.product_id=? ORDER BY st.created_at DESC LIMIT 100""",
        (product_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── 수불부 (매출 기반 출고량) ──
@app.get("/api/stock/sales-outbound/{product_id}")
async def stock_sales_outbound(product_id: int, days: int = 90, period: str = "daily", conn=Depends(db)):
    if period == "weekly":
        rows = conn.execute(
            """SELECT strftime('%Y-W%W', s.sale_date) as period, SUM(sl.qty) as qty,
                      SUM(sl.line_total) as amount
               FROM sale_lines sl JOIN sales s ON s.id=sl.sale_id
               WHERE sl.product_id=? AND s.status='confirmed'
               AND s.sale_date >= date('now', '-' || ? || ' days', 'localtime')
               GROUP BY period ORDER BY period DESC""",
            (product_id, days),
        ).fetchall()
        total_qty = sum(r["qty"] for r in rows)
        day_count = len(set(r["period"] for r in rows)) or 1
        return {"items": [dict(r) for r in rows], "total_qty": total_qty,
                "avg_daily": round(total_qty / min(days, day_count)) if total_qty else 0}

    # ── 일별: 출고 + 그날 입고 + 추정 재고(현재고 역산) ── (2026-07-03 대표님 요청)
    out_rows = conn.execute(
        """SELECT s.sale_date as d, SUM(sl.qty) as qty, SUM(sl.line_total) as amount
           FROM sale_lines sl JOIN sales s ON s.id=sl.sale_id
           WHERE sl.product_id=? AND s.status='confirmed'
           AND s.sale_date >= date('now', '-' || ? || ' days', 'localtime')
           GROUP BY s.sale_date""",
        (product_id, days),
    ).fetchall()
    outbound = {r["d"]: r for r in out_rows}
    # 입고 = 완료(또는 부분입고) 발주의 납품일 기준 실입고 수량
    in_rows = conn.execute(
        """SELECT po.delivery_date as d, SUM(pol.qty_received) as qty
           FROM purchase_order_lines pol JOIN purchase_orders po ON po.id=pol.po_id
           WHERE pol.product_id=? AND po.status IN ('completed','partial')
           AND pol.qty_received > 0 AND po.delivery_date IS NOT NULL
           AND po.delivery_date >= date('now', '-' || ? || ' days', 'localtime')
           GROUP BY po.delivery_date""",
        (product_id, days),
    ).fetchall()
    inbound = {r["d"]: r["qty"] for r in in_rows}

    cur = conn.execute("SELECT qty_on_hand FROM stock WHERE product_id=?", (product_id,)).fetchone()
    current_stock = cur["qty_on_hand"] if cur else None

    # 출고일 ∪ 입고일 전체를 날짜 내림차순으로 (입고만 있는 날도 표기)
    all_dates = sorted(set(outbound) | set(inbound), reverse=True)
    items, running, broke = [], current_stock, False
    for d in all_dates:
        o = outbound.get(d)
        oq = o["qty"] if o else 0
        iq = inbound.get(d, 0)
        # running = 해당일 '마감' 추정재고 (현재고에서 이후 흐름을 역산).
        # 음수가 되면 그 이전은 재고 sync 조정·누락입고로 역산 신뢰불가 → 이후 전부 null로 끊음(정직).
        if running is not None and running < 0:
            broke = True
        items.append({
            "period": d,
            "qty": oq,
            "amount": (o["amount"] if o else 0),
            "inbound": iq,
            "stock": None if (broke or running is None) else running,
        })
        if running is not None:
            running = running - iq + oq  # 하루 전 마감 = 오늘마감 - 오늘입고 + 오늘출고

    total_qty = sum(it["qty"] for it in items)
    day_count = len(outbound) or 1
    return {
        "items": items,
        "total_qty": total_qty,
        "avg_daily": round(total_qty / min(days, day_count)) if total_qty else 0,
        "current_stock": current_stock,
        "stock_estimated": True,  # 현재고 역산 추정치 (외부 재고동기화 조정분은 미반영)
    }


# ── 대시보드 확장 API ──
@app.get("/api/dashboard/trend")
async def dashboard_trend(days: int = 30, conn=Depends(db)):
    rows = conn.execute(
        """SELECT sale_date, SUM(total_amount) as total
           FROM sales WHERE sale_date >= date('now', '-' || ? || ' days', 'localtime')
           AND status='confirmed' GROUP BY sale_date ORDER BY sale_date""",
        (days,),
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/dashboard/channels")
async def dashboard_channels(conn=Depends(db)):
    month_start = datetime.now().strftime("%Y-%m-01")
    rows = conn.execute(
        """SELECT channel, SUM(total_amount) as total, COUNT(*) as cnt
           FROM sales WHERE sale_date >= ? AND status='confirmed' AND channel IS NOT NULL
           GROUP BY channel ORDER BY total DESC""",
        (month_start,),
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/dashboard/top-products")
async def dashboard_top_products(conn=Depends(db)):
    month_start = datetime.now().strftime("%Y-%m-01")
    rows = conn.execute(
        """SELECT sl.product_name, SUM(sl.qty) as total_qty, SUM(sl.line_total) as total_amount
           FROM sale_lines sl JOIN sales s ON s.id=sl.sale_id
           WHERE s.sale_date >= ? AND s.status='confirmed' AND sl.product_name IS NOT NULL
           GROUP BY sl.product_name ORDER BY total_amount DESC LIMIT 10""",
        (month_start,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── 품목 삭제 ──
@app.delete("/api/products/{pid}")
async def delete_product(pid: int, conn=Depends(db)):
    conn.execute("UPDATE products SET is_active=0, updated_at=datetime('now','localtime') WHERE id=?", (pid,))
    conn.commit()
    return {"ok": True}


# ── 품목 단종 처리 ──
@app.put("/api/products/{pid}/discontinue")
async def discontinue_product(pid: int, request: Request, conn=Depends(db)):
    d = await request.json()
    val = 1 if d.get("discontinue", True) else 0
    conn.execute(
        "UPDATE products SET is_discontinued=?, updated_at=datetime('now','localtime') WHERE id=?",
        (val, pid),
    )
    conn.commit()
    return {"ok": True, "is_discontinued": val}


# ── 품목 일괄 처리 ──
@app.post("/api/products/bulk-action")
async def bulk_product_action(request: Request, conn=Depends(db)):
    d = await request.json()
    ids = d.get("ids", [])
    action = d.get("action", "")
    if not ids or action not in ("delete", "discontinue", "activate"):
        raise HTTPException(400, "ids와 action(delete/discontinue/activate) 필수")
    placeholders = ",".join("?" * len(ids))
    if action == "delete":
        conn.execute(f"UPDATE products SET is_active=0, updated_at=datetime('now','localtime') WHERE id IN ({placeholders})", ids)
    elif action == "discontinue":
        conn.execute(f"UPDATE products SET is_discontinued=1, updated_at=datetime('now','localtime') WHERE id IN ({placeholders})", ids)
    elif action == "activate":
        conn.execute(f"UPDATE products SET is_discontinued=0, updated_at=datetime('now','localtime') WHERE id IN ({placeholders})", ids)
    conn.commit()
    return {"ok": True, "count": len(ids), "action": action}


# ── 사용자 관리 ──
@app.get("/api/users")
async def list_users(conn=Depends(db)):
    rows = conn.execute("SELECT id, username, name, role, email, is_active, created_at FROM users").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/users")
async def create_user(request: Request, conn=Depends(db)):
    d = await request.json()
    pw_hash = hashlib.sha256(d["password"].encode()).hexdigest()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, name, role, email) VALUES (?,?,?,?,?)",
            (d["username"], pw_hash, d["name"], d.get("role", "staff"), d.get("email")),
        )
        conn.commit()
        return {"id": cur.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(400, "이미 존재하는 사용자입니다")


@app.put("/api/users/{uid}")
async def update_user(uid: int, request: Request, conn=Depends(db)):
    d = await request.json()
    fields, params = [], []
    for k in ("name", "role", "email"):
        if k in d:
            fields.append(f"{k}=?")
            params.append(d[k])
    if "is_active" in d:
        fields.append("is_active=?")
        params.append(1 if d["is_active"] else 0)
    if not fields:
        raise HTTPException(400, "변경할 내용이 없습니다")
    fields.append("updated_at=datetime('now','localtime')")
    params.append(uid)
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", params)
    conn.commit()
    return {"ok": True}


@app.post("/api/users/{uid}/reset-password")
async def reset_user_password(uid: int, request: Request, conn=Depends(db)):
    d = await request.json()
    pw = d.get("password", "")
    if len(pw) < 4:
        raise HTTPException(400, "비밀번호는 4자 이상이어야 합니다")
    pw_hash = hashlib.sha256(pw.encode()).hexdigest()
    conn.execute(
        "UPDATE users SET password_hash=?, updated_at=datetime('now','localtime') WHERE id=?",
        (pw_hash, uid),
    )
    conn.commit()
    return {"ok": True}


# ── 일정 (캘린더) ──
@app.get("/api/events")
async def list_events(start: str = "", end: str = "", conn=Depends(db)):
    """기간 내 일정 조회. 수동/노션 일정 + 발주 재입고일(자동) 합쳐서 반환."""
    where, params = [], []
    if start:
        where.append("COALESCE(end_date, start_date) >= ?")
        params.append(start)
    if end:
        where.append("start_date <= ?")
        params.append(end)
    sql = "SELECT * FROM events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    # 발주 납품예정일 → 재입고 일정으로 자동 생성 (events 테이블엔 저장 안 함, 조회 시 합성)
    po_where = ["po.delivery_date IS NOT NULL", "po.delivery_date != ''", "po.status != 'cancelled'"]
    po_params = []
    if start:
        po_where.append("po.delivery_date >= ?"); po_params.append(start)
    if end:
        po_where.append("po.delivery_date <= ?"); po_params.append(end)
    po_rows = conn.execute(
        f"""SELECT po.id, po.po_number, po.delivery_date, po.memo, p.name as supplier,
            (SELECT product_name FROM purchase_order_lines WHERE po_id=po.id ORDER BY id LIMIT 1) as first_product,
            (SELECT COUNT(*) FROM purchase_order_lines WHERE po_id=po.id) as line_count
            FROM purchase_orders po LEFT JOIN partners p ON p.id=po.supplier_id
            WHERE {' AND '.join(po_where)}""",
        po_params,
    ).fetchall()
    for po in po_rows:
        name = po["first_product"] or po["memo"] or po["supplier"] or "발주"
        if name.startswith("[") and "]" in name:  # [비코어랩] 류 브랜드 태그 제거
            name = name.split("]", 1)[1].strip()
        extra = f" 외 {po['line_count'] - 1}건" if (po["line_count"] or 0) > 1 else ""
        rows.append({
            "id": f"po-{po['id']}", "title": f"📦 {name}{extra} 입고",
            "event_type": "restock", "start_date": po["delivery_date"], "end_date": None,
            "all_day": 1, "memo": f"발주번호 {po['po_number']} · {po['supplier'] or ''}", "source": "po",
            "source_id": str(po["id"]), "readonly": True,
        })

    # 공휴일 합성 (events 테이블엔 저장 안 함, 조회 시 생성)
    rows.extend(get_holidays_in_range(start, end))

    return rows


@app.post("/api/events")
async def create_event(request: Request, conn=Depends(db)):
    d = await request.json()
    if not d.get("title") or not d.get("start_date"):
        raise HTTPException(400, "제목과 날짜는 필수입니다")
    cur = conn.execute(
        """INSERT INTO events (title, event_type, start_date, end_date, all_day, start_time, memo, color, created_by)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (d["title"], d.get("event_type", "etc"), d["start_date"], d.get("end_date") or None,
         1 if d.get("all_day", True) else 0, d.get("start_time") or None,
         d.get("memo") or None, d.get("color") or None, d.get("created_by")),
    )
    conn.commit()
    return {"id": cur.lastrowid}


@app.put("/api/events/{eid}")
async def update_event_erp(eid: int, request: Request, conn=Depends(db)):
    d = await request.json()
    fields, params = [], []
    for k in ("title", "event_type", "start_date", "end_date", "start_time", "memo", "color"):
        if k in d:
            fields.append(f"{k}=?"); params.append(d[k] or None)
    if "all_day" in d:
        fields.append("all_day=?"); params.append(1 if d["all_day"] else 0)
    if not fields:
        raise HTTPException(400, "변경할 내용이 없습니다")
    fields.append("updated_at=datetime('now','localtime')")
    params.append(eid)
    conn.execute(f"UPDATE events SET {', '.join(fields)} WHERE id=?", params)
    conn.commit()
    return {"ok": True}


@app.delete("/api/events/{eid}")
async def delete_event_erp(eid: int, conn=Depends(db)):
    conn.execute("DELETE FROM events WHERE id=?", (eid,))
    conn.commit()
    return {"ok": True}


# ── 채널별 가격관리 (파일럿) ──
@app.get("/api/pricing")
async def get_pricing(conn=Depends(db)):
    channels = [dict(r) for r in conn.execute(
        "SELECT id, name, commission_rate, vat_rate, sort_order FROM price_channels ORDER BY sort_order").fetchall()]
    items = [dict(r) for r in conn.execute(
        "SELECT id, code, name, group_name, pack, cost, consumer, sort_order FROM price_items ORDER BY sort_order").fetchall()]
    cellmap = {}
    for r in conn.execute("SELECT item_id, channel_id, sale_price FROM price_cells").fetchall():
        cellmap.setdefault(r["item_id"], {})[str(r["channel_id"])] = r["sale_price"]
    for it in items:
        it["prices"] = cellmap.get(it["id"], {})
    return {"channels": channels, "items": items}


@app.put("/api/pricing/cell")
async def update_pricing_cell(request: Request, conn=Depends(db)):
    d = await request.json()
    price = d.get("sale_price")
    price = int(price) if price not in (None, "") else None
    conn.execute(
        "INSERT INTO price_cells (item_id, channel_id, sale_price) VALUES (?,?,?) "
        "ON CONFLICT(item_id, channel_id) DO UPDATE SET sale_price=excluded.sale_price",
        (d["item_id"], d["channel_id"], price))
    conn.commit()
    return {"ok": True}


@app.put("/api/pricing/item/{iid}")
async def update_pricing_item(iid: int, request: Request, conn=Depends(db)):
    d = await request.json()
    fields, params = [], []
    for k in ("cost", "consumer", "name", "code", "pack"):
        if k in d:
            fields.append(f"{k}=?")
            params.append(d[k])
    if not fields:
        raise HTTPException(400, "변경할 내용이 없습니다")
    params.append(iid)
    conn.execute(f"UPDATE price_items SET {', '.join(fields)} WHERE id=?", params)
    conn.commit()
    return {"ok": True}


# ── 거래처 연락처 ──
@app.get("/api/partners/{partner_id}/contacts")
async def list_partner_contacts(partner_id: int, conn=Depends(db)):
    rows = conn.execute(
        "SELECT * FROM partner_contacts WHERE partner_id=? AND is_active=1 ORDER BY contact_type, name",
        (partner_id,),
    ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/partners/{partner_id}/contacts")
async def add_partner_contact(partner_id: int, request: Request, conn=Depends(db)):
    d = await request.json()
    conn.execute(
        "INSERT INTO partner_contacts (partner_id, name, email, contact_type) VALUES (?,?,?,?)",
        (partner_id, d["name"], d["email"], d.get("contact_type", "to")),
    )
    conn.commit()
    return {"ok": True}


@app.delete("/api/partners/{partner_id}/contacts/{contact_id}")
async def delete_partner_contact(partner_id: int, contact_id: int, conn=Depends(db)):
    conn.execute("UPDATE partner_contacts SET is_active=0 WHERE id=? AND partner_id=?", (contact_id, partner_id))
    conn.commit()
    return {"ok": True}


# ── 카카오 선물하기 트렌드 (2026-07-03) — rank_track.py 스냅샷 서빙 ──
KAKAO_SNAPDIR = "/Users/macmini_ky/ClaudeAITeam/kakao_gift_tracker/rank_snapshots"


def _kakao_snap_dates():
    if not os.path.isdir(KAKAO_SNAPDIR):
        return []
    return sorted((f[:-5] for f in os.listdir(KAKAO_SNAPDIR) if f.endswith(".json")), reverse=True)


@app.get("/api/kakao/dates")
async def kakao_dates():
    return {"dates": _kakao_snap_dates()}


@app.get("/api/kakao/rank")
async def kakao_rank(date: str = ""):
    """선물하기 베스트 랭킹 (탭별) + 전일 대비 변동. date 미지정 시 최신."""
    dates = _kakao_snap_dates()
    if not dates:
        return JSONResponse({"error": "no_data", "message": "아직 수집된 랭킹이 없습니다"}, status_code=404)
    cur_date = date if (date and date in dates) else dates[0]
    with open(os.path.join(KAKAO_SNAPDIR, f"{cur_date}.json"), encoding="utf-8") as f:
        snap = json.load(f)
    # 전일 스냅샷(있으면) — 변동 계산용
    prev = None
    older = [d for d in dates if d < cur_date]
    if older:
        with open(os.path.join(KAKAO_SNAPDIR, f"{older[0]}.json"), encoding="utf-8") as f:
            prev = json.load(f)

    tabs = []
    for label, tab in snap.get("tabs", {}).items():
        pmap = {}
        if prev:
            pmap = {r["id"]: r for r in prev.get("tabs", {}).get(label, {}).get("rows", [])}
        rows = []
        for r in tab.get("rows", []):
            pv = pmap.get(r["id"])
            move, wish_d, order_d, rev_d = "new", None, None, None
            if pv:
                move = pv["rank"] - r["rank"]  # +면 상승
                if r.get("wishCount") is not None and pv.get("wishCount") is not None:
                    wish_d = r["wishCount"] - pv["wishCount"]
                if r.get("orderCount") is not None and pv.get("orderCount") is not None:
                    order_d = r["orderCount"] - pv["orderCount"]
                if r.get("reviewTotal") is not None and pv.get("reviewTotal") is not None:
                    rev_d = r["reviewTotal"] - pv["reviewTotal"]  # 리뷰 증분 = 실구매 프록시
            rows.append({**r, "move": move, "wishDelta": wish_d,
                         "orderDelta": order_d, "reviewDelta": rev_d})
        tabs.append({
            "label": label, "updatedAt": tab.get("updatedAt"),
            "hasOrder": any(r.get("orderCount") is not None for r in rows),
            "rows": rows,
        })
    return {"date": cur_date, "prevDate": (older[0] if older else None),
            "isFirst": prev is None, "tabs": tabs}


@app.get("/api/kakao/insights")
async def kakao_insights(date: str = ""):
    """선물 트렌드 인사이트 — "무슨 제품이 잘 팔리나" 도출.
    ① 카테고리 활발도(리뷰·찜·가격) ② 검증 상품 TOP(리뷰순) ③ 판매 급상승(리뷰증분)
    ④ 가격대 분포. 데이터 누적될수록 ③이 강해짐(첫날은 ①②④만)."""
    import statistics
    dates = _kakao_snap_dates()
    if not dates:
        return JSONResponse({"error": "no_data"}, status_code=404)
    cur = date if (date and date in dates) else dates[0]
    with open(os.path.join(KAKAO_SNAPDIR, f"{cur}.json"), encoding="utf-8") as f:
        snap = json.load(f)
    older = [d for d in dates if d < cur]
    prev = None
    if older:
        with open(os.path.join(KAKAO_SNAPDIR, f"{older[0]}.json"), encoding="utf-8") as f:
            prev = json.load(f)

    def med(xs):
        xs = [x for x in xs if isinstance(x, (int, float))]
        return round(statistics.median(xs)) if xs else None

    categories, all_products = [], []
    for label, tab in snap.get("tabs", {}).items():
        rows = tab.get("rows", [])
        reviews = [r.get("reviewTotal") for r in rows if r.get("reviewTotal") is not None]
        wishes = [r.get("wishCount") for r in rows if r.get("wishCount") is not None]
        prices = [r.get("price") for r in rows if isinstance(r.get("price"), (int, float))]
        categories.append({
            "label": label, "count": len(rows),
            "reviewSum": sum(reviews), "reviewMedian": med(reviews),
            "wishSum": sum(wishes), "wishMedian": med(wishes),
            "priceMedian": med(prices),
            "priceMin": min(prices) if prices else None,
            "priceMax": max(prices) if prices else None,
        })
        for r in rows:
            all_products.append({**r, "category": label})

    # 검증 상품 TOP (리뷰 누적 최다 = 이미 많이 팔린 안전한 시장)
    top_reviewed = sorted([p for p in all_products if p.get("reviewTotal")],
                          key=lambda p: -p["reviewTotal"])[:20]

    # 판매 급상승 (전일 대비 리뷰 증분 — 지금 가장 빨리 팔리는 것)
    risers = []
    if prev:
        pmap = {}
        for label, tab in prev.get("tabs", {}).items():
            for r in tab.get("rows", []):
                if r.get("reviewTotal") is not None:
                    pmap[r["id"]] = r["reviewTotal"]
        for p in all_products:
            if p.get("reviewTotal") is not None and p["id"] in pmap:
                d = p["reviewTotal"] - pmap[p["id"]]
                if d > 0:
                    risers.append({**p, "reviewDelta": d})
        risers.sort(key=lambda p: -p["reviewDelta"])
        risers = risers[:20]

    trim = lambda p: {"brand": p.get("brand"), "name": p.get("name"), "category": p.get("category"),
                      "price": p.get("price"), "reviewTotal": p.get("reviewTotal"),
                      "reviewDelta": p.get("reviewDelta"), "wishCount": p.get("wishCount"),
                      "productUrl": p.get("productUrl"), "imageUrl": p.get("imageUrl")}
    return {
        "date": cur, "prevDate": (older[0] if older else None), "hasPrev": prev is not None,
        "categories": sorted(categories, key=lambda c: -(c["reviewSum"] or 0)),
        "topReviewed": [trim(p) for p in top_reviewed],
        "risers": [trim(p) for p in risers],
    }


# ── 시작 시 DB 초기화 ──
@app.on_event("startup")
async def startup():
    if not os.path.exists(DB_PATH):
        init_db()


if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8085)
