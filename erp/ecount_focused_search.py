#!/usr/bin/env python3
"""
이카운트 OAPI V2 정밀 탐색
- 알려진 성공 패턴 기반 발주 엔드포인트 추론
- InventoryBalance, InventoryBasic 등 알려진 카테고리 기반
- 다양한 파라미터 조합 시도
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

# 로그인
resp = requests.post(f"{BASE}/OAPILogin", json={
    "COM_CODE": COM_CODE, "USER_ID": USER_ID,
    "API_CERT_KEY": API_CERT_KEY, "LAN_TYPE": "ko-KR", "ZONE": ZONE
})
SID = resp.json()["Data"]["Datas"]["SESSION_ID"]
print(f"✅ 로그인 완료: {SID[:25]}...")

def call(endpoint, payload=None):
    url = f"{BASE}/{endpoint}?SESSION_ID={SID}"
    r = requests.post(url, json=payload or {}, timeout=10)
    try:
        body = r.json()
    except:
        body = {"raw": r.text[:300]}
    st = r.status_code
    ec_st = body.get("Status", "") if isinstance(body, dict) else ""
    errors = body.get("Errors", []) if isinstance(body, dict) else []
    msg = errors[0].get("Message", "") if errors else ""
    data = body.get("Data", {}) if isinstance(body, dict) else {}
    return st, ec_st, msg, data, body

def show(endpoint, st, ec_st, msg, data, full):
    if ec_st == "200":
        print(f"  ✅ {endpoint} → 성공! TotalCnt={data.get('TotalCnt', '?')}")
        if data.get("Result"):
            print(f"     첫 레코드: {str(data['Result'][0])[:200]}")
    elif "인증되지 않은" in msg:
        print(f"  🔒 {endpoint} → 인증 안됨 (비활성화)")
    elif "Check Parameter" in msg or "필수 입력" in msg or "입력 오류" in msg:
        print(f"  ⚙️  {endpoint} → 파라미터 오류: {msg}")
    elif "Not Found" in msg:
        pass  # Not Found는 출력 안 함
    elif st == 404:
        pass  # HTTP 404도 출력 안 함
    else:
        print(f"  ⚠️  {endpoint} → [{st}/{ec_st}] {msg[:80]}")

all_results = {}

# ============================================================
# 1. 알려진 InventoryBalance 엔드포인트 - 파라미터 조합 테스트
# ============================================================
print("\n[1] InventoryBalance 파라미터 탐색...")

inv_bal_tests = [
    {"BASE_DATE": "20230101"},
    {"BASE_DATE": "20230101", "END_DATE": "20260528"},
    {"BASE_DATE": "20230101", "END_DATE": "20260528", "WH_CD": ""},
    {},
]
for p in inv_bal_tests:
    st, ec_st, msg, data, full = call("InventoryBalance/GetListInventoryBalanceStatusByLocation", p)
    print(f"  파라미터={p}: [{ec_st}] {msg[:80]}")
    if ec_st == "200":
        print(f"  ✅ 성공! {str(data)[:300]}")

# ============================================================
# 2. 이카운트 내부 카테고리명 추론 집중 탐색
# ============================================================
print("\n[2] 발주/매출/매입 카테고리 집중 탐색...")

# 이카운트 ERP 메뉴 구조 기반:
# - 재고: Inventory → InventoryBasic, InventoryBalance, InventoryIO
# - 구매: Purchasing → PurchaseOrder(발주), Purchase(구매입력)
# - 판매: Sale → SaleOrder(수주), Sale(판매입력)
# - 입출고: IO → IncomingIO(입고), OutgoingIO(출고)

test_endpoints = [
    # InventoryBasic 계열 (알려진 성공 패턴)
    ("InventoryBasic/GetBasicProductsList", {}),
    ("InventoryBasic/GetBasicAccountList", {}),
    ("InventoryBasic/GetBasicWarehouseList", {}),

    # InventoryIO 계열 (입출고)
    ("InventoryIO/GetListInventoryIO", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("InventoryIO/GetListIO", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("InventoryIO/SaveInventoryIO", {}),

    # 발주(구매발주)
    ("PurchaseOrder/GetListPurchaseOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("PurchaseOrder/SavePurchaseOrder", {}),

    # 구매입력
    ("Purchase/GetListPurchase", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Purchase/SavePurchase", {}),

    # Purchasing 계열
    ("Purchasing/GetListPurchasing", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Purchasing/SavePurchasing", {}),

    # Purchases 계열 (알려진 SavePurchases 기반)
    ("Purchases/GetListPurchases", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Purchases/SavePurchases", {}),

    # 매출(판매)
    ("Sale/GetListSale", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Sale/SaveSale", {}),  # 이미 알려진 것 (데이터 입력 오류 = 존재함)
    ("Sale/GetListSaleOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("SaleOrder/GetListSaleOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),

    # 현재고 (알려진 GetListInventoryBalanceStatusByLocation 기반)
    ("InventoryBalance/GetListInventoryBalanceStatus", {}),
    ("InventoryBalance/GetListInventoryBalance", {"BASE_DATE": "20230101"}),

    # 전표 조회
    ("Slip/GetListPurchaseOrderSlip", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Slip/GetListPurchaseSlip", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Slip/GetListSaleSlip", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),

    # 주문/발주 통합
    ("Order/GetListOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Order/GetListPurchaseOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),

    # 거래처별 조회
    ("AccountBasic/GetBasicAccountList", {}),

    # 생산 관련
    ("WorkOrder/GetListWorkOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Production/GetListProduction", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),

    # 이카운트 쇼핑 API 계열
    ("Shop/GetListOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Shopping/GetListOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
]

for ep, payload in test_endpoints:
    st, ec_st, msg, data, full = call(ep, payload)
    show(ep, st, ec_st, msg, data, full)
    all_results[ep] = {
        "http_status": st, "ec_status": ec_st, "message": msg,
        "has_data": bool(data), "payload": payload
    }
    time.sleep(0.25)

# ============================================================
# 3. 성공한 InventoryBasic/GetBasicProductsList 전체 데이터 수집
# ============================================================
print("\n[3] 품목 데이터 전체 수집 (성공 케이스)...")
st, ec_st, msg, data, full = call("InventoryBasic/GetBasicProductsList")
if ec_st == "200":
    print(f"  품목 수: {data.get('TotalCnt', 0)}개")
    print(f"  첫 5개: {[r.get('PROD_CD','') + ':' + r.get('PROD_DES','') for r in (data.get('Result') or [])[:5]]}")

# ============================================================
# 4. 매출 데이터 - Sale/SaveSale 기반 파라미터 추론
# ============================================================
print("\n[4] Sale/GetList 변형 집중 테스트...")

sale_variants = [
    ("Sale/GetListSale", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Sale/GetListSale", {"BASE_DATE": "20230101"}),
    ("Sale/GetListSale", {}),
    ("Sale/GetSaleList", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Sale/ListSale", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Sale/GetList", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("SaleList/GetList", {}),
    ("SaleList/GetListSale", {}),
]

for ep, payload in sale_variants:
    st, ec_st, msg, data, full = call(ep, payload)
    if ec_st == "200" or ("Not Found" not in msg and "404" not in str(st)):
        print(f"  [{st}/{ec_st}] {ep}: {msg[:80]}")
    time.sleep(0.2)

# ============================================================
# 5. 결과 요약
# ============================================================
print("\n" + "="*60)
print("최종 결과 요약")
print("="*60)

success = [k for k, v in all_results.items() if v["ec_status"] == "200"]
param_error = [k for k, v in all_results.items() if any(x in v["message"] for x in ["Check Parameter", "필수 입력", "입력 오류"])]
auth_error = [k for k, v in all_results.items() if "인증되지 않은" in v["message"]]
not_found = [k for k, v in all_results.items() if "Not Found" in v["message"] or v["http_status"] == 404]

print(f"\n✅ 성공: {success}")
print(f"⚙️  파라미터 오류 (엔드포인트 존재): {param_error}")
print(f"🔒 인증 안됨 (비활성화): {auth_error}")
print(f"❌ Not Found: {len(not_found)}개")

# 저장
with open("/Users/macmini_ky/ClaudeAITeam/erp/ecount_focused_search.json", "w") as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "session_id": SID,
        "summary": {"success": success, "param_error": param_error, "auth_error": auth_error, "not_found_count": len(not_found)},
        "all_results": all_results
    }, f, ensure_ascii=False, indent=2)

print("\n저장 완료: ecount_focused_search.json")
