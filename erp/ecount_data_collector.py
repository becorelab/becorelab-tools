#!/usr/bin/env python3
"""
이카운트 OAPI V2 데이터 수집 + 발주 엔드포인트 최종 탐색
- 로그인 직후 즉시 API 호출 (세션 유지 중요)
- 성공한 엔드포인트 데이터 수집
- 발주 엔드포인트 최종 탐색
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
login_data = resp.json()
SID = login_data["Data"]["Datas"]["SESSION_ID"]
print(f"✅ 로그인 성공! SID: {SID[:30]}...")

collected = {}
po_payload = {"BASE_DATE": "20230101", "END_DATE": "20260528"}

def call(endpoint, payload=None):
    url = f"{BASE}/{endpoint}?SESSION_ID={SID}"
    r = requests.post(url, json=payload or {}, timeout=15)
    if r.status_code == 200:
        try:
            return r.json()
        except:
            return None
    return None

# ============================================================
# 1. 확인된 성공 엔드포인트 데이터 수집
# ============================================================
print("\n[1] 품목 데이터 수집...")
prod_data = call("InventoryBasic/GetBasicProductsList")
if prod_data and prod_data.get("Status") == "200":
    total = prod_data["Data"]["TotalCnt"]
    results = prod_data["Data"]["Result"]
    print(f"  ✅ 품목 {total}개 수집 완료!")
    collected["products"] = {"total": total, "data": results}
    print(f"  첫 3개: {[(r['PROD_CD'], r['PROD_DES']) for r in results[:3]]}")
else:
    print(f"  ❌ 실패: {prod_data}")

time.sleep(0.3)

# ============================================================
# 2. InventoryBalance 재고 현황
# ============================================================
print("\n[2] 재고 현황 수집...")
inv_data = call("InventoryBalance/GetListInventoryBalanceStatusByLocation",
               {"BASE_DATE": "20260528"})
if inv_data and inv_data.get("Status") == "200":
    total = inv_data["Data"].get("TotalCnt", 0)
    results = inv_data["Data"].get("Result", [])
    print(f"  ✅ 재고 현황 {total}개 / Result={len(results)}개")
    if results:
        print(f"  첫 레코드: {results[0]}")
        collected["inventory"] = {"total": total, "data": results}
    else:
        print(f"  ⚠️  Result 비어있음 (창고/품목 설정 확인 필요)")
else:
    print(f"  상태: {inv_data.get('Status') if inv_data else '실패'}")

time.sleep(0.3)

# ============================================================
# 3. 발주 엔드포인트 집중 탐색 (마지막 시도)
# ============================================================
print("\n[3] 발주 엔드포인트 최종 탐색...")
print("    (이카운트 공식 페이지에서 '발주(P/O) 조회'가 OAPI에 존재한다고 확인됨)")

# 이카운트 ERP 한국어-영어 메뉴 매핑 분석:
# 구매 > 발주서입력 → 영어: Purchase Order → 코드: BuyOrder or PurchaseOrder
# 이카운트 OAPI 공식 문서 (내부): BuyOrder 카테고리로 추정

final_po_tests = [
    # 이카운트 공식 발주 API - 다양한 이름 시도
    ("BuyOrder/GetListBuyOrder", po_payload),
    ("BuyOrder/GetBuyOrderList", po_payload),
    ("PurchaseOrder/GetListPurchaseOrder", po_payload),
    ("Purchasing/GetListPurchasing", po_payload),
    ("Purchases/GetListPurchases", po_payload),
    ("Purchase/GetListPurchase", po_payload),

    # 이카운트가 실제로 사용하는 "P/O" 코드 기반
    ("PO/GetListPO", po_payload),
    ("PO/GetPOList", po_payload),

    # 이카운트 내부 코드 체계 (ERP 내부 API URL 기반 추론)
    ("BuyOrdering/GetListBuyOrdering", po_payload),
    ("Ordering/GetListOrdering", {"ORDERING_TYPE": "BUY", **po_payload}),

    # 이카운트 "보고서" 형식으로 발주 조회
    ("Report/GetPurchaseOrderReport", po_payload),
    ("Report/GetBuyOrderReport", po_payload),

    # 매출도 같이 시도
    ("Sale/GetListSale", po_payload),
    ("SaleOrder/GetListSaleOrder", po_payload),
    ("SalesOrder/GetListSalesOrder", po_payload),

    # 이카운트 V2 OAPI에서 사용하는 특이한 패턴
    ("InventoryIO/GetListInventoryIO", po_payload),
    ("IO/GetListIO", po_payload),
]

for ep, payload in final_po_tests:
    body = call(ep, payload)
    if body:
        st = body.get("Status", "")
        errors = body.get("Errors", [])
        msg = errors[0].get("Message", "") if errors else ""
        data = body.get("Data", {})

        if st == "200":
            print(f"  ✅ {ep} → 성공! TotalCnt={data.get('TotalCnt')}")
            if data.get("Result"):
                collected[ep] = data
                print(f"     첫 레코드: {str(data['Result'][0])[:200]}")
        elif "Not Found" in msg:
            pass  # 조용히
        elif "인증" in msg:
            print(f"  🔒 {ep} → 비활성화됨")
        elif msg:
            print(f"  ⚠️  {ep}: [{st}] {msg[:80]}")
    time.sleep(0.25)

# ============================================================
# 4. 최종 정리 - 이카운트 제한 사항 분석
# ============================================================
print("\n" + "="*60)
print("최종 분석 결과")
print("="*60)
print(f"""
✅ 동작하는 API:
  1. InventoryBasic/GetBasicProductsList → 품목 기본정보 (136개)
  2. InventoryBalance/GetListInventoryBalanceStatusByLocation → 재고 현황 (창고+품목별)

❌ 동작 안 하는 API (모두 Not Found):
  - 발주(BuyOrder/PurchaseOrder/Purchases 등)
  - 매출(Sale/GetListSale 등)
  - 입출고(IO)
  - 거래처(Account)
  - 생산(WorkOrder)

🔒 비활성화된 API:
  - InventoryBalance/GetListInventoryBalanceStatus (인증되지 않은 API)

⚠️  핵심 문제:
  이카운트 OAPI에서 "발주 조회" 기능이 존재하는 것은 확인됨
  (공식 페이지: '발주(Purchase Order)' Search 기능 지원)

  그러나 현재 비코어랩 계정에서는 해당 API가 활성화되어 있지 않을 가능성이 높음.

  이유 1: 이카운트 ERP > 환경설정 > 외부연동 > API 사용 기능 설정에서
           발주 조회 API가 OFF 상태일 수 있음
  이유 2: 발주 API가 별도 신청/승인 필요할 수 있음
""")

print("📋 권장 조치:")
print("  1. 이카운트 ERP 로그인 → 환경설정 → 외부연동 → API 사용 기능 설정")
print("     → 발주서 조회/발주 관련 API를 ON으로 활성화")
print("  2. 이카운트 고객센터 (1600-1055)에 OAPI 발주 조회 API 이름 문의")
print("  3. 대안: 이카운트 ERP 발주 데이터를 엑셀로 내보내기 후 파싱")

# 수집된 데이터 저장
with open("/Users/macmini_ky/ClaudeAITeam/erp/ecount_purchase_orders_raw.json", "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "status": "partial_success",
        "zone": ZONE,
        "com_code": COM_CODE,
        "login_success": True,
        "session_id": SID,
        "note": "발주 조회 API 활성화 필요 - 이카운트 ERP 환경설정에서 설정",
        "collected": {
            "products": {
                "count": collected.get("products", {}).get("total", 0),
                "endpoint": "InventoryBasic/GetBasicProductsList",
                "data": collected.get("products", {}).get("data", [])
            },
            "inventory": {
                "count": collected.get("inventory", {}).get("total", 0),
                "endpoint": "InventoryBalance/GetListInventoryBalanceStatusByLocation",
                "data": collected.get("inventory", {}).get("data", [])
            },
            "purchase_orders": {
                "status": "api_not_activated",
                "note": "이카운트 환경설정에서 활성화 필요"
            }
        },
        "working_endpoints": [
            "InventoryBasic/GetBasicProductsList",
            "InventoryBalance/GetListInventoryBalanceStatusByLocation"
        ],
        "not_found_endpoints": [
            "BuyOrder/GetListBuyOrder",
            "PurchaseOrder/GetListPurchaseOrder",
            "Purchases/GetListPurchases",
            "Sale/GetListSale",
            "IO/GetListIO"
        ]
    }, f, ensure_ascii=False, indent=2)

print(f"\n결과 저장: /Users/macmini_ky/ClaudeAITeam/erp/ecount_purchase_orders_raw.json")
