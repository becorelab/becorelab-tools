#!/usr/bin/env python3
"""
이카운트 sboapi 서버 집중 탐색
- sboapi vs oapi 서버 비교
- 알려진 패턴 기반 발주 엔드포인트 탐색
- 조회(GetList) vs 입력(Save) 패턴
"""
import requests
import json
import time
from datetime import datetime

COM_CODE = "640682"
USER_ID = "BECORELAB1"
API_CERT_KEY = "47a8af0d25e934b19b6bc9d5a890eb1f48"
ZONE = "BB"

# 두 서버 모두 시도
SERVERS = {
    "sboapi": f"https://sboapibb.ecount.com/OAPI/V2",
    "oapi": f"https://oapibb.ecount.com/OAPI/V2",
}

print("=== 이카운트 sboapi 서버 집중 탐색 ===")

# 로그인 (두 서버에 모두 로그인 시도)
sessions = {}
for server_name, base_url in SERVERS.items():
    login_url = f"{base_url.replace('/OAPI/V2', '')}/OAPI/V2/OAPILogin"
    try:
        resp = requests.post(login_url, json={
            "COM_CODE": COM_CODE, "USER_ID": USER_ID,
            "API_CERT_KEY": API_CERT_KEY, "LAN_TYPE": "ko-KR", "ZONE": ZONE
        }, timeout=10)
        data = resp.json()
        sid = data.get("Data", {}).get("Datas", {}).get("SESSION_ID")
        if sid:
            sessions[server_name] = (base_url, sid)
            print(f"✅ {server_name} 로그인 성공: {sid[:20]}...")
        else:
            print(f"❌ {server_name} 로그인 실패: {data}")
    except Exception as e:
        print(f"❌ {server_name} 로그인 오류: {e}")

def try_ep(base_url, session_id, endpoint, payload=None):
    url = f"{base_url}/{endpoint}?SESSION_ID={session_id}"
    try:
        resp = requests.post(url, json=payload or {}, timeout=10)
        status = resp.status_code
        try:
            body = resp.json()
        except:
            body = resp.text[:200]

        if status == 200 and isinstance(body, dict):
            ec_status = body.get("Status", "")
            errors = body.get("Errors", [])
            err_msg = errors[0].get("Message", "") if errors else ""
            data = body.get("Data", {})
            return ec_status, err_msg, data, body
        return str(status), "", {}, body
    except Exception as e:
        return "ERR", str(e), {}, {}

# 알려진 성공 패턴 기반 발주 엔드포인트 집중 탐색
print("\n[발주/구매 관련 엔드포인트 탐색]")

# 이카운트 공식 패턴: 동사(카테고리) + 명사(리소스)
# 알려진: Purchases/SavePurchases, Sale/SaveSale, InventoryBalance/GetListInventoryBalanceStatusByLocation
# InventoryBasic/GetBasicProductsList

# 발주 관련 다양한 패턴 시도
purchase_order_endpoints = [
    # 발주(구매발주) - BuyOrder 패턴
    ("BuyOrder/SaveBuyOrder", {"BASE_DATE": "20230101"}),
    ("BuyOrder/GetListBuyOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("BuyOrder/GetBuyOrderList", {}),

    # 구매발주 - PurchaseOrder 패턴
    ("PurchaseOrder/SavePurchaseOrder", {}),
    ("PurchaseOrder/GetListPurchaseOrder", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),

    # Purchasing 패턴 (구매입력)
    ("Purchasing/SavePurchasing", {}),
    ("Purchasing/GetListPurchasing", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Purchasing/GetPurchasingList", {}),

    # 알려진 SavePurchases → GetListPurchases 추론
    ("Purchases/GetListPurchases", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Purchases/GetPurchasesList", {}),

    # Sale 패턴에서 추론 (Sale/SaveSale → Sale/GetListSale)
    ("Sale/GetListSale", {"BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("Sale/GetSaleList", {}),
    ("Sale/GetListSaleOrder", {}),

    # IO (입출고) 패턴
    ("IO/SaveIO", {}),
    ("IO/GetListIO", {"IO_TYPE": "I", "BASE_DATE": "20230101", "END_DATE": "20260528"}),
    ("IO/GetIOList", {}),

    # 재고 관련
    ("InventoryBalance/GetListInventoryBalance", {}),
    ("InventoryBalance/GetListInventoryBalanceStatus", {}),
    # 알려진 것: InventoryBalance/GetListInventoryBalanceStatusByLocation
    ("InventoryBalance/GetListInventoryBalanceStatusByLocation", {}),

    # 품목 관련 (알려진 것: InventoryBasic/GetBasicProductsList)
    ("InventoryBasic/GetBasicProductsList", {}),

    # 거래처
    ("AccountBasic/GetBasicAccountList", {}),
    ("Account/GetListAccount", {}),

    # 전표 직접 조회
    ("Slip/GetListSlip", {"BASE_DATE": "20230101", "END_DATE": "20260528", "SLIP_TYPE": "PO"}),
    ("Slip/GetListSlip", {"BASE_DATE": "20230101", "END_DATE": "20260528", "SLIP_KIND": "B"}),

    # 추가 패턴
    ("GoodsDelivery/GetListGoodsDelivery", {}),  # 출하/배달
    ("GoodsReceipt/GetListGoodsReceipt", {}),    # 입고
    ("WorkOrder/GetListWorkOrder", {}),           # 작업지시
]

all_results = []

for server_name, (base_url, sid) in sessions.items():
    print(f"\n--- {server_name} 서버 ({base_url}) ---")
    for ep_data in purchase_order_endpoints:
        endpoint, payload = ep_data
        ec_status, err_msg, data, full_body = try_ep(base_url, sid, endpoint, payload)

        # 결과 분류
        if ec_status == "200":
            icon = "✅ SUCCESS"
        elif "Not Found" in err_msg or ec_status == "500" and "Not Found" in str(full_body):
            icon = "❌ Not Found"
        elif ec_status == "404":
            icon = "❌ HTTP 404"
        else:
            icon = f"⚠️  [{ec_status}]"

        # 중요한 것만 출력 (Not Found 제외)
        if "Not Found" not in err_msg and "404" not in str(ec_status):
            print(f"  {icon} {endpoint}")
            print(f"       Status={ec_status}, Msg={err_msg[:100]}")
            if data:
                print(f"       Data={str(data)[:200]}")

        result = {
            "server": server_name,
            "endpoint": endpoint,
            "payload": payload,
            "ec_status": ec_status,
            "err_msg": err_msg,
            "has_data": bool(data),
            "data_preview": str(data)[:300]
        }
        if ec_status == "200":
            result["full_response"] = full_body
        all_results.append(result)

        time.sleep(0.2)

# 성공 케이스 요약
print("\n" + "="*60)
print("성공/주목할 만한 결과:")
for r in all_results:
    if r["ec_status"] == "200":
        print(f"  ✅ [{r['server']}] {r['endpoint']}")
        print(f"     {r['data_preview'][:200]}")
    elif "Not Found" not in r["err_msg"] and r["ec_status"] not in ["500", "404"]:
        print(f"  ⚠️  [{r['server']}] {r['endpoint']} → {r['ec_status']}: {r['err_msg'][:80]}")

# 저장
output = {
    "timestamp": datetime.now().isoformat(),
    "servers_tested": list(sessions.keys()),
    "results": all_results,
    "successes": [r for r in all_results if r["ec_status"] == "200"]
}
with open("/Users/macmini_ky/ClaudeAITeam/erp/ecount_sboapi_discovery.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\n결과 저장: /Users/macmini_ky/ClaudeAITeam/erp/ecount_sboapi_discovery.json")
