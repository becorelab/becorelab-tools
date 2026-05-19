-- 비코어랩 ERP 데이터베이스 스키마
-- SQLite (초기 버전, 추후 PostgreSQL 이관 가능)

-- 사용자 / 권한
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',  -- admin, manager, staff, viewer
    email TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 거래처
CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT DEFAULT 'supplier',  -- supplier(공급처), channel(판매채널), both
    ceo_name TEXT,
    business_no TEXT,
    phone TEXT,
    mobile TEXT,
    email TEXT,
    address TEXT,
    bank_info TEXT,
    memo TEXT,
    is_active INTEGER DEFAULT 1,
    ecount_code TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 품목
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    spec TEXT,
    unit TEXT DEFAULT 'EA',
    category TEXT,
    product_type TEXT DEFAULT 'goods',  -- goods, material, intangible
    purchase_price REAL DEFAULT 0,
    sell_price REAL DEFAULT 0,
    safety_stock INTEGER DEFAULT 0,
    lead_time_days INTEGER DEFAULT 7,
    moq INTEGER DEFAULT 0,
    primary_supplier_id INTEGER REFERENCES partners(id),
    barcode TEXT,
    is_active INTEGER DEFAULT 1,
    ecount_code TEXT,
    ezadmin_code TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 재고 현황 (스냅샷)
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty_on_hand INTEGER DEFAULT 0,
    qty_reserved INTEGER DEFAULT 0,
    qty_available INTEGER GENERATED ALWAYS AS (qty_on_hand - qty_reserved) STORED,
    pending_inbound INTEGER DEFAULT 0,
    last_synced_at TEXT,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 재고 이동 이력
CREATE TABLE IF NOT EXISTS stock_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    tx_type TEXT NOT NULL,  -- inbound, outbound, adjust, return
    qty_change INTEGER NOT NULL,
    qty_before INTEGER,
    qty_after INTEGER,
    ref_type TEXT,  -- purchase_order, sale, manual
    ref_id INTEGER,
    memo TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 매출 전표
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_date TEXT NOT NULL,
    partner_id INTEGER REFERENCES partners(id),
    channel TEXT,
    channel_order_no TEXT,
    total_supply REAL DEFAULT 0,
    total_tax REAL DEFAULT 0,
    total_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'confirmed',  -- confirmed, cancelled, returned
    recipient TEXT,
    memo TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 매출 상세
CREATE TABLE IF NOT EXISTS sale_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    product_id INTEGER REFERENCES products(id),
    product_name TEXT,
    qty INTEGER NOT NULL,
    unit_price REAL DEFAULT 0,
    supply_amount REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    line_total REAL DEFAULT 0
);

-- 발주서
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT UNIQUE NOT NULL,
    po_date TEXT NOT NULL,
    supplier_id INTEGER NOT NULL REFERENCES partners(id),
    delivery_date TEXT,
    total_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'draft',  -- draft, confirmed, partial, completed, cancelled
    email_sent_at TEXT,
    memo TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 발주 상세
CREATE TABLE IF NOT EXISTS purchase_order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id INTEGER NOT NULL REFERENCES purchase_orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    product_name TEXT,
    qty_ordered INTEGER NOT NULL,
    qty_received INTEGER DEFAULT 0,
    unit_price REAL DEFAULT 0,
    amount REAL DEFAULT 0
);

-- 입고 기록
CREATE TABLE IF NOT EXISTS receiving_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id INTEGER REFERENCES purchase_orders(id),
    po_line_id INTEGER REFERENCES purchase_order_lines(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    recv_date TEXT NOT NULL,
    qty_received INTEGER NOT NULL,
    memo TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 감사 로그
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    table_name TEXT,
    record_id INTEGER,
    old_data TEXT,  -- JSON
    new_data TEXT,  -- JSON
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_partners_code ON partners(partner_code);
CREATE INDEX IF NOT EXISTS idx_products_code ON products(product_code);
CREATE INDEX IF NOT EXISTS idx_stock_product ON stock(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_tx_product ON stock_transactions(product_id);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_po_date ON purchase_orders(po_date);
CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status);
CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_logs(table_name, record_id);
