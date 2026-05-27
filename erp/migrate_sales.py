#!/usr/bin/env python3
"""
이카운트 판매전표 CSV → ERP DB 매출 임포트 스크립트
- 14개 CSV 파일 (2023-01 ~ 2026-03)
- 주문번호 기준 중복 제거 (기간 겹침 파일 처리)
- 기존 이지어드민 데이터(2026-03-18~) 보존
"""

import csv
import sqlite3
import glob
import re
from collections import defaultdict

DB_PATH = "/Users/macmini_ky/ClaudeAITeam/erp/erp.db"
CSV_GLOB = "/Users/macmini_ky/Downloads/판매전표-Excel다운로드*.csv"


def parse_number(s):
    """쉼표 포함 숫자 문자열 → float. 빈 문자열은 0."""
    s = s.strip().replace(",", "")
    if not s:
        return 0.0
    return float(s)


def parse_date(date_no_str):
    """'2023/03/02 -1\t' → ('2023-03-02', '2023/03/02 -1')"""
    s = date_no_str.strip()
    # 날짜 부분 추출: YYYY/MM/DD
    m = re.match(r"(\d{4})/(\d{2})/(\d{2})\s+(-\d+)", s)
    if not m:
        return None, None
    date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    date_no = s  # 원본 일자-No (그룹핑 키로 사용)
    return date_str, date_no


def is_skip_row(row):
    """타임스탬프 행이나 빈 행 판별"""
    if not row or len(row) < 2:
        return True
    first = row[0].strip()
    if not first:
        return True
    # 오전/오후 포함 타임스탬프
    if "오전" in first or "오후" in first:
        return True
    # 날짜-No 패턴 아닌 행
    if not re.match(r"\d{4}/\d{2}/\d{2}\s+-\d+", first):
        return True
    return False


def load_products(conn):
    """products 테이블에서 이름→id 매핑 로드"""
    cur = conn.execute("SELECT id, name FROM products")
    products = {}
    for pid, name in cur.fetchall():
        products[name.strip()] = pid
    return products


def match_product(product_name, products_map):
    """품목명으로 product_id 매칭. 정확 매칭 우선, 없으면 포함 매칭."""
    pn = product_name.strip()
    # [규격] 제거한 버전도 시도
    pn_no_spec = re.sub(r"\s*\[.*?\]\s*$", "", pn)

    # 1) 정확 매칭
    if pn in products_map:
        return products_map[pn]
    if pn_no_spec in products_map:
        return products_map[pn_no_spec]

    # 2) 포함 매칭 (product name이 CSV 품목명에 포함되거나 그 반대)
    for name, pid in products_map.items():
        if name in pn or pn_no_spec in name:
            return pid

    return None


def load_partners(conn):
    """partners 테이블에서 이름→id 매핑"""
    cur = conn.execute("SELECT id, name FROM partners")
    return {name.strip(): pid for pid, name in cur.fetchall()}


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # 1) source 컬럼 추가 (없으면)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(sales)").fetchall()]
    if "source" not in cols:
        conn.execute("ALTER TABLE sales ADD COLUMN source TEXT DEFAULT NULL")
        conn.commit()
        print("[INFO] sales 테이블에 source 컬럼 추가 완료")

    products_map = load_products(conn)
    partners_map = load_partners(conn)

    # 2) CSV 파일 목록 (정렬)
    csv_files = sorted(glob.glob(CSV_GLOB))
    print(f"[INFO] CSV 파일 {len(csv_files)}개 발견")

    # 3) 모든 CSV에서 행 로드 (주문번호 기준 중복 제거)
    # 키: (date_no, channel, order_no) → 하나의 sales
    # 파일 간 중복: 동일 주문번호가 여러 파일에 있으면 먼저 나온 것만 유지
    seen_orders = set()  # (date_no, order_no) 이미 본 것
    all_lines = []  # (date_str, date_no, channel, product_name_raw, qty, unit_price, supply, tax, total, shipping, order_no, recipient)

    for fpath in csv_files:
        fname = fpath.split("/")[-1]
        with open(fpath, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)

        file_count = 0
        file_dup = 0
        for row in rows[2:]:  # 1행 타이틀, 2행 헤더 스킵
            if is_skip_row(row):
                continue

            date_str, date_no = parse_date(row[0])
            if not date_str:
                continue

            channel = row[1].strip() if len(row) > 1 else ""
            product_name = row[2].strip() if len(row) > 2 else ""
            qty = int(parse_number(row[3])) if len(row) > 3 else 0
            unit_price = parse_number(row[4]) if len(row) > 4 else 0
            supply = parse_number(row[5]) if len(row) > 5 else 0
            tax = parse_number(row[6]) if len(row) > 6 else 0
            total = parse_number(row[7]) if len(row) > 7 else 0
            shipping = parse_number(row[8]) if len(row) > 8 else 0
            order_no = row[9].strip() if len(row) > 9 else ""
            recipient = row[10].strip() if len(row) > 10 else ""

            # 중복 체크: 같은 date_no + order_no + product_name + qty 조합
            dedup_key = (date_no, order_no, product_name, qty)
            if dedup_key in seen_orders:
                file_dup += 1
                continue
            seen_orders.add(dedup_key)

            all_lines.append((date_str, date_no, channel, product_name, qty,
                              unit_price, supply, tax, total, shipping, order_no, recipient))
            file_count += 1

        print(f"  {fname}: {file_count}행 로드, {file_dup}행 중복 스킵")

    print(f"[INFO] 총 {len(all_lines)}행 로드 (중복 제거 후)")

    # 4) 그룹핑: (date_no, channel, order_no) → sales 1건
    groups = defaultdict(list)
    for line in all_lines:
        date_str, date_no, channel, *rest = line
        order_no = line[10]
        group_key = (date_str, date_no, channel, order_no)
        groups[group_key].append(line)

    print(f"[INFO] 그룹핑 결과: {len(groups)}건의 sales")

    # 5) 기존 이지어드민 데이터와 충돌 체크
    # 2026-03-18 이후 데이터 중 source가 NULL인 것 = 이지어드민
    existing_ezadmin = conn.execute(
        "SELECT sale_date, channel_order_no FROM sales WHERE sale_date >= '2026-03-18' AND source IS NULL"
    ).fetchall()
    existing_orders = set()
    for d, ono in existing_ezadmin:
        if ono:
            existing_orders.add(ono.strip())
    print(f"[INFO] 기존 이지어드민 데이터 {len(existing_ezadmin)}건 (2026-03-18~)")

    # 6) 임포트
    sales_count = 0
    lines_count = 0
    skipped_overlap = 0
    year_stats = defaultdict(lambda: {"sales": 0, "amount": 0.0})

    for group_key, lines in groups.items():
        date_str, date_no, channel, order_no = group_key

        # 기존 이지어드민 데이터와 주문번호 중복 체크
        if order_no and order_no in existing_orders:
            skipped_overlap += 1
            continue

        # partner_id 매칭
        partner_id = partners_map.get(channel)

        # sales 레코드의 합계
        grp_supply = sum(l[6] for l in lines)
        grp_tax = sum(l[7] for l in lines)
        grp_total = sum(l[8] for l in lines)

        # recipient: 그룹 내 첫 번째 수취인
        recipient = lines[0][11] if lines[0][11] else None

        # INSERT sales
        cur = conn.execute("""
            INSERT INTO sales (sale_date, partner_id, channel, channel_order_no,
                              total_supply, total_tax, total_amount, status, recipient, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, 'ecount')
        """, (date_str, partner_id, channel, order_no, grp_supply, grp_tax, grp_total, recipient))
        sale_id = cur.lastrowid
        sales_count += 1

        year = date_str[:4]
        year_stats[year]["sales"] += 1
        year_stats[year]["amount"] += grp_total

        # INSERT sale_lines
        for line in lines:
            product_name = line[3]
            qty = line[4]
            unit_price = line[5]
            supply = line[6]
            tax = line[7]
            total = line[8]

            product_id = match_product(product_name, products_map)

            conn.execute("""
                INSERT INTO sale_lines (sale_id, product_id, product_name, qty,
                                       unit_price, supply_amount, tax_amount, line_total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (sale_id, product_id, product_name, qty, unit_price, supply, tax, total))
            lines_count += 1

    conn.commit()

    # 7) 결과 보고
    print("\n" + "=" * 60)
    print("임포트 완료")
    print("=" * 60)
    print(f"  sales 레코드: {sales_count:,}건")
    print(f"  sale_lines 레코드: {lines_count:,}건")
    print(f"  이지어드민 중복 스킵: {skipped_overlap}건")

    print("\n연도별 매출 집계:")
    print(f"  {'연도':<8} {'건수':>8} {'매출액':>15}")
    print(f"  {'-'*8} {'-'*8} {'-'*15}")
    total_all = 0
    for year in sorted(year_stats.keys()):
        s = year_stats[year]
        print(f"  {year:<8} {s['sales']:>8,} {s['amount']:>15,.0f}원")
        total_all += s["amount"]
    print(f"  {'합계':<8} {sales_count:>8,} {total_all:>15,.0f}원")

    # DB 전체 현황
    total_db = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    ecount_db = conn.execute("SELECT COUNT(*) FROM sales WHERE source='ecount'").fetchone()[0]
    other_db = conn.execute("SELECT COUNT(*) FROM sales WHERE source IS NULL OR source != 'ecount'").fetchone()[0]
    print(f"\nDB 전체 현황:")
    print(f"  전체 sales: {total_db:,}건")
    print(f"  이카운트: {ecount_db:,}건")
    print(f"  이지어드민: {other_db:,}건")

    conn.close()


if __name__ == "__main__":
    main()
