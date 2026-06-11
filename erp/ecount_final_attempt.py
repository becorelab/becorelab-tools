#!/usr/bin/env python3
"""
이카운트 OAPI V2 최종 시도
- 이카운트 공식 페이지에서 확인된 지원 API: 발주(Purchase Order) 조회 지원
- 이카운트 OAPI 공식 문서의 실제 API 명칭 추론
- 이카운트 ERP 한국어 메뉴: 구매 > 발주서 입력 = 영어: BuyOrder
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

collected_data = {}

def call_and_report(ep, payload=None):
    url = f"{BASE}/{ep}?SESSION_ID={SID}"
    r = requests.post(url, json=payload or {}, timeout=10)
    try:
        body = r.json()
    except:
        return r.status_code, "", "", {}, {}
    ec_st = body.get("Status", "")
    errors = body.get("Errors", []) if isinstance(body, dict) else []
    msg = errors[0].get("Message", "") if errors else ""
    data = body.get("Data", {}) if isinstance(body, dict) else {}
    return r.status_code, ec_st, msg, data, body

# 이카운트 공식 문서에서 확인된 지원 카테고리 (오픈API 페이지 기준):
# 입력(Save): 판매주문, 매출, 발주, 구매, 작업지시, 상품출고, 상품입고, 구매/판매 청구서, 게시물
# 조회(GetList): 발주(Purchase Order), 재고 잔액

# 발주 조회 API가 있다고 확인됨 - 정확한 이름을 찾아야 함

print("\n=== 체계적인 네임스페이스 탐색 ===")

# 이카운트 영어 메뉴명 분석:
# - Purchase Order = 구매발주 = BuyOrder (이카운트 내부 코드)
# - Purchase = 구매입력 = Purchases (알려진 SavePurchases)
# - Sale Order = 판매발주/수주 = SaleOrder
# - Sale = 판매입력 = Sale (알려진 SaveSale)

# OAPI V2 실제 엔드포인트 패턴 분석:
# 알려진: InventoryBasic/GetBasicProductsList
# 알려진: InventoryBalance/GetListInventoryBalanceStatusByLocation
# 알려진: Purchases/SavePurchases (구매입력)
# 알려진: Sale/SaveSale (판매입력)
# 추정: BuyOrder/ (발주) ← 이카운트 공식 영어 메뉴명

# 이카운트 ERP의 실제 URL 패턴 (웹 UI 기반 추론)
# ecerp.com 내 메뉴 경로에서 API 이름 추론

# 새로운 전략: GetList 접두사 대신 이카운트 특유의 Get메서드명 시도
print("\n[1] 발주 관련 다양한 Get 메서드명 시도")
po_payload = {"BASE_DATE": "20230101", "END_DATE": "20260528"}

# 이카운트 InventoryBasic의 메서드: GetBasicProductsList (GetBasic + 리소스명 + List)
# 이카운트 InventoryBalance의 메서드: GetListInventoryBalanceStatusByLocation

# 발주 카테고리: 이카운트 내부 코드명 추론
# 한국어: 발주서입력 → 영어: BuyOrder (이카운트 공식 영문 메뉴)
# API 조회: GetListBuyOrder? 또는 GetBuyOrderList?

test_cases = [
    # BuyOrder 카테고리 (가장 가능성 높음)
    ("BuyOrder/GetListBuyOrder", po_payload),
    ("BuyOrder/GetBuyOrderList", po_payload),
    ("BuyOrder/GetBasicBuyOrderList", po_payload),
    ("BuyOrder/GetListBuyOrderSlip", po_payload),
    ("BuyOrder/GetBuyOrder", po_payload),
    ("BuyOrder/GetBuyOrderStatus", po_payload),

    # PurchaseOrder 카테고리
    ("PurchaseOrder/GetListPurchaseOrder", po_payload),
    ("PurchaseOrder/GetPurchaseOrderList", po_payload),
    ("PurchaseOrder/GetBasicPurchaseOrderList", po_payload),

    # Purchasing (발주입력과 다름)
    ("Purchasing/GetListPurchasing", po_payload),
    ("Purchasing/GetPurchasingList", po_payload),

    # InventoryBasic 패턴 적용 (이카운트 특유의 GetBasic 메서드)
    ("BuyOrder/GetBasicBuyOrderList", {}),
    ("SaleOrder/GetBasicSaleOrderList", {}),

    # 이카운트 내부 SLIP 번호 기반 조회
    ("BuyOrder/GetListBuyOrderByNo", {"BASE_DATE": "20230101"}),

    # 이카운트가 실제로 사용하는 API 이름 (문서에서 "P/O List" 언급됨)
    ("PO/GetListPO", po_payload),
    ("POList/GetList", po_payload),
    ("PurchasingOrder/GetListPurchasingOrder", po_payload),
    ("BuyingOrder/GetListBuyingOrder", po_payload),

    # 조회용 다른 패턴
    ("BuySlip/GetListBuySlip", po_payload),
    ("BuySlip/GetBuySlipList", po_payload),

    # 이카운트 공식 문서에서 자주 쓰이는 "Status" 포함 패턴
    ("BuyOrder/GetListBuyOrderStatus", po_payload),
    ("PurchaseOrder/GetListPurchaseOrderStatus", po_payload),
]

results = {}
for ep, payload in test_cases:
    st, ec_st, msg, data, full = call_and_report(ep, payload)
    results[ep] = {"st": st, "ec": ec_st, "msg": msg}
    if ec_st == "200":
        print(f"  ✅ {ep} → SUCCESS! TotalCnt={data.get('TotalCnt')}")
        collected_data[ep] = data
    elif "Not Found" not in msg and st != 404:
        print(f"  ⚠️  {ep}: [{ec_st}] {msg[:80]}")
    time.sleep(0.2)

# [2] 매출 데이터도 조회 시도 (알려진 SaveSale 기반)
print("\n[2] 매출(Sale) 조회 다양한 시도")
sale_tests = [
    ("Sale/GetListSale", po_payload),
    ("Sale/GetSaleList", po_payload),
    ("Sale/GetBasicSaleList", {}),
    ("Sale/GetListSaleByDate", po_payload),
    ("Sale/GetListSaleStatus", po_payload),
    ("SaleList/GetListSale", po_payload),
    ("SaleSlip/GetListSaleSlip", po_payload),

    # 이카운트 공식 문서 기반 - 매출 조회 API명
    ("SaleOrder/GetListSaleOrder", po_payload),
    ("SaleOrdering/GetListSaleOrdering", po_payload),
]

for ep, payload in sale_tests:
    st, ec_st, msg, data, full = call_and_report(ep, payload)
    if ec_st == "200":
        print(f"  ✅ {ep} → SUCCESS!")
        collected_data[ep] = data
    elif "Not Found" not in msg and st != 404:
        print(f"  ⚠️  {ep}: [{ec_st}] {msg[:80]}")
    time.sleep(0.2)

# [3] 이카운트가 발주 API에서 사용하는 특정 파라미터명 테스트
# "Delivery Date" 파라미터가 추가됐다고 공지됨 (2024-07-26)
print("\n[3] 발주 조회 파라미터 변형 테스트 (BuyOrder 집중)")
param_tests = [
    {},
    {"BASE_DATE": "20230101"},
    {"BASE_DATE": "20230101", "END_DATE": "20260528"},
    {"SLIP_DATE": "20230101"},
    {"SLIP_DATE": "20230101", "SLIP_DATE_END": "20260528"},
    {"FROM_DATE": "20230101", "TO_DATE": "20260528"},
    {"START_DATE": "20230101", "END_DATE": "20260528"},
    {"DATE_FROM": "20230101", "DATE_TO": "20260528"},
    {"YEAR": "2023"},
    {"MONTH": "2023-01"},
]

for params in param_tests:
    # BuyOrder로 시도
    st, ec_st, msg, data, full = call_and_report("BuyOrder/GetListBuyOrder", params)
    if ec_st == "200":
        print(f"  ✅ BuyOrder/GetListBuyOrder params={params} → SUCCESS!")
        collected_data["BuyOrder/GetListBuyOrder"] = data
    elif "Not Found" not in msg and "404" not in str(st):
        print(f"  ⚠️  BuyOrder params={params}: [{ec_st}] {msg[:80]}")
    time.sleep(0.15)

# [4] 마지막 시도: 이카운트 OAPI V2의 실제 엔드포인트 경로 재탐색
# API 경로에서 v1 vs v2 vs v3 차이 확인
print("\n[4] API 버전 및 경로 변형 탐색")
version_bases = [
    "https://oapibb.ecount.com/OAPI/V1",
    "https://oapibb.ecount.com/OAPI/V2",
    "https://oapibb.ecount.com/OAPI/V3",
    "https://oapibb.ecount.com/OAPI",
]
for vbase in version_bases:
    url = f"{vbase}/BuyOrder/GetListBuyOrder?SESSION_ID={SID}"
    r = requests.post(url, json={"BASE_DATE": "20230101"}, timeout=5)
    try:
        body = r.json()
        st = body.get("Status", "")
        msg = (body.get("Errors") or [{}])[0].get("Message", "")
        print(f"  {vbase}: [{r.status_code}/{st}] {msg[:60]}")
    except:
        print(f"  {vbase}: {r.status_code} - {r.text[:80]}")
    time.sleep(0.2)

# [5] 최종 결과 요약
print("\n" + "="*60)
success_eps = [k for k, v in results.items() if v["ec"] == "200"]
param_error_eps = [k for k, v in results.items() if any(x in v["msg"] for x in ["Parameter", "입력", "필수"])]
auth_eps = [k for k, v in results.items() if "인증" in v["msg"]]

print("최종 결과:")
print(f"  ✅ 성공: {success_eps}")
print(f"  ⚙️  파라미터 오류 (존재): {param_error_eps}")
print(f"  🔒 인증 오류 (비활성): {auth_eps}")

# 데이터 저장
with open("/Users/macmini_ky/ClaudeAITeam/erp/ecount_final_attempt.json", "w") as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "session": SID,
        "results": results,
        "collected_data": {k: {"TotalCnt": v.get("TotalCnt", 0), "Result": v.get("Result", [])[:3]}
                          for k, v in collected_data.items()}
    }, f, ensure_ascii=False, indent=2)

print("\n저장: ecount_final_attempt.json")
