"""경쟁사 레이더 — SQLite DB 레이어

테이블:
  products   : 추적 대상 제품(우리/경쟁사). 쿠팡=productId, 네이버=키워드+상품명 매칭.
  snapshots  : 날짜별 스냅샷(가격/리뷰수/평점/순위/월매출/옵션). (product_ref, snap_date) 유니크.
  alerts     : 변동 감지 알림(가격↓↑/리뷰급증/옵션변경/순위변동).
"""
import os
import json
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")


def conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = conn()
    c.executescript(
        """
    CREATE TABLE IF NOT EXISTS products (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        platform     TEXT NOT NULL,            -- 'naver' | 'coupang'
        label        TEXT NOT NULL,            -- 표시용 별칭
        brand        TEXT,
        keyword      TEXT,                      -- 검색/스캔 키워드
        match_name   TEXT,                      -- 상품명 매칭 키(부분일치)
        product_id   TEXT,                      -- 쿠팡 productId
        product_url  TEXT,
        is_mine      INTEGER DEFAULT 0,         -- 우리(일비아) 제품 여부
        active       INTEGER DEFAULT 1,
        created_at   TEXT
    );

    CREATE TABLE IF NOT EXISTS snapshots (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        product_ref     INTEGER NOT NULL,
        snap_date       TEXT NOT NULL,
        price           INTEGER,
        review_count    INTEGER,
        rating          REAL,
        ranking         INTEGER,
        revenue_monthly INTEGER,
        sales_monthly   INTEGER,
        options_json    TEXT,                   -- [{name, price, share}]
        raw_json        TEXT,
        created_at      TEXT,
        UNIQUE(product_ref, snap_date)
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        product_ref  INTEGER NOT NULL,
        snap_date    TEXT,
        type         TEXT,                       -- price_drop/price_up/review_surge/option_change/rank_up/rank_down/rating_change
        message      TEXT,
        delta        REAL,
        seen         INTEGER DEFAULT 0,
        created_at   TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_snap_ref_date ON snapshots(product_ref, snap_date);
    CREATE INDEX IF NOT EXISTS idx_alert_date ON alerts(snap_date);
    """
    )
    c.commit()
    c.close()


# ---------- products ----------
def add_product(platform, label, keyword=None, match_name=None, product_id=None,
                product_url=None, brand=None, is_mine=0):
    c = conn()
    cur = c.execute(
        """INSERT INTO products(platform,label,brand,keyword,match_name,product_id,
                                 product_url,is_mine,active,created_at)
           VALUES(?,?,?,?,?,?,?,?,1,?)""",
        (platform, label, brand, keyword, match_name, product_id, product_url,
         int(is_mine), datetime.now().isoformat(timespec="seconds")),
    )
    c.commit()
    pid = cur.lastrowid
    c.close()
    return pid


def list_products(active_only=True):
    c = conn()
    q = "SELECT * FROM products"
    if active_only:
        q += " WHERE active=1"
    q += " ORDER BY is_mine DESC, platform, id"
    rows = [dict(r) for r in c.execute(q)]
    c.close()
    return rows


def get_product(pid):
    c = conn()
    r = c.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    c.close()
    return dict(r) if r else None


def update_product(pid, **fields):
    if not fields:
        return
    allowed = {"label", "brand", "keyword", "match_name", "product_id",
               "product_url", "is_mine", "active"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return
    vals.append(pid)
    c = conn()
    c.execute(f"UPDATE products SET {','.join(sets)} WHERE id=?", vals)
    c.commit()
    c.close()


def delete_product(pid):
    c = conn()
    c.execute("DELETE FROM snapshots WHERE product_ref=?", (pid,))
    c.execute("DELETE FROM alerts WHERE product_ref=?", (pid,))
    c.execute("DELETE FROM products WHERE id=?", (pid,))
    c.commit()
    c.close()


# ---------- snapshots ----------
def save_snapshot(product_ref, snap_date, price=None, review_count=None, rating=None,
                  ranking=None, revenue_monthly=None, sales_monthly=None,
                  options=None, raw=None):
    c = conn()
    c.execute(
        """INSERT INTO snapshots(product_ref,snap_date,price,review_count,rating,ranking,
                                  revenue_monthly,sales_monthly,options_json,raw_json,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(product_ref,snap_date) DO UPDATE SET
             price=COALESCE(excluded.price, snapshots.price),
             review_count=COALESCE(excluded.review_count, snapshots.review_count),
             rating=COALESCE(excluded.rating, snapshots.rating),
             ranking=COALESCE(excluded.ranking, snapshots.ranking),
             revenue_monthly=COALESCE(excluded.revenue_monthly, snapshots.revenue_monthly),
             sales_monthly=COALESCE(excluded.sales_monthly, snapshots.sales_monthly),
             options_json=COALESCE(excluded.options_json, snapshots.options_json),
             raw_json=COALESCE(excluded.raw_json, snapshots.raw_json)""",
        (product_ref, snap_date, price, review_count, rating, ranking,
         revenue_monthly, sales_monthly,
         json.dumps(options, ensure_ascii=False) if options is not None else None,
         json.dumps(raw, ensure_ascii=False) if raw is not None else None,
         datetime.now().isoformat(timespec="seconds")),
    )
    c.commit()
    c.close()


def get_snapshots(product_ref, limit=90):
    c = conn()
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM snapshots WHERE product_ref=? ORDER BY snap_date DESC LIMIT ?",
        (product_ref, limit))]
    c.close()
    rows.reverse()  # 오래된→최신
    return rows


def latest_two(product_ref):
    """최신 2개 스냅샷(오늘, 직전) 반환 — 변동 비교용."""
    c = conn()
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM snapshots WHERE product_ref=? ORDER BY snap_date DESC LIMIT 2",
        (product_ref,))]
    c.close()
    cur = rows[0] if rows else None
    prev = rows[1] if len(rows) > 1 else None
    return cur, prev


# ---------- alerts ----------
def add_alert(product_ref, snap_date, type_, message, delta=None):
    c = conn()
    c.execute(
        """INSERT INTO alerts(product_ref,snap_date,type,message,delta,seen,created_at)
           VALUES(?,?,?,?,?,0,?)""",
        (product_ref, snap_date, type_, message, delta,
         datetime.now().isoformat(timespec="seconds")),
    )
    c.commit()
    c.close()


def list_alerts(limit=50, unseen_only=False):
    c = conn()
    q = """SELECT a.*, p.label, p.platform, p.is_mine
           FROM alerts a JOIN products p ON a.product_ref=p.id"""
    if unseen_only:
        q += " WHERE a.seen=0"
    q += " ORDER BY a.created_at DESC LIMIT ?"
    rows = [dict(r) for r in c.execute(q, (limit,))]
    c.close()
    return rows


def mark_alerts_seen():
    c = conn()
    c.execute("UPDATE alerts SET seen=1 WHERE seen=0")
    c.commit()
    c.close()


if __name__ == "__main__":
    init_db()
    print("✅ radar.db 초기화 완료 →", DB_PATH)
