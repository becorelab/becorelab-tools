"""이카운트 + 이지어드민 데이터 → ERP DB 마이그레이션"""
import json
import os
import sqlite3
import sys

from database import get_db, init_db, DB_PATH

PROJECT_ROOT = "/Users/macmini_ky/ClaudeAITeam"
ECOUNT_PRODUCTS = os.path.join(PROJECT_ROOT, "erp", "ecount_products.json")
CUSTOMER_CODES = os.path.join(PROJECT_ROOT, "logistics", "erp_customer_codes.json")
CACHE_FILE = os.path.join(PROJECT_ROOT, "logistics", "data", "cache.json")

PROD_TYPE_MAP = {
    "1": "goods",   # 세트
    "2": "material", # 원재료
    "3": "goods",    # 판매상품
    "4": "material", # 부자재
    "7": "intangible", # 서비스
}


def migrate_partners():
    """거래처 마이그레이션 (erp_customer_codes.json)"""
    if not os.path.exists(CUSTOMER_CODES):
        print("⚠️  거래처 매핑 파일 없음, 건너뜀")
        return 0

    with open(CUSTOMER_CODES) as f:
        codes = json.load(f)

    conn = get_db()
    count = 0
    idx = 1
    for name, biz_no in codes.items():
        partner_code = f"P{idx:04d}"
        try:
            ptype = "channel" if "비코어랩" in name else "supplier"
            conn.execute(
                """INSERT INTO partners (partner_code, name, type, business_no, ecount_code)
                   VALUES (?, ?, ?, ?, ?)""",
                (partner_code, name, ptype, biz_no, biz_no),
            )
            count += 1
            idx += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    print(f"✅ 거래처 {count}개 등록 완료")
    return count


def migrate_products():
    """품목 마이그레이션 (이카운트 API → products 테이블)"""
    if not os.path.exists(ECOUNT_PRODUCTS):
        print("⚠️  이카운트 품목 파일 없음, 건너뜀")
        return 0

    with open(ECOUNT_PRODUCTS) as f:
        data = json.load(f)

    products = data.get("products", data) if isinstance(data, dict) else data

    conn = get_db()
    count = 0
    for p in products:
        prod_cd = p.get("PROD_CD", "")
        prod_name = p.get("PROD_DES", "")
        if not prod_cd or not prod_name:
            continue

        spec = p.get("CONT1", "") or p.get("SIZE_DES", "")
        unit = p.get("UNIT", "EA") or "EA"
        prod_type = PROD_TYPE_MAP.get(p.get("PROD_TYPE", "3"), "goods")
        purchase_price = float(p.get("IN_PRICE", 0) or 0)
        sell_price = float(p.get("OUT_PRICE", 0) or 0)
        safety_stock = int(float(p.get("SAFE_QTY", 0) or 0))
        barcode = p.get("BAR_CODE", "") or None

        try:
            conn.execute(
                """INSERT INTO products (product_code, name, spec, unit, product_type,
                   purchase_price, sell_price, safety_stock, barcode, ecount_code, ezadmin_code)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (prod_cd, prod_name, spec, unit, prod_type,
                 purchase_price, sell_price, safety_stock, barcode, prod_cd, prod_cd),
            )
            count += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    print(f"✅ 품목 {count}개 등록 완료")
    return count


def migrate_stock():
    """재고 동기화 (이지어드민 캐시 → stock 테이블)"""
    if not os.path.exists(CACHE_FILE):
        print("⚠️  재고 캐시 없음, 건너뜀")
        return 0

    with open(CACHE_FILE) as f:
        cache = json.load(f)

    inventory = cache.get("inventory", {})
    conn = get_db()
    count = 0

    for code, info in inventory.items():
        qty = info.get("stock", 0)
        updated = info.get("updated", "")
        product = conn.execute(
            "SELECT id FROM products WHERE product_code=? OR ezadmin_code=?", (code, code)
        ).fetchone()
        if product:
            existing = conn.execute("SELECT id FROM stock WHERE product_id=?", (product["id"],)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE stock SET qty_on_hand=?, last_synced_at=? WHERE product_id=?",
                    (qty, updated, product["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO stock (product_id, qty_on_hand, last_synced_at) VALUES (?,?,?)",
                    (product["id"], qty, updated),
                )
            count += 1
        else:
            print(f"  ⚠️  품목 코드 '{code}' 미매칭 (재고: {qty})")

    conn.commit()
    conn.close()
    print(f"✅ 재고 {count}개 동기화 완료")
    return count


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("🗑️  기존 DB 삭제")

    init_db()
    print(f"📦 DB 초기화 완료: {DB_PATH}\n")

    migrate_partners()
    migrate_products()
    migrate_stock()

    conn = get_db()
    p_cnt = conn.execute("SELECT COUNT(*) as c FROM partners").fetchone()["c"]
    pr_cnt = conn.execute("SELECT COUNT(*) as c FROM products").fetchone()["c"]
    s_cnt = conn.execute("SELECT COUNT(*) as c FROM stock WHERE qty_on_hand > 0").fetchone()["c"]
    conn.close()
    print(f"\n📊 최종 현황: 거래처 {p_cnt}개 / 품목 {pr_cnt}개 / 재고보유 {s_cnt}개")


if __name__ == "__main__":
    main()
