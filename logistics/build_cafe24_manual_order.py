#!/usr/bin/env python3
"""카페24 자동수집 주문을 ACG 수동발주 XLS로 변환한다."""

from __future__ import annotations

import argparse
import re
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

import xlrd
from xlutils.copy import copy as copy_workbook


ORDER_SHEET = "수동발주양식"
PRODUCT_SHEET = "일비아 상품리스트"
OUTPUT_HEADERS = [
    "주문번호", "받으시는분", "받으시는분전화", "받는분담당자", "받는분핸드폰",
    "주문자명", "주문자전화번호", "받는분우편번호", "받는분총주소", "수량",
    "품목", "운임타입", "지불조건", "운송장 번호", "특기사항", "상품명",
    "업체명", "업체전화번호", "출고지",
]

SKU_KEYS = {
    "detergent": "♥일비아 하트 식기세척기 세제",
    "clip": "♥일비아 하트 집게",
    "tin": "♥일비아 하트 틴케이스",
    "sample": "세제샘플 테스트키트",
    "sponge": "일비아 올인원 세제 수세미 36매",
    "stain": "일비아 얼룩제거제 350ml",
}


def text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def quantity(value) -> int:
    raw = text(value)
    try:
        parsed = int(float(raw))
    except ValueError as exc:
        raise ValueError(f"수량을 정수로 읽을 수 없습니다: {raw!r}") from exc
    if parsed <= 0:
        raise ValueError(f"수량은 1 이상이어야 합니다: {parsed}")
    return parsed


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def find_named_file(directory: Path, wanted: str) -> Path:
    for candidate in directory.iterdir():
        if candidate.is_file() and nfc(candidate.name) == nfc(wanted):
            return candidate
    raise FileNotFoundError(f"파일을 찾지 못했습니다: {directory / wanted}")


def header_map(sheet) -> dict[str, int]:
    return {text(sheet.cell_value(0, col)): col for col in range(sheet.ncols)}


def product_names(template_book) -> tuple[set[str], dict[str, str]]:
    sheet = template_book.sheet_by_name(PRODUCT_SHEET)
    names = {text(sheet.cell_value(row, 1)) for row in range(1, sheet.nrows)}
    names.discard("")

    resolved = {}
    for key, suffix in SKU_KEYS.items():
        matches = [name for name in names if name.endswith(suffix)]
        if len(matches) != 1:
            raise ValueError(f"상품리스트에서 {suffix!r} 등록명을 하나로 확정하지 못했습니다: {matches}")
        resolved[key] = matches[0]
    return names, resolved


def decompose(product: str, option: str, source_qty: int, sku: dict[str, str]) -> Counter:
    combined = f"{product} {option}"
    result = Counter()

    if "샘플 키트" in combined:
        result[sku["sample"]] += source_qty
    elif "식기세척기" in combined:
        match = re.search(r"(\d+)개\s*\(", option)
        if not match:
            raise ValueError(f"식기세척기 옵션의 구성 수량을 찾지 못했습니다: {option!r}")
        result[sku["detergent"]] += int(match.group(1)) * source_qty
        if "틴케이스" in option:
            result[sku["tin"]] += source_qty
        if "집게" in option:
            result[sku["clip"]] += source_qty
    elif "틴케이스" in combined:
        result[sku["tin"]] += source_qty
    elif "집게" in combined:
        result[sku["clip"]] += source_qty
    elif "올인원 세제 수세미" in combined:
        result[sku["sponge"]] += source_qty
    elif "얼룩제거제" in combined and "350ml" in combined:
        result[sku["stain"]] += source_qty
    else:
        raise ValueError(f"매핑되지 않은 상품/옵션입니다: 상품={product!r}, 옵션={option!r}")

    return result


def transform(source_book, sku: dict[str, str]):
    sheet = source_book.sheet_by_index(0)
    headers = header_map(sheet)
    required = {
        "주문번호", "수량", "수령인", "주문상품명", "옵션", "우편번호", "주소",
        "전화번호", "핸드폰", "배송메시지", "주문자", "주문자 전화번호", "주문자 핸드폰",
    }
    missing = sorted(required - headers.keys())
    if missing:
        raise ValueError(f"카페24 원본에 필요한 열이 없습니다: {missing}")

    orders = OrderedDict()
    for row in range(1, sheet.nrows):
        get = lambda name: text(sheet.cell_value(row, headers[name]))
        order_no = get("주문번호")
        if not order_no:
            continue
        recipient = {
            "주문번호": order_no,
            "받으시는분": get("수령인"),
            "받으시는분전화": get("전화번호"),
            "받는분담당자": "",
            "받는분핸드폰": get("핸드폰"),
            "주문자명": get("주문자"),
            "주문자전화번호": get("주문자 핸드폰") or get("주문자 전화번호"),
            "받는분우편번호": get("우편번호"),
            "받는분총주소": get("주소"),
            "특기사항": get("배송메시지"),
        }
        if order_no not in orders:
            orders[order_no] = {"recipient": recipient, "items": Counter()}
        elif orders[order_no]["recipient"] != recipient:
            raise ValueError(f"한 주문번호 안의 수취인 정보가 서로 다릅니다: {order_no}")

        components = decompose(
            get("주문상품명"), get("옵션"), quantity(get("수량")), sku
        )
        orders[order_no]["items"].update(components)

    rows = []
    for order in orders.values():
        for item_name, item_qty in order["items"].items():
            rows.append({
                **order["recipient"],
                "수량": item_qty,
                "품목": item_name,
                "운임타입": "",
                "지불조건": "",
                "운송장 번호": "",
                "상품명": "",
                "업체명": "",
                "업체전화번호": "",
                "출고지": "",
            })
    return orders, rows


def write_output(template_book, rows: list[dict], output: Path) -> None:
    template_sheet = template_book.sheet_by_name(ORDER_SHEET)
    actual_headers = [text(template_sheet.cell_value(0, col)) for col in range(template_sheet.ncols)]
    if actual_headers != OUTPUT_HEADERS:
        raise ValueError(f"수동발주 양식 헤더가 예상과 다릅니다: {actual_headers}")

    writable = copy_workbook(template_book)
    sheet_index = template_book.sheet_names().index(ORDER_SHEET)
    target = writable.get_sheet(sheet_index)

    # 양식의 예시 데이터 행 스타일을 새 발주 행 전체에 재사용한다.
    template_styles = [
        target.row(1)._Row__cells[col].xf_idx for col in range(template_sheet.ncols)
    ]
    for row_index, record in enumerate(rows, start=1):
        for col_index, header in enumerate(OUTPUT_HEADERS):
            target.write(row_index, col_index, record[header])
            cell = target.row(row_index)._Row__cells[col_index]
            cell.xf_idx = template_styles[col_index]

    output.parent.mkdir(parents=True, exist_ok=True)
    writable.save(str(output))


def verify(output: Path, expected_orders, allowed_names: set[str]) -> Counter:
    book = xlrd.open_workbook(str(output))
    sheet = book.sheet_by_name(ORDER_SHEET)
    headers = header_map(sheet)
    actual = OrderedDict()
    for row in range(1, sheet.nrows):
        order_no = text(sheet.cell_value(row, headers["주문번호"]))
        if not order_no:
            continue
        item = text(sheet.cell_value(row, headers["품목"]))
        if item not in allowed_names:
            raise ValueError(f"출력 품목이 상품리스트에 없습니다: {item}")
        actual.setdefault(order_no, Counter())[item] += quantity(sheet.cell_value(row, headers["수량"]))

    expected = OrderedDict((number, data["items"]) for number, data in expected_orders.items())
    if actual != expected:
        raise ValueError("출력 파일의 주문별 품목/수량이 변환 예상치와 다릅니다.")
    return Counter({"orders": len(actual), "rows": sum(len(v) for v in actual.values())})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transfer-dir", type=Path, required=True)
    parser.add_argument("--source", default="카페24일비아_자동수집.xls")
    parser.add_argument("--template", default="●비코어랩 수동발주 양식(ACG)_클로드.xls")
    parser.add_argument("--output", default="비코어랩_수동발주_20260714_완성.xls")
    args = parser.parse_args()

    source = find_named_file(args.transfer_dir, args.source)
    template = find_named_file(args.transfer_dir, args.template)
    output = args.transfer_dir / args.output

    source_book = xlrd.open_workbook(str(source))
    template_book = xlrd.open_workbook(str(template), formatting_info=True)
    allowed_names, sku = product_names(template_book)
    orders, rows = transform(source_book, sku)
    write_output(template_book, rows, output)
    verified = verify(output, orders, allowed_names)

    totals = Counter()
    for order in orders.values():
        totals.update(order["items"])
    print(f"output={output}")
    print(f"orders={verified['orders']} rows={verified['rows']}")
    for name, qty in totals.items():
        print(f"{name}\t{qty}")


if __name__ == "__main__":
    main()
