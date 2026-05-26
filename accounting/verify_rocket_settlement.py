#!/usr/bin/env python3
"""
로켓그로스 채움컴퍼니 5월 정산 검증 스크립트
원본 4개 파일(0602, 0609, 0616, 0623)을 파싱하여 보고서 수치와 대조
"""

import openpyxl
import os
from collections import defaultdict

BASE_DIR = "/Users/macmini_ky/Library/CloudStorage/MYBOX-igimylife/개인 폴더/Becorelab/03. 영업/20. 월별 매출정산/2026.05/2026.05_클로드/로켓 그로스_채움컴퍼니"

FILES = {
    "0602": os.path.join(BASE_DIR, "0602_판매수수료 정산.xlsx"),
    "0609": os.path.join(BASE_DIR, "0609_판매수수료 정산.xlsx"),
    "0616": os.path.join(BASE_DIR, "0616_판매수수료 정산.xlsx"),
    "0623": os.path.join(BASE_DIR, "0623_판매수수료 정산.xlsx"),
}

# 컬럼 인덱스 (0-based)
COL = {
    "정산유형": 0,
    "정산주기종료일": 1,
    "세금계산서발행월": 2,
    "발생일": 3,
    "매출인식일": 4,
    "주문ID": 5,
    "거래유형": 6,
    "카테고리ID": 7,
    "카테고리명": 8,
    "과세유형": 9,
    "등록상품ID": 10,
    "옵션ID": 11,
    "SKU_ID": 12,
    "등록상품명": 13,
    "옵션명": 14,
    "판매가A": 15,
    "판매수량B": 16,
    "판매액AB": 17,
    "쿠팡지원할인C": 18,
    "매출금액": 19,
    "즉시할인쿠폰D": 20,
    "다운로드쿠폰E": 21,
    "판매자할인쿠폰DE": 22,
    "정산대상액": 23,
    "판매수수료율": 24,
    "할인적용수수료율": 25,
    "판매수수료": 26,
    "판매수수료VAT": 27,
}

def to_num(val):
    """숫자 변환 (None, 빈 문자열 → 0)"""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return val
    s = str(val).strip().replace(",", "").replace(" ", "")
    if s == "" or s == "-":
        return 0
    try:
        return float(s)
    except:
        return 0

def parse_file(filepath, label):
    """파일 파싱 → 행 리스트 반환"""
    print(f"\n{'='*60}")
    print(f"파싱 중: [{label}] {os.path.basename(filepath)}")

    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    print(f"  전체 행 수: {len(rows)}")

    # Header row 확인 (row 2, index 1)
    if len(rows) > 1:
        header = rows[1]
        print(f"  헤더(row2): {header[:5]}...")

    # 데이터는 row 3부터 (index 2)
    data_rows = rows[2:]

    # 빈 행 제거
    valid_rows = []
    for r in data_rows:
        if r[COL["주문ID"]] is not None and str(r[COL["주문ID"]]).strip() != "":
            valid_rows.append(r)

    print(f"  유효 데이터 행 수: {len(valid_rows)}")

    # 샘플 출력
    if valid_rows:
        r = valid_rows[0]
        print(f"  첫 번째 행 샘플:")
        print(f"    SKU ID: {r[COL['SKU_ID']]}, 옵션ID: {r[COL['옵션ID']]}")
        print(f"    등록상품명: {r[COL['등록상품명']]}")
        print(f"    판매수량: {r[COL['판매수량B']]}, 판매액: {r[COL['판매액AB']]}")
        print(f"    정산대상액: {r[COL['정산대상액']]}, 판매수수료: {r[COL['판매수수료']]}, VAT: {r[COL['판매수수료VAT']]}")

    return valid_rows

def analyze_all():
    all_rows = []
    per_file = {}

    for label, filepath in FILES.items():
        rows = parse_file(filepath, label)
        all_rows.extend(rows)
        per_file[label] = rows

    print(f"\n{'='*60}")
    print(f"총 유효 행 수 (4개 파일 합계): {len(all_rows)}")

    # =========================================
    # 1. 정산기별 집계
    # =========================================
    print(f"\n{'='*60}")
    print("【1. 정산기별 집계】")

    REPORT_PERIOD = {
        "0602": 1_396_660,
        "0609": 3_764_852,
        "0616": 3_992_896,
        "0623": 6_655_936,  # 물류비 차감 전
    }

    for label, rows in per_file.items():
        qty_total = sum(to_num(r[COL["판매수량B"]]) for r in rows)
        sales_total = sum(to_num(r[COL["판매액AB"]]) for r in rows)
        settlement_total = sum(to_num(r[COL["정산대상액"]]) for r in rows)
        fee_total = sum(to_num(r[COL["판매수수료"]]) for r in rows)
        vat_total = sum(to_num(r[COL["판매수수료VAT"]]) for r in rows)
        payout = settlement_total - fee_total - vat_total

        report_val = REPORT_PERIOD[label]
        match = "✅ 일치" if abs(round(payout) - report_val) <= 1 else f"❌ 불일치 (보고서: {report_val:,.0f}, 실제: {payout:,.0f}, 차이: {payout - report_val:+,.0f})"

        print(f"\n  [{label}]")
        print(f"    판매수량:   {qty_total:>10,.0f}")
        print(f"    판매액:     {sales_total:>12,.0f}원")
        print(f"    정산대상액: {settlement_total:>12,.0f}원")
        print(f"    수수료:     {fee_total:>12,.0f}원")
        print(f"    수수료VAT:  {vat_total:>12,.0f}원")
        print(f"    지급예정:   {payout:>12,.0f}원  ← {match}")

    # =========================================
    # 2. SKU별 집계
    # =========================================
    print(f"\n{'='*60}")
    print("【2. SKU별 집계】")

    sku_data = defaultdict(lambda: {"qty": 0, "sales": 0, "settlement": 0, "fee": 0, "vat": 0, "name": ""})

    for r in all_rows:
        sku = str(r[COL["SKU_ID"]]).strip() if r[COL["SKU_ID"]] else "UNKNOWN"
        sku_data[sku]["qty"] += to_num(r[COL["판매수량B"]])
        sku_data[sku]["sales"] += to_num(r[COL["판매액AB"]])
        sku_data[sku]["settlement"] += to_num(r[COL["정산대상액"]])
        sku_data[sku]["fee"] += to_num(r[COL["판매수수료"]])
        sku_data[sku]["vat"] += to_num(r[COL["판매수수료VAT"]])
        if not sku_data[sku]["name"] and r[COL["등록상품명"]]:
            sku_data[sku]["name"] = str(r[COL["등록상품명"]])[:30]

    # 보고서 기준 수치
    REPORT_SKU = {
        "61082837": {"label": "바이올렛", "qty": 710, "sales": 9_454_500, "settlement": 8_643_571, "fee": 810_929},
        "24876706": {"label": "베이비크림", "qty": 173, "sales": 3_751_800, "settlement": 3_429_864, "fee": 321_936},
        "56550750": {"label": "얼룩제거제", "qty": 316, "sales": 3_005_400, "settlement": 2_464_144, "fee": 231_256},
        "71067834": {"label": "입테이프", "qty": 309, "sales": 3_652_660, "settlement": 2_910_278, "fee": 273_392},
    }

    for sku_id, rep in REPORT_SKU.items():
        d = sku_data.get(sku_id, None)
        print(f"\n  SKU {sku_id} | {rep['label']}")
        if d is None:
            print(f"    ❌ SKU 데이터 없음!")
            continue

        actual_fee_total = d["fee"] + d["vat"]

        qty_check = "✅" if abs(d["qty"] - rep["qty"]) <= 1 else f"❌ (보고서:{rep['qty']}, 실제:{d['qty']:,.0f})"
        sales_check = "✅" if abs(d["sales"] - rep["sales"]) <= 1 else f"❌ (보고서:{rep['sales']:,}, 실제:{d['sales']:,.0f})"
        settle_check = "✅" if abs(d["settlement"] - rep["settlement"]) <= 1 else f"❌ (보고서:{rep['settlement']:,}, 실제:{d['settlement']:,.0f})"
        fee_check = "✅" if abs(actual_fee_total - rep["fee"]) <= 1 else f"❌ (보고서:{rep['fee']:,}, 실제:{actual_fee_total:,.0f})"

        print(f"    상품명: {d['name']}")
        print(f"    판매수량:   {d['qty']:>8,.0f}   {qty_check}")
        print(f"    매출액:     {d['sales']:>12,.0f}원  {sales_check}")
        print(f"    정산대상액: {d['settlement']:>12,.0f}원  {settle_check}")
        print(f"    수수료+VAT: {actual_fee_total:>12,.0f}원  {fee_check}")

    print(f"\n  [기타 SKU]")
    for sku_id, d in sku_data.items():
        if sku_id not in REPORT_SKU:
            print(f"    SKU {sku_id}: 수량 {d['qty']:.0f}, 매출 {d['sales']:,.0f}원, 정산 {d['settlement']:,.0f}원")

    # =========================================
    # 3. 전체 합계 검증
    # =========================================
    print(f"\n{'='*60}")
    print("【3. 전체 합계 검증】")

    total_qty = sum(d["qty"] for d in sku_data.values())
    total_sales = sum(d["sales"] for d in sku_data.values())
    total_settlement = sum(d["settlement"] for d in sku_data.values())
    total_fee_vat = sum(d["fee"] + d["vat"] for d in sku_data.values())
    total_payout = total_settlement - total_fee_vat

    REPORT_TOTAL_SALES = 19_864_360
    REPORT_TOTAL_SETTLEMENT = 17_447_857
    REPORT_TOTAL_FEE_VAT = 1_637_513  # 보고서 정산 흐름에서

    sales_match = "✅ 일치" if abs(total_sales - REPORT_TOTAL_SALES) <= 1 else f"❌ 불일치 (보고서: {REPORT_TOTAL_SALES:,}, 실제: {total_sales:,.0f}, 차이: {total_sales - REPORT_TOTAL_SALES:+,.0f})"
    settle_match = "✅ 일치" if abs(total_settlement - REPORT_TOTAL_SETTLEMENT) <= 1 else f"❌ 불일치 (보고서: {REPORT_TOTAL_SETTLEMENT:,}, 실제: {total_settlement:,.0f}, 차이: {total_settlement - REPORT_TOTAL_SETTLEMENT:+,.0f})"
    fee_match = "✅ 일치" if abs(total_fee_vat - REPORT_TOTAL_FEE_VAT) <= 1 else f"❌ 불일치 (보고서: {REPORT_TOTAL_FEE_VAT:,}, 실제: {total_fee_vat:,.0f}, 차이: {total_fee_vat - REPORT_TOTAL_FEE_VAT:+,.0f})"

    print(f"\n  총 판매수량:   {total_qty:>10,.0f}")
    print(f"  총 매출액:     {total_sales:>12,.0f}원  ← {sales_match}")
    print(f"  정산대상액:    {total_settlement:>12,.0f}원  ← {settle_match}")
    print(f"  수수료+VAT:    {total_fee_vat:>12,.0f}원  ← {fee_match}")
    print(f"  지급예정 합계: {total_payout:>12,.0f}원")

    REPORT_PAYOUT_SUM = 15_466_199  # 물류비 차감 포함
    print(f"\n  ※ 보고서 지급예정 합계(물류비 차감 후): {REPORT_PAYOUT_SUM:,}원")
    print(f"     실제 계산된 합계(수수료만 차감): {total_payout:,.0f}원")
    print(f"     차이(물류비 해당): {total_payout - REPORT_PAYOUT_SUM:,.0f}원")

    # =========================================
    # 4. 옵션별 집계
    # =========================================
    print(f"\n{'='*60}")
    print("【4. 옵션ID별 집계】")

    opt_data = defaultdict(lambda: {"qty": 0, "sales": 0, "settlement": 0, "fee": 0, "vat": 0, "name": "", "prod_name": ""})

    for r in all_rows:
        opt_id = str(r[COL["옵션ID"]]).strip() if r[COL["옵션ID"]] else "UNKNOWN"
        opt_data[opt_id]["qty"] += to_num(r[COL["판매수량B"]])
        opt_data[opt_id]["sales"] += to_num(r[COL["판매액AB"]])
        opt_data[opt_id]["settlement"] += to_num(r[COL["정산대상액"]])
        opt_data[opt_id]["fee"] += to_num(r[COL["판매수수료"]])
        opt_data[opt_id]["vat"] += to_num(r[COL["판매수수료VAT"]])
        if not opt_data[opt_id]["name"] and r[COL["옵션명"]]:
            opt_data[opt_id]["name"] = str(r[COL["옵션명"]])[:40]
        if not opt_data[opt_id]["prod_name"] and r[COL["등록상품명"]]:
            opt_data[opt_id]["prod_name"] = str(r[COL["등록상품명"]])[:20]

    print(f"\n  {'옵션ID':<15} {'옵션명':<35} {'수량':>6} {'매출':>12} {'정산대상':>12} {'수수료+VAT':>12}")
    print(f"  {'-'*100}")
    for opt_id, d in sorted(opt_data.items(), key=lambda x: -x[1]["sales"]):
        print(f"  {opt_id:<15} {d['name']:<35} {d['qty']:>6,.0f} {d['sales']:>12,.0f} {d['settlement']:>12,.0f} {(d['fee']+d['vat']):>12,.0f}")

    print(f"\n{'='*60}")
    print("검증 완료!")

if __name__ == "__main__":
    analyze_all()
