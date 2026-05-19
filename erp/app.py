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
    return templates.TemplateResponse("index.html", {"request": request})


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
    low_stock = conn.execute("SELECT COUNT(*) as cnt FROM stock WHERE qty_on_hand <= 10").fetchone()["cnt"]

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
async def list_stock(q: str = "", alert_only: bool = False, conn=Depends(db)):
    where, params = ["p.is_active=1"], []
    if q:
        where.append("(p.name LIKE ? OR p.product_code LIKE ?)")
        params += [f"%{q}%"] * 2
    if alert_only:
        where.append("s.qty_on_hand <= p.safety_stock")
    w = " AND ".join(where)
    rows = conn.execute(
        f"""SELECT p.id, p.product_code, p.name, p.spec, p.unit, p.safety_stock,
            p.ezadmin_code, s.qty_on_hand, s.qty_reserved, s.qty_available, s.pending_inbound,
            s.last_synced_at
            FROM products p LEFT JOIN stock s ON s.product_id=p.id
            WHERE {w} ORDER BY s.qty_on_hand ASC""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/stock/sync")
async def sync_stock(conn=Depends(db)):
    """이지어드민 캐시 데이터로 재고 동기화"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{LOGISTICS_URL}/api/cached-data") as resp:
            if resp.status != 200:
                raise HTTPException(502, "물류서버 연결 실패")
            data = await resp.json()

    inventory = data.get("inventory", {})
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
    partner_id: int = 0, q: str = "",
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
    total = conn.execute(f"SELECT COUNT(*) as cnt FROM sales s WHERE {w}", params).fetchone()["cnt"]

    sum_row = conn.execute(
        f"SELECT COALESCE(SUM(total_amount),0) as sum_amount, COALESCE(SUM(total_supply),0) as sum_supply FROM sales s WHERE {w}",
        params,
    ).fetchone()

    rows = conn.execute(
        f"""SELECT s.*, p.name as partner_name
            FROM sales s LEFT JOIN partners p ON p.id=s.partner_id
            WHERE {w} ORDER BY s.sale_date DESC, s.id DESC LIMIT ? OFFSET ?""",
        params + [size, (page - 1) * size],
    ).fetchall()
    return {
        "items": [dict(r) for r in rows], "total": total, "page": page, "size": size,
        "sum_amount": sum_row["sum_amount"], "sum_supply": sum_row["sum_supply"],
    }


@app.get("/api/sales/channels")
async def list_sales_channels(conn=Depends(db)):
    rows = conn.execute("SELECT DISTINCT channel FROM sales WHERE channel IS NOT NULL ORDER BY channel").fetchall()
    return [r["channel"] for r in rows]


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
                    product_name = order.get("name", "")
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


# ── 발주 CRUD ──
@app.get("/api/purchase-orders")
async def list_po(
    status: str = "", supplier_id: int = 0, q: str = "",
    date_from: str = "", date_to: str = "",
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
    total = conn.execute(
        f"SELECT COUNT(*) as cnt FROM purchase_orders po LEFT JOIN partners sup ON sup.id=po.supplier_id WHERE {w}", params
    ).fetchone()["cnt"]
    sum_row = conn.execute(
        f"SELECT COALESCE(SUM(po.total_amount),0) as sum_amount FROM purchase_orders po LEFT JOIN partners sup ON sup.id=po.supplier_id WHERE {w}", params
    ).fetchone()
    rows = conn.execute(
        f"""SELECT po.*, sup.name as supplier_name
            FROM purchase_orders po LEFT JOIN partners sup ON sup.id=po.supplier_id
            WHERE {w} ORDER BY po.po_date DESC LIMIT ? OFFSET ?""",
        params + [size, (page - 1) * size],
    ).fetchall()
    return {"items": [dict(r) for r in rows], "total": total, "page": page, "size": size, "sum_amount": sum_row["sum_amount"]}


@app.get("/api/purchase-orders/{po_id}")
async def get_po(po_id: int, conn=Depends(db)):
    po = conn.execute(
        "SELECT po.*, sup.name as supplier_name FROM purchase_orders po LEFT JOIN partners sup ON sup.id=po.supplier_id WHERE po.id=?",
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
    conn.execute(
        """UPDATE purchase_orders SET po_date=?, supplier_id=?, delivery_date=?,
           status=?, memo=?, updated_at=datetime('now','localtime') WHERE id=?""",
        (d.get("po_date"), d.get("supplier_id"), d.get("delivery_date"),
         d.get("status"), d.get("memo"), po_id),
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


# ── 시작 시 DB 초기화 ──
@app.on_event("startup")
async def startup():
    if not os.path.exists(DB_PATH):
        init_db()


if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8085, reload=True)
