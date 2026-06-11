#!/usr/bin/env python3
"""
이카운트 OAPI V2 엔드포인트 탐색 스크립트
- 로그인 후 다양한 엔드포인트 패턴 시도
- 성공한 엔드포인트로 발주 데이터 수집
"""
import requests
import json
import time
from datetime import datetime

# 인증 정보
COM_CODE = "640682"
USER_ID = "BECORELAB1"
API_CERT_KEY = "47a8af0d25e934b19b6bc9d5a890eb1f48"
ZONE = "BB"
BASE_URL = f"https://oapi{ZONE.lower()}.ecount.com/OAPI/V2"
BASE_URL2 = f"https://oapibb.ecount.com/OAPI/V2"

print(f"=== 이카운트 OAPI V2 탐색 시작 ===")
print(f"BASE_URL: {BASE_URL2}")

# 1. 로그인
print("\n[1] 로그인 시도...")
login_resp = requests.post(
    "https://oapibb.ecount.com/OAPI/V2/OAPILogin",
    json={
        "COM_CODE": COM_CODE,
        "USER_ID": USER_ID,
        "API_CERT_KEY": API_CERT_KEY,
        "LAN_TYPE": "ko-KR",
        "ZONE": ZONE
    }
)
login_data = login_resp.json()
print(f"로그인 응답 상태: {login_resp.status_code}")

if login_data.get("Data", {}).get("Datas", {}).get("SESSION_ID"):
    SESSION_ID = login_data["Data"]["Datas"]["SESSION_ID"]
    print(f"✅ 로그인 성공! SESSION_ID: {SESSION_ID[:30]}...")
else:
    print(f"❌ 로그인 실패: {login_data}")
    exit(1)

def try_endpoint(endpoint, payload=None, method="POST"):
    """엔드포인트 시도 후 결과 반환"""
    url = f"{BASE_URL2}/{endpoint}?SESSION_ID={SESSION_ID}"
    try:
        if method == "POST":
            resp = requests.post(url, json=payload or {}, timeout=10)
        else:
            resp = requests.get(url, timeout=10)

        status = resp.status_code
        try:
            body = resp.json()
        except:
            body = resp.text[:300]

        # 결과 분류
        if status == 200:
            if isinstance(body, dict):
                result_code = body.get("Status", body.get("status", ""))
                if "200" in str(result_code) or result_code == 0:
                    return "SUCCESS", body
                elif "404" in str(result_code):
                    return "NOT_FOUND", body
                else:
                    return f"RESULT_{result_code}", body
            return "HTTP_200", body
        elif status == 404:
            return "HTTP_404", body
        else:
            return f"HTTP_{status}", body
    except Exception as e:
        return "ERROR", str(e)

# 2. 발주/구매 관련 엔드포인트 집중 탐색
print("\n[2] 발주/구매/매출 엔드포인트 탐색...")

# 이카운트 OAPI V2 공식 문서 기반 + 알려진 패턴
endpoints_to_test = [
    # === 발주(구매발주) 관련 ===
    ("Purchasing/GetListPurchaseOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Purchasing/GetPurchaseOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("PurchaseOrder/GetPurchaseOrder", {}),
    ("PurchaseOrder/GetListPurchaseOrder", {}),
    ("BuyOrder/GetListBuyOrder", {}),
    ("BuyOrder/GetBuyOrder", {}),

    # 이카운트 V2 공식 슬립 타입별
    ("Slip/GetListSlip", {"SLIP_TYPE": "PO", "BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Slip/GetListSlip", {"SLIP_TYPE": "PU", "BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Slip/GetListSlip", {"SLIP_TYPE": "SO", "BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Slip/GetListSlip", {"SLIP_TYPE": "SA", "BASE_DATE": "20230101", "END_DATE": "20260528"}),

    # 매입 관련
    ("Purchase/GetListPurchase", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Purchase/GetPurchase", {}),
    ("Purchasing/GetListPurchasing", {}),
    ("IO/GetListPurchase", {}),
    ("IO/GetListIO", {"IO_TYPE": "I"}),

    # 매출 관련
    ("Sale/GetListSale", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Sale/GetSale", {}),
    ("Sale/GetListData", {}),

    # 재고 관련
    ("Inventory/GetListInventory", {}),
    ("Stock/GetListStock", {}),

    # 거래처 관련
    ("Account/GetListAccount", {}),
    ("Customer/GetListCustomer", {}),

    # 품목 관련
    ("Product/GetListProduct", {}),
    ("Item/GetListItem", {}),

    # 일반 전표/슬립
    ("Slip/GetSlip", {}),
    ("Slip/GetList", {}),
    ("Voucher/GetListVoucher", {}),

    # 이카운트 공식 문서에서 확인된 패턴
    ("OAPILogin", {}),  # 이미 알고 있는 것
]

results = {}
print(f"\n총 {len(endpoints_to_test)}개 엔드포인트 테스트...")

for endpoint_data in endpoints_to_test:
    if isinstance(endpoint_data, tuple):
        endpoint, payload = endpoint_data
    else:
        endpoint, payload = endpoint_data, {}

    result_type, body = try_endpoint(endpoint, payload)

    # 결과 저장 (같은 엔드포인트 여러 번이면 가장 좋은 결과 유지)
    endpoint_key = endpoint
    if endpoint_key not in results or result_type == "SUCCESS":
        results[endpoint_key] = {
            "result_type": result_type,
            "payload": payload,
            "response_preview": str(body)[:200]
        }

    status_icon = "✅" if result_type == "SUCCESS" else "❌" if "404" in result_type or "NOT_FOUND" in result_type else "⚠️"
    print(f"  {status_icon} {endpoint} [{result_type}] payload={payload}")

    if result_type == "SUCCESS":
        print(f"     → 응답: {str(body)[:300]}")

    time.sleep(0.3)  # 서버 부하 방지

print("\n[3] 더 많은 패턴 탐색...")

# 실제 이카운트 OAPI 문서에서 발견된 패턴들
more_endpoints = [
    # 재고입출고
    ("Inventory/GetListInventoryIO", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("InventoryIO/GetList", {}),

    # 발주 - 다양한 명명 방식
    ("Order/GetListOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Order/GetOrder", {}),
    ("PO/GetListPO", {}),
    ("PO/GetPO", {}),

    # 거래 슬립
    ("Slip/GetListSlip", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Slip/GetListSlip", {"SLIP_KIND": "PO", "BASE_DATE": "20230101", "END_DATE": "20260528"}),

    # 매입발주 전용
    ("PurchaseSlip/GetList", {}),
    ("PurchaseVoucher/GetList", {}),

    # 이카운트 v1 스타일
    ("Sale/GetListSaleOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),

    # EzAdmin에서 확인된 메뉴
    ("EzAdmin/GetList", {}),

    # 현재고
    ("CurrentInventory/GetList", {}),
    ("Inventory/GetCurrentStock", {}),

    # 마스터 데이터
    ("Basic/GetListBasic", {}),
    ("BaseMaster/GetList", {}),
]

for endpoint_data in more_endpoints:
    if isinstance(endpoint_data, tuple):
        endpoint, payload = endpoint_data
    else:
        endpoint, payload = endpoint_data, {}

    result_type, body = try_endpoint(endpoint, payload)

    endpoint_key = f"{endpoint}_{json.dumps(payload)[:30]}"
    results[endpoint_key] = {
        "result_type": result_type,
        "payload": payload,
        "response_preview": str(body)[:200]
    }

    status_icon = "✅" if result_type == "SUCCESS" else "❌" if "404" in result_type or "NOT_FOUND" in result_type else "⚠️"
    print(f"  {status_icon} {endpoint} [{result_type}]")

    if result_type == "SUCCESS":
        print(f"     → 응답: {str(body)[:300]}")

    time.sleep(0.3)

# 4. 결과 요약
print("\n" + "="*60)
print("탐색 결과 요약")
print("="*60)

success_endpoints = [(k, v) for k, v in results.items() if v["result_type"] == "SUCCESS"]
warning_endpoints = [(k, v) for k, v in results.items() if "HTTP_200" in v["result_type"] or "RESULT_" in v["result_type"]]
not_found_endpoints = [(k, v) for k, v in results.items() if "404" in v["result_type"] or "NOT_FOUND" in v["result_type"]]

print(f"\n✅ 성공 ({len(success_endpoints)}개):")
for ep, info in success_endpoints:
    print(f"  - {ep}")
    print(f"    응답: {info['response_preview'][:150]}")

print(f"\n⚠️  200 반환 (데이터 형식 확인 필요) ({len(warning_endpoints)}개):")
for ep, info in warning_endpoints:
    print(f"  - {ep} [{info['result_type']}]: {info['response_preview'][:100]}")

print(f"\n❌ Not Found ({len(not_found_endpoints)}개): {[ep for ep, _ in not_found_endpoints[:5]]}...")

# 결과 저장
output = {
    "timestamp": datetime.now().isoformat(),
    "session_id": SESSION_ID,
    "base_url": BASE_URL2,
    "results": results,
    "summary": {
        "success": [k for k, v in results.items() if v["result_type"] == "SUCCESS"],
        "warning_200": [k for k, v in results.items() if "HTTP_200" in v["result_type"] or "RESULT_" in v["result_type"]],
        "not_found": len(not_found_endpoints),
        "total_tested": len(results)
    }
}

with open("/Users/macmini_ky/ClaudeAITeam/erp/ecount_api_discovery.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n결과 저장 완료: /Users/macmini_ky/ClaudeAITeam/erp/ecount_api_discovery.json")
print(f"SESSION_ID: {SESSION_ID}")
