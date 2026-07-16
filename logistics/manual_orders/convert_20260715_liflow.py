#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""라이플로우 수동발주 → ACG 양식 변환 (2026-07-15 발주분, 파일럿 런)
- 소스: 전송폴더/수동발주_인박스/ (xlsx 1건 + xls 2행 + txt 3건 중 2건)
- 장보는집(변윤경) 주문은 건조기시트 향 미확정으로 이번 파일에서 제외 (대표님 답변 대기)
- 출력: ACG 수동발주 양식 xls (97-2003) + 검증 리포트 stdout
"""
import json, sys
import xlrd, xlwt
import openpyxl, warnings
warnings.filterwarnings("ignore")

XFER = "/Users/macmini_ky/Library/CloudStorage/GoogleDrive-cky2833@gmail.com/내 드라이브/Claude AI work space/mac window file transfer"
INBOX = f"{XFER}/수동발주_인박스"
MAP = json.load(open("/Users/macmini_ky/ClaudeAITeam/logistics/manual_orders/vendor_product_map.json"))
PRODUCTS = MAP["acg_products"]
LIFLOW = MAP["mappings"]["라이플로우"]

COLS = ["주문번호", "받으시는분", "받으시는분전화", "받는분담당자", "받는분핸드폰",
        "주문자명", "주문자전화번호", "받는분우편번호", "받는분총주소", "수량", "품목",
        "운임타입", "지불조건", "운송장 번호", "특기사항", "상품명", "업체명", "업체전화번호", "출고지"]


def acg_name(vendor_label):
    """벤더 표기 → ACG 정답명. 미등록이면 즉시 중단 (오발송 금지)."""
    code = LIFLOW.get(vendor_label)
    if not code:
        raise SystemExit(f"❌ 미등록 상품 표기: {vendor_label!r} — 매핑테이블에 추가 후 재실행")
    return PRODUCTS[code]


rows = []  # (주문번호, 받는분, 전화, 우편, 주소, 수량, 품목, 특기)

# ── ① 구형 xls (B2B — 원오버엔/엔빵마켓) ──
wb = xlrd.open_workbook(f"{INBOX}/라이플로우_260715 일비아 주문건1.xls")
sh = wb.sheet_by_index(0)
hdr = {str(sh.cell_value(0, c)): c for c in range(sh.ncols)}
for r in range(1, sh.nrows):
    g = lambda k: str(sh.cell_value(r, hdr[k])).strip()
    qty = int(float(sh.cell_value(r, hdr["수량"])))
    rows.append(("260715-1", g("수령인"), g("휴대전화"), g("우편번호").split(".")[0],
                 g("주소"), qty, acg_name(g("상품명")), f"매출처: {g('매출처')}"))

# ── ② xlsx (현정케이커머스 → 김현정) ──
wb2 = openpyxl.load_workbook(f"{INBOX}/20260715 일비아 발주건2.xlsx")
s2 = wb2.active
h2 = {c.value: j for j, c in enumerate(s2[1])}
v = [c.value for c in s2[2]]
rows.append(("260715-2", str(v[h2["받는분"]]), str(v[h2["받는분연락처1"]]),
             str(v[h2["우편번호"]]), str(v[h2["받는분주소"]]),
             int(v[h2["수량"]]), acg_name(str(v[h2["상품명"]]).strip()),
             f"주문자: {v[h2['주문자']]} {v[h2['주문자연락처1']]}"))

# ── ③ txt 자유서식 — 대표님 대조표 승인분 (2026-07-16) ──
# 오늘앤픽: 고체탈취제 파우더린넨 500개 (20입 25박스)
rows.append(("260715-3", "오늘앤픽", "010-4544-7969", "",
             "경기도 남양주시 와부읍 석실로 336번길 15-1 오늘앤픽",
             500, acg_name("일비아 고체탈취제 파우더린넨"), "20입 25박스 포장"))
# 슈퍼키친 서울역센트럴점 김세진
for label, q in [("일비아 초고농축 세탁 캡슐세제 버블코튼 30개입", 1),
                 ("일비아 화이트 버블 스팀 캡슐 표백제 30개입", 1),
                 ("일비아 티트리 딥클린 얼룩제거제 100ml", 1)]:
    rows.append(("260715-4", "김세진", "010-9176-1689", "",
                 "서울시 중구 만리재로 177, 상가동 102호, 슈퍼키친 서울역센트럴점",
                 q, acg_name(label), ""))
# ⏸️ 장보는집(변윤경): 건조기시트 향 미확정 — 이번 파일 제외, 답변 후 260715-5로 추가

# ── 출력 ──
out_wb = xlwt.Workbook(encoding="utf-8")
ws = out_wb.add_sheet("수동발주양식")
for j, c in enumerate(COLS):
    ws.write(0, j, c)
for i, (ono, name, phone, zipc, addr, qty, item, note) in enumerate(rows, start=1):
    ws.write(i, 0, ono); ws.write(i, 1, name); ws.write(i, 2, phone)
    ws.write(i, 5, name); ws.write(i, 6, phone)
    ws.write(i, 7, zipc); ws.write(i, 8, addr)
    ws.write(i, 9, qty); ws.write(i, 10, item); ws.write(i, 14, note)
out_path = f"{XFER}/비코어랩_수동발주_20260715_라이플로우_변환본.xls"
out_wb.save(out_path)

# ── 검증 리포트 ──
print(f"✅ 저장: {out_path}")
print(f"주문 {len(set(r[0] for r in rows))}건 / 품목행 {len(rows)}줄 / 총수량 {sum(r[5] for r in rows)}개")
from collections import Counter
for item, q in sorted(Counter()._update_ret if False else
                      [(i, sum(r[5] for r in rows if r[6] == i)) for i in {r[6] for r in rows}]):
    print(f"  {item}: {q}개")
missing_zip = [r[0] for r in rows if not r[3]]
if missing_zip:
    print(f"🚩 우편번호 없음: {sorted(set(missing_zip))} (원본에 미기재 — 주소로 조회 필요 여부 확인)")
