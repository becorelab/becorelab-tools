#!/usr/bin/env python3
"""
이카운트 OAPI V2 최종 정밀 탐색
- Purchases/SavePurchases 기반 조회 엔드포인트 탐색
- Sale/SaveSale 기반 조회 엔드포인트 탐색
- 이카운트 내부 명명 규칙 분석 적용
"""
import requests
import json
import time
from datetime import datetime

COM_CODE = "640682"
USER_ID = "BECORELAB1"
API_CERT_KEY = "47a8af0d25e934b19b6bc9d5a890eb1f48"
ZONE = "BB"
BASE = "https://oapibb.ecount.com/OAPI/V2"

resp = requests.post(f"{BASE}/OAPILogin", json={
    "COM_CODE": COM_CODE, "USER_ID": USER_ID,
    "API_CERT_KEY": API_CERT_KEY, "LAN_TYPE": "ko-KR", "ZONE": ZONE
})
SID = resp.json()["Data"]["Datas"]["SESSION_ID"]
print(f"✅ 로그인: {SID[:25]}...")

def call(endpoint, payload=None):
    url = f"{BASE}/{endpoint}?SESSION_ID={SID}"
    r = requests.post(url, json=payload or {}, timeout=10)
    try:
        body = r.json()
    except:
        body = {"raw": r.text[:300]}
    ec_st = body.get("Status", "") if isinstance(body, dict) else ""
    errors = body.get("Errors", []) if isinstance(body, dict) else []
    msg = errors[0].get("Message", "") if errors else ""
    data = body.get("Data", {}) if isinstance(body, dict) else {}
    return r.status_code, ec_st, msg, data, body

all_results = {}

def test_and_show(ep, payload=None):
    st, ec_st, msg, data, full = call(ep, payload)
    all_results[ep] = {"st": st, "ec": ec_st, "msg": msg, "payload": payload or {}}
    if ec_st == "200":
        print(f"  ✅ {ep} → 성공! TotalCnt={data.get('TotalCnt')} / Result[0]={str(data.get('Result', [{}])[0])[:150] if data.get('Result') else '[]'}")
        all_results[ep]["data"] = data
    elif "Not Found" in msg or st == 404:
        pass  # 조용히
    elif "인증되지 않은" in msg:
        print(f"  🔒 {ep} → 비활성화됨")
    elif "입력" in msg or "Parameter" in msg or "Check" in msg:
        print(f"  ⚙️  {ep} → [{ec_st}] {msg[:100]}")
    else:
        print(f"  ⚠️  {ep} → [{st}/{ec_st}] {msg[:80]}")
    time.sleep(0.2)

# ============================================================
# Purchases 카테고리 집중 (SavePurchases 존재 확인됨)
# ============================================================
print("\n[Purchases 카테고리 - 구매입력 조회]")
purchase_date = {"BASE_DATE": "20230101", "END_DATE": "20260528"}
for ep in [
    "Purchases/GetListPurchases",
    "Purchases/GetPurchasesList",
    "Purchases/GetList",
    "Purchases/ListPurchases",
    "Purchases/GetPurchases",
    "Purchases/PurchasesList",
    "Purchases/GetBasicPurchasesList",
    "Purchases/GetListPurchase",
]:
    test_and_show(ep, purchase_date)

# ============================================================
# Sale 카테고리 집중 (SaveSale 존재 확인됨)
# ============================================================
print("\n[Sale 카테고리 - 매출 조회]")
for ep in [
    "Sale/GetListSale",
    "Sale/GetSaleList",
    "Sale/GetList",
    "Sale/ListSale",
    "Sale/GetSales",
    "Sale/GetBasicSaleList",
    "Sale/GetListSaleSlip",
]:
    test_and_show(ep, purchase_date)

# ============================================================
# 이카운트 공식 API 문서 기반 - 더 다양한 카테고리명
# ============================================================
print("\n[이카운트 공식 패턴 - 다양한 카테고리]")
test_eps = [
    # 발주(구매발주) - PO 관련
    ("BuyOrder/GetListBuyOrder", purchase_date),
    ("BuyOrder/GetBuyOrderList", purchase_date),
    ("BuyOrder/GetList", purchase_date),

    # 수주(판매발주) - SO 관련
    ("SaleOrder/GetListSaleOrder", purchase_date),
    ("SaleOrder/GetList", purchase_date),

    # 입고/출고 (IO)
    ("IncomingIO/GetListIncomingIO", purchase_date),
    ("OutgoingIO/GetListOutgoingIO", purchase_date),

    # 전표 (Slip)
    ("Slip/GetListSlip", {**purchase_date, "SLIP_TYPE": "BuyOrder"}),
    ("Slip/GetListSlip", {**purchase_date, "SLIP_TYPE": "Purchase"}),
    ("Slip/GetListSlip", {**purchase_date, "SLIP_TYPE": "Sale"}),
    ("Slip/GetListSlip", {**purchase_date, "SLIP_TYPE": "Purchasing"}),

    # 이카운트 최신 문서 패턴
    ("PurchasingSlip/GetListPurchasingSlip", purchase_date),
    ("SaleSlip/GetListSaleSlip", purchase_date),
    ("BuyOrderSlip/GetListBuyOrderSlip", purchase_date),

    # 이카운트 사내 개발자 참고 패턴
    ("PurchaseBasic/GetBasicPurchaseList", {}),
    ("SaleBasic/GetBasicSaleList", {}),

    # 재고입출 관련
    ("InventoryIO/GetListInventoryIO", purchase_date),
    ("InventoryIn/GetListInventoryIn", purchase_date),
    ("InventoryOut/GetListInventoryOut", purchase_date),

    # 회계/전표
    ("AccountSlip/GetListAccountSlip", purchase_date),
    ("JournalEntry/GetListJournalEntry", purchase_date),
]

for ep, payload in test_eps:
    test_and_show(ep, payload)

# ============================================================
# 이카운트 ERP 발주서 조회 - 실제 API명 추론
# (이카운트 공지: "ERP 발주서조회 OAPI에 조회 가능 항목 추가")
# ============================================================
print("\n[발주서 조회 특화 패턴]")
po_variants = [
    ("PO/GetListPO", purchase_date),
    ("PO/GetPOList", purchase_date),
    ("PO/GetList", purchase_date),
    ("POList/GetList", purchase_date),
    ("PurchaseOrderList/GetList", purchase_date),
    ("BuyOrderList/GetList", purchase_date),
    ("ReceivingOrder/GetListReceivingOrder", purchase_date),

    # 이카운트 내부 코드 기반 추론
    ("BuyOrdering/GetListBuyOrdering", purchase_date),
    ("Ordering/GetListOrdering", purchase_date),
    ("OrderList/GetList", purchase_date),
]
for ep, payload in po_variants:
    test_and_show(ep, payload)

# ============================================================
# 최종 요약
# ============================================================
print("\n" + "="*60)
print("최종 결과")
print("="*60)

success = [(k, v) for k, v in all_results.items() if v["ec"] == "200"]
exists = [(k, v) for k, v in all_results.items()
          if "Not Found" not in v["msg"] and v["st"] != 404
          and v["ec"] not in ["200", ""] and "입력" not in v["msg"]
          and "Parameter" not in v["msg"]]

print(f"\n✅ 성공 ({len(success)}개):")
for k, v in success:
    print(f"  {k}: TotalCnt={v.get('data', {}).get('TotalCnt', '?')}")

print(f"\n⚠️  존재하지만 오류 ({len(exists)}개):")
for k, v in exists:
    print(f"  {k}: [{v['st']}/{v['ec']}] {v['msg'][:60]}")

with open("/Users/macmini_ky/ClaudeAITeam/erp/ecount_final_search.json", "w") as f:
    json.dump({"timestamp": datetime.now().isoformat(), "results": all_results,
               "success": [k for k, v in success]}, f, ensure_ascii=False, indent=2)

print("\n저장: ecount_final_search.json")
