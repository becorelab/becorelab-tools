"""이카운트 발주서 CSV → ERP DB 마이그레이션"""
import csv
import re
import glob
import os
import sys
from datetime import datetime
from database import get_db, execute, query

DOWNLOAD_DIR = os.path.expanduser("~/Downloads")
PATTERN = os.path.join(DOWNLOAD_DIR, "발주서-Excel다운로드*.csv")

def parse_number(s):
    s = s.strip().strip('\t').replace(",", "")
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return 0

def parse_csv_files():
    files = sorted(glob.glob(PATTERN))
    seen_ranges = set()
    filtered = []
    for f in files:
        base = os.path.basename(f)
        m = re.search(r'\((\d{8}~\d{8}_\d+)\)', base)
        if m:
            key = m.group(1)
            if key in seen_ranges:
                continue
            seen_ranges.add(key)
        filtered.append(f)

    all_lines = []
    for fpath in filtered:
        with open(fpath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)

        for row in rows:
            if not row or len(row) < 6:
                continue
            cell0 = row[0].strip().strip('\t')
            if not cell0 or '데이터관리' in cell0 or '일자-No' in cell0:
                continue
            if '오전' in cell0 or '오후' in cell0:
                continue

            date_no = cell0
            product_raw = row[1].strip().strip('\t')
            qty = parse_number(row[2])
            unit_price = parse_number(row[3])
            supply_amount = parse_number(row[4])
            supplier = row[5].strip().strip('\t')
            memo = row[6].strip().strip('\t') if len(row) > 6 else ''

            m = re.match(r'(\d{4}/\d{2}/\d{2})\s*-(\d+)', date_no)
            if not m:
                continue

            date_str = m.group(1).replace('/', '-')
            po_seq = int(m.group(2))

            name_match = re.match(r'(?:\[.*?\])?\s*(.+?)(?:\s*\[(.+?)\])?\s*$', product_raw)
            product_name = product_raw
            product_spec = ''
            if name_match:
                product_name = name_match.group(1).strip()
                specs = re.findall(r'\[([^\]]+)\]', product_raw)
                if specs:
                    first_bracket = specs[0] if specs else ''
                    if first_bracket.startswith('비코어랩'):
                        specs = specs[1:]
                    product_spec = ' / '.join(specs) if specs else ''

            all_lines.append({
                'date': date_str,
                'po_seq': po_seq,
                'product_name': product_raw,
                'product_spec': product_spec,
                'qty': qty,
                'unit_price': unit_price,
                'supply_amount': supply_amount,
                'supplier': supplier,
                'memo': memo,
            })

    return all_lines

def ensure_suppliers(lines):
    suppliers = set()
    for l in lines:
        if l['supplier']:
            suppliers.add(l['supplier'])

    existing = {r['name']: r['id'] for r in query("SELECT id, name FROM partners WHERE type IN ('supplier','both')")}

    supplier_map = {}
    for s in suppliers:
        if s in existing:
            supplier_map[s] = existing[s]
        else:
            max_code = query("SELECT partner_code FROM partners ORDER BY id DESC LIMIT 1")
            code_num = 1
            if max_code:
                m = re.search(r'P(\d+)', max_code[0]['partner_code'])
                if m:
                    code_num = int(m.group(1)) + 1
            new_code = f"P{code_num:04d}"
            execute(
                "INSERT INTO partners (partner_code, name, type) VALUES (?, ?, 'supplier')",
                (new_code, s)
            )
            new_id = query("SELECT id FROM partners WHERE partner_code = ?", (new_code,))[0]['id']
            supplier_map[s] = new_id
            print(f"  거래처 추가: {new_code} {s}")

    return supplier_map

def migrate():
    lines = parse_csv_files()
    if not lines:
        print("발주 데이터 없음")
        return

    print(f"총 {len(lines)}개 라인 파싱 완료")

    po_groups = {}
    for l in lines:
        key = (l['date'], l['po_seq'])
        if key not in po_groups:
            po_groups[key] = {
                'date': l['date'],
                'po_seq': l['po_seq'],
                'supplier': l['supplier'],
                'memo': l['memo'],
                'lines': [],
            }
        po_groups[key]['lines'].append(l)

    print(f"총 {len(po_groups)}개 발주서")

    supplier_map = ensure_suppliers(lines)

    existing_pos = {r['po_number'] for r in query("SELECT po_number FROM purchase_orders")}
    imported = 0
    skipped = 0

    for key in sorted(po_groups.keys()):
        po = po_groups[key]
        date_compact = po['date'].replace('-', '')
        po_number = f"PO-{date_compact}-{po['po_seq']}"

        if po_number in existing_pos:
            skipped += 1
            continue

        supplier_id = supplier_map.get(po['supplier'])
        total = sum(l['supply_amount'] for l in po['lines'])

        delivery_date = None
        po_date_obj = datetime.strptime(po['date'], '%Y-%m-%d')

        execute(
            """INSERT INTO purchase_orders
               (po_number, po_date, supplier_id, delivery_date, status, total_amount, memo)
               VALUES (?, ?, ?, ?, 'completed', ?, ?)""",
            (po_number, po['date'], supplier_id, delivery_date, total, po['memo'])
        )
        po_id = query("SELECT id FROM purchase_orders WHERE po_number = ?", (po_number,))[0]['id']

        for l in po['lines']:
            product_rows = query(
                "SELECT id FROM products WHERE name LIKE ? LIMIT 1",
                (f"%{l['product_name'][:20]}%",)
            )
            product_id = product_rows[0]['id'] if product_rows else None

            execute(
                """INSERT INTO purchase_order_lines
                   (po_id, product_id, product_name, qty_ordered, qty_received, unit_price, amount)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (po_id, product_id, l['product_name'], l['qty'], l['qty'], l['unit_price'], l['supply_amount'])
            )

        imported += 1

    print(f"\n=== 결과 ===")
    print(f"임포트: {imported}건")
    print(f"스킵(중복): {skipped}건")
    print(f"총 발주서: {imported + skipped}건")

    year_stats = {}
    for key, po in po_groups.items():
        year = key[0][:4]
        total = sum(l['supply_amount'] for l in po['lines'])
        if year not in year_stats:
            year_stats[year] = {'count': 0, 'amount': 0}
        year_stats[year]['count'] += 1
        year_stats[year]['amount'] += total

    print(f"\n연도별 발주 현황:")
    for y in sorted(year_stats.keys()):
        s = year_stats[y]
        print(f"  {y}년: {s['count']}건 / ₩{s['amount']:,.0f}")

if __name__ == '__main__':
    migrate()
