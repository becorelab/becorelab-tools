#!/usr/bin/env python3
"""
이카운트 OAPI V2 내부 문서 및 메타데이터 접근 시도
+ 이카운트 ERP 웹 UI에서 사용되는 실제 API 엔드포인트 탐색
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
print(f"✅ 로그인: {SID[:30]}...")

def call(endpoint, payload=None, method="POST"):
    url = f"{BASE}/{endpoint}?SESSION_ID={SID}"
    if method == "POST":
        r = requests.post(url, json=payload or {}, timeout=10)
    else:
        r = requests.get(url, timeout=10)
    try:
        body = r.json()
    except:
        body = {"raw": r.text[:500]}
    ec_st = body.get("Status", "") if isinstance(body, dict) else ""
    errors = body.get("Errors", []) if isinstance(body, dict) else []
    msg = errors[0].get("Message", "") if errors else ""
    data = body.get("Data", {}) if isinstance(body, dict) else {}
    return r.status_code, ec_st, msg, data, body

# ============================================================
# 전략 1: 이카운트 OAPI 메타데이터/문서 엔드포인트 접근
# ============================================================
print("\n[전략1] OAPI 메타데이터/내부 문서 엔드포인트")
meta_eps = [
    "OAPIView", "OAPIList", "OAPIInfo",
    "OAPI/GetList", "OAPI/GetAPIList",
    "OAPIMenu/GetList", "OAPIMenu/GetAPIMenu",
    "OAPIGuide/GetList",
    "OAPIDoc/GetList",
    "APIList/GetList",
    "APIMenu/GetList",
    "GetAPIList", "GetOAPIList",
    "OAPILogin/GetAPIList",
    "OAPIAuth/GetList",
    "Help/GetAPIList",
    "Swagger", "swagger",
    "api-docs", "openapi.json",
]
for ep in meta_eps:
    st, ec_st, msg, data, full = call(ep)
    if ec_st == "200" or (st == 200 and "Not Found" not in msg and "404" not in str(st)):
        print(f"  ⚠️  {ep}: [{st}/{ec_st}] {msg[:60]}")
        if data:
            print(f"       {str(data)[:200]}")
    time.sleep(0.1)

# ============================================================
# 전략 2: 이카운트 ERP 웹 UI 내부 API (별도 도메인)
# ============================================================
print("\n[전략2] 이카운트 ERP 웹 내부 API")

# 이카운트 ERP는 ecerp.com 도메인 사용
erp_headers = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
}

# 이카운트 ERP 웹 세션으로 내부 API 접근 시도
erp_urls = [
    "https://ecerp.com/Api/Purchasing/GetPurchaseOrder",
    "https://ecerp.com/Api/Inventory/GetInventoryIO",
    f"https://ecountbb.ecount.com/ECERP/OAPI/OAPIView",
    f"https://oapibb.ecount.com/ECERP/OAPI/OAPIView",
]
for url in erp_urls:
    try:
        r = requests.post(url, headers=erp_headers, json={}, timeout=5)
        print(f"  {url}: {r.status_code} - {r.text[:150]}")
    except Exception as e:
        print(f"  {url}: 오류 - {e}")
    time.sleep(0.2)

# ============================================================
# 전략 3: 이카운트 공개 API 문서 페이지 (다른 URL 패턴)
# ============================================================
print("\n[전략3] 공개 OAPI 문서 다른 URL 패턴")

doc_urls = [
    "https://oapibb.ecount.com/ECERP/OAPI/OAPIView?lan_type=ko-KR",
    "https://oapibb.ecount.com/OAPI/View",
    "https://oapibb.ecount.com/OAPI/V2/OAPIView",
    "https://oapibb.ecount.com/OAPI/V2/Help",
]
for url in doc_urls:
    try:
        r = requests.get(url, timeout=5)
        print(f"  {url.split('?')[0].split('/')[-2:]}: {r.status_code} - {r.text[:200]}")
    except Exception as e:
        print(f"  오류: {e}")
    time.sleep(0.2)

# ============================================================
# 전략 4: 이카운트 내부에서 알려진 SaveXXX → GetListXXX 매핑
# 알려진 Save 엔드포인트 전체 목록에서 GetList 변형 추론
# ============================================================
print("\n[전략4] 알려진 Save 엔드포인트 기반 GetList 추론")

# 이카운트 OAPI 공식 문서에 명시된 Save 엔드포인트들
known_save_patterns = [
    "Sale/SaveSale",           # 매출입력
    "Purchases/SavePurchases", # 구매입력
    # 이카운트 공식 문서에 있는 나머지 Save API들 추론
]

# 이카운트 OAPI V2에서 알려진 모든 API 카테고리 (공식 문서 기반 + 추론)
known_categories = [
    "Sale",
    "Purchases",
    "InventoryBasic",      # 품목 기본 정보
    "InventoryBalance",    # 재고 현황
    "AccountBasic",        # 거래처 기본 정보
]

# 발주 관련으로 추측되는 카테고리 (이카운트 ERP 메뉴 구조 기반)
# 이카운트 ERP 메뉴: 구매 > 발주 > 발주서입력 (BuyOrder)
#                             > 구매입력 (Purchasing/Purchase)
#                  판매 > 수주 > 수주서입력 (SaleOrder)
#                             > 판매입력 (Sale)

# 이카운트 공식 API 문서에서의 실제 API 이름 패턴 (영문 메뉴명 기반)
# 발주 = BuyOrder (Buy + Order)
# 수주 = SaleOrder
# 구매입력 = Purchasing (알려진 Save: Purchases)
# 판매입력 = Sale (알려진 Save: Sale)

get_variants = [
    "GetList",
    "GetListData",
    "GetSlipList",
    "GetListSlip",
    "GetListInfo",
]

# BuyOrder 변형 집중
print("\n  [BuyOrder 변형 집중]")
for get_method in get_variants:
    for cat in ["BuyOrder", "BuyOrdering", "BuyOrderSlip"]:
        ep = f"{cat}/{get_method}{cat.replace('Slip','')}"
        st, ec_st, msg, data, full = call(ep, {"BASE_DATE": "20230101", "END_DATE": "20260528"})
        if "Not Found" not in msg and st != 404:
            print(f"    {ep}: [{ec_st}] {msg[:80]}")
        time.sleep(0.15)

# SaleOrder (수주) 변형
print("\n  [SaleOrder 변형]")
for cat in ["SaleOrder", "SaleOrdering"]:
    for get_method in ["GetListSaleOrder", "GetList", "GetSaleOrderList"]:
        ep = f"{cat}/{get_method}"
        st, ec_st, msg, data, full = call(ep, {"BASE_DATE": "20230101", "END_DATE": "20260528"})
        if "Not Found" not in msg and st != 404:
            print(f"    {ep}: [{ec_st}] {msg[:80]}")
        time.sleep(0.15)

# ============================================================
# 전략 5: 이카운트 OAPI 실제 요청 정보 - HTTP OPTIONS로 확인
# ============================================================
print("\n[전략5] HTTP OPTIONS로 허용 메서드 확인")
try:
    r = requests.options(f"{BASE}/BuyOrder/GetListBuyOrder?SESSION_ID={SID}", timeout=5)
    print(f"  BuyOrder OPTIONS: {r.status_code}, Allow={r.headers.get('Allow', 'N/A')}")
    r2 = requests.options(f"{BASE}/Sale/GetListSale?SESSION_ID={SID}", timeout=5)
    print(f"  Sale OPTIONS: {r2.status_code}, Allow={r2.headers.get('Allow', 'N/A')}")
except Exception as e:
    print(f"  오류: {e}")

# ============================================================
# 전략 6: 이카운트 OAPI 설정에서 API 목록 조회 가능한지 테스트
# ============================================================
print("\n[전략6] 이카운트 OAPI 설정 관련 엔드포인트")
setting_eps = [
    ("OAPIAuth/GetAPIList", {}),
    ("OAPISetting/GetList", {}),
    ("OAPIConfig/GetList", {}),
    ("APIConfig/GetList", {}),
    ("OAPIMenu/GetMenuList", {}),
    ("CommonCode/GetList", {}),
    ("Company/GetCompanyInfo", {}),
    ("User/GetUserInfo", {}),
    ("Zone/GetZoneInfo", {}),
]
for ep, payload in setting_eps:
    st, ec_st, msg, data, full = call(ep, payload)
    if "Not Found" not in msg and st != 404:
        print(f"  {ep}: [{st}/{ec_st}] {msg[:80]}")
        if data:
            print(f"     {str(data)[:200]}")
    time.sleep(0.15)

print("\n탐색 완료!")
