#!/usr/bin/env python3
"""
이카운트 ERP 웹 UI 로그인 후 내부 OAPI 문서 접근 시도
이카운트 ERP 웹은 별도 세션으로 운영됨
"""
import requests
import json
import time

COM_CODE = "640682"
USER_ID = "BECORELAB1"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/json",
})

print("=== 이카운트 ERP 웹 내부 OAPI 문서 접근 시도 ===")

# 이카운트 ERP 웹 접속 주소들
# BB존: https://oapi.ecount.com (API용), https://ecerp.com (웹 UI용)
# 실제 이카운트 ERP URL 패턴 탐색

base_urls = [
    "https://oapi.ecount.com",
    "https://oapibb.ecount.com",
    "https://sboapi.ecount.com",
]

print("\n[1] 이카운트 OAPI 서버 루트 확인...")
for base in base_urls:
    try:
        r = requests.get(base, timeout=5)
        print(f"  {base}: {r.status_code}")
        if r.text[:200]:
            print(f"    → {r.text[:150]}")
    except Exception as e:
        print(f"  {base}: 오류 - {str(e)[:60]}")

# OAPI V2 API 목록을 GET으로 접근
print("\n[2] OAPI V2 API 목록 페이지 GET 접근...")

# 이카운트 ERP OAPI 공식 문서가 로그인 후 접근되는 경우
# 세션 쿠키를 사용하여 접근 시도
api_doc_urls = [
    "https://oapi.ecount.com/ECERP/OAPI/OAPIView?lan_type=ko-KR",
    "https://sboapi.ecount.com/ECERP/OAPI/OAPIView?lan_type=ko-KR",
    "https://oapibb.ecount.com/ECERP/OAPI/OAPIView?lan_type=ko-KR",
]
for url in api_doc_urls:
    try:
        r = requests.get(url, timeout=5)
        print(f"  {url.split('/')[-2:]}: {r.status_code}")
        # JSON인지 HTML인지 확인
        if r.headers.get('Content-Type', '').startswith('application/json'):
            try:
                data = r.json()
                print(f"    JSON: {str(data)[:200]}")
            except:
                pass
        else:
            print(f"    HTML: {r.text[:100]}")
    except Exception as e:
        print(f"  오류: {str(e)[:60]}")

print("\n[3] 이카운트 OAPI V2 활성화된 기능 확인...")
# 현재 계정에서 활성화된 API 목록을 조회하는 방법
# - 이카운트 ERP 내 환경설정 > 외부연동 > API 사용 기능 설정 메뉴

# OAPI로 로그인 후 어떤 API가 허용되어 있는지 확인
OAPI_BASE = "https://oapibb.ecount.com/OAPI/V2"
login_resp = requests.post(f"{OAPI_BASE}/OAPILogin", json={
    "COM_CODE": COM_CODE, "USER_ID": USER_ID,
    "API_CERT_KEY": "47a8af0d25e934b19b6bc9d5a890eb1f48",
    "LAN_TYPE": "ko-KR", "ZONE": "BB"
})
SID = login_resp.json()["Data"]["Datas"]["SESSION_ID"]

# 이카운트 ERP는 API 기능을 계정별로 활성화/비활성화 가능
# 활성화된 기능 목록을 조회하는 엔드포인트가 있을 수 있음
auth_check_eps = [
    "OAPIAuth/GetAuthList",
    "OAPIAuth/GetAPIAuthList",
    "OAPIAuth/GetList",
    "Auth/GetAPIList",
    "Auth/GetList",
    "OAPIMenu/GetAuthMenu",
    "OAPIMenu/GetList",
    "OAPI/GetAuthList",
    "Company/GetOAPIAuthList",
    "Setting/GetOAPIAuth",
]

print(f"\n  세션 ID: {SID[:25]}...")
for ep in auth_check_eps:
    url = f"{OAPI_BASE}/{ep}?SESSION_ID={SID}"
    r = requests.post(url, json={}, timeout=5)
    try:
        body = r.json()
        st = body.get("Status", "")
        msg = body.get("Errors", [{}])[0].get("Message", "") if body.get("Errors") else ""
        if "Not Found" not in msg and st != "500":
            print(f"  {ep}: [{r.status_code}/{st}] {msg[:80]}")
            if body.get("Data"):
                print(f"    Data: {str(body['Data'])[:200]}")
    except:
        print(f"  {ep}: {r.status_code} - {r.text[:80]}")
    time.sleep(0.1)

print("\n[4] 발주 데이터 대안 - InventoryBasic으로 수집 가능한 데이터 정리")
# InventoryBasic/GetBasicProductsList는 성공 → 품목 데이터 활용 가능
r = requests.post(f"{OAPI_BASE}/InventoryBasic/GetBasicProductsList?SESSION_ID={SID}",
                  json={}, timeout=10)
data = r.json()
total = data.get("Data", {}).get("TotalCnt", 0)
results = data.get("Data", {}).get("Result", [])
print(f"  품목 수: {total}개")
print(f"  필드 목록: {list(results[0].keys()) if results else 'N/A'}")

# AccountBasic 시도
print("\n[5] 거래처 정보 조회 시도...")
r2 = requests.post(f"{OAPI_BASE}/AccountBasic/GetBasicAccountList?SESSION_ID={SID}",
                   json={}, timeout=10)
body2 = r2.json()
st2 = body2.get("Status", "")
msg2 = (body2.get("Errors") or [{}])[0].get("Message", "")
data2 = body2.get("Data", {})
print(f"  AccountBasic: [{st2}] {msg2[:80]}")
if data2:
    print(f"  Data: {str(data2)[:300]}")
