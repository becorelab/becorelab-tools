"""
카페24 매출 정산 스크립트
원본 데이터 → 상품명 매핑 → 피벗 집계 → 결과 비교/출력

사용법: python cafe24_settlement.py <원본파일.xlsx>
"""
import sys
import io
import os
import json
import openpyxl
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ─── 설정 ───
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
NAME_MAP_PATH = os.path.join(PARENT_DIR, 'cafe24_name_map_temp.json')

# ─── 품명리스트 로드 ───
with open(NAME_MAP_PATH, 'r', encoding='utf-8') as f:
    NAME_MAP = json.load(f)
print(f"[1/4] 품명리스트 로드: {len(NAME_MAP)}개 매핑")

# ─── 원본 파일 읽기 ───
if len(sys.argv) < 2:
    print("사용법: python cafe24_settlement.py <원본파일.xlsx>")
    sys.exit(1)

raw_path = sys.argv[1]
print(f"[2/4] 원본 파일 읽는 중: {os.path.basename(raw_path)}")

wb = openpyxl.load_workbook(raw_path, data_only=True)
ws = wb[wb.sheetnames[0]]  # 첫 번째 시트 = 원본

# 헤더 파싱
headers = [cell.value for cell in ws[1]]
def col_idx(keyword):
    """컬럼명에 keyword가 포함된 인덱스 찾기 (부분 매칭)"""
    for i, h in enumerate(headers):
        if h and keyword in str(h):
            return i
    return None

# 필요한 컬럼 인덱스
IDX_ORDER_NO = col_idx('주문번호')
IDX_PRODUCT_NAME = col_idx('주문상품명(옵션포함)') or col_idx('주문상품명')
IDX_OPTION_PRICE = col_idx('옵션+판매가')
IDX_QTY = col_idx('수량')
IDX_SHIPPING = col_idx('총 배송비(KRW)')
IDX_PURCHASE_AMT = col_idx('상품구매금액')
IDX_SELL_PRICE = col_idx('판매가')

print(f"  컬럼 인덱스: 주문번호={IDX_ORDER_NO}, 상품명={IDX_PRODUCT_NAME}, "
      f"옵션+판매가={IDX_OPTION_PRICE}, 수량={IDX_QTY}, 배송비={IDX_SHIPPING}")

# ─── 데이터 처리 ───
print(f"[3/4] 데이터 처리 중...")

# 주문번호별 배송비 추적 (첫 품목에만 표시)
order_shipping_used = set()

pivot = defaultdict(lambda: {'qty': 0, 'amount': 0, 'shipping': 0})
unmapped = []
total_rows = 0

for row in ws.iter_rows(min_row=2, values_only=True):
    total_rows += 1

    # 상품명 매핑
    product_name_raw = str(row[IDX_PRODUCT_NAME] or '').strip()
    final_name = NAME_MAP.get(product_name_raw, None)

    if not final_name:
        unmapped.append(product_name_raw)
        continue

    # 수량
    qty = row[IDX_QTY]
    if qty is None:
        qty = 0
    qty = int(qty)

    # 결제총액 = 옵션+판매가 × 수량
    option_price = row[IDX_OPTION_PRICE]
    if option_price is None:
        option_price = 0
    amount = float(option_price) * qty

    # 배송비 (주문 단위, 첫 품목에만)
    order_no = str(row[IDX_ORDER_NO] or '')
    shipping = 0
    if order_no and order_no not in order_shipping_used:
        ship_val = row[IDX_SHIPPING]
        if ship_val is not None:
            shipping = float(ship_val)
        order_shipping_used.add(order_no)

    pivot[final_name]['qty'] += qty
    pivot[final_name]['amount'] += amount
    pivot[final_name]['shipping'] += shipping

# ─── 결과 출력 ───
print(f"[4/4] 결과 출력\n")
print(f"{'='*80}")
print(f"  카페24 매출 피벗 결과")
print(f"{'='*80}")
print(f"  총 {total_rows}행 처리 → {len(pivot)}개 상품 카테고리\n")

# 정렬: 상품명 가나다순
sorted_items = sorted(pivot.items(), key=lambda x: x[0])

print(f"{'#':>3}  {'상품명':<45} {'수량':>8} {'결제총액':>15} {'배송비':>12}")
print(f"{'─'*3}  {'─'*45} {'─'*8} {'─'*15} {'─'*12}")

total_qty = 0
total_amount = 0
total_shipping = 0

for i, (name, data) in enumerate(sorted_items, 1):
    q = data['qty']
    a = data['amount']
    s = data['shipping']
    total_qty += q
    total_amount += a
    total_shipping += s
    print(f"{i:>3}  {name:<45} {q:>8,} {a:>15,.0f} {s:>12,.0f}")

print(f"{'─'*3}  {'─'*45} {'─'*8} {'─'*15} {'─'*12}")
print(f"{'':>3}  {'총합계':<45} {total_qty:>8,} {total_amount:>15,.0f} {total_shipping:>12,.0f}")
print(f"\n  결제총액 + 배송비 = {total_amount + total_shipping:,.0f}")

# 미매핑 상품
if unmapped:
    unique_unmapped = sorted(set(unmapped))
    print(f"\n{'='*80}")
    print(f"  ⚠️ 미매핑 상품: {len(unique_unmapped)}개 ({len(unmapped)}행)")
    print(f"{'='*80}")
    for name in unique_unmapped:
        cnt = unmapped.count(name)
        print(f"  - {name} ({cnt}건)")
else:
    print(f"\n  ✅ 미매핑 상품 없음 — 전체 매핑 성공!")

print()
