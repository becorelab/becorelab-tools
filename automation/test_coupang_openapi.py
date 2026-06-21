#!/usr/bin/env python3
"""쿠팡 윙 OpenAPI 연결 테스트 (그로스 A00940134).
목적: 이지어드민에 물린 OpenAPI 키로 우리가 직접 GET 조회가 되는지 검증.
- 읽기(GET) 전용. 쓰기 API 절대 호출 안 함 (이지어드민 주문흐름 보호).
- 의존성 0 (표준 urllib + hmac).
"""
import gzip
import hashlib
import hmac
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone


def _decode(raw):
    if raw[:2] == b"\x1f\x8b":  # gzip magic
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")

sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
from coupang_openapi_config import COUPANG_OPENAPI

HOST = "https://api-gateway.coupang.com"
CFG = COUPANG_OPENAPI["chaewoom_gross"]


def _auth(method, path, query=""):
    dt = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
    message = dt + method + path + query
    sig = hmac.new(CFG["secret_key"].encode(), message.encode(), hashlib.sha256).hexdigest()
    return (f"CEA algorithm=HmacSHA256, access-key={CFG['access_key']}, "
            f"signed-date={dt}, signature={sig}")


def call(method, path, query=""):
    url = HOST + path + (("?" + query) if query else "")
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", _auth(method, path, query))
    req.add_header("Content-Type", "application/json;charset=UTF-8")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, _decode(r.read())
    except urllib.error.HTTPError as e:
        return e.code, _decode(e.read())
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main():
    v = CFG["vendor_id"]
    print(f"=== 쿠팡 OpenAPI 테스트 (vendor {v}) ===\n")

    # 1) 인증 검증 — 반품지 목록 (가장 가벼운 GET)
    print("[1] 반품지 목록 (인증 검증용)")
    path = f"/v2/providers/openapi/apis/api/v4/vendors/{v}/returnShippingCenters"
    code, body = call("GET", path, "pageNum=1&pageSize=1")
    print(f"   HTTP {code}\n   {body[:400]}\n")

    # 2) 주문서 조회 — 최근 1일 (매출/주문 데이터 존재 확인)
    print("[2] 주문서 조회 (최근 데이터 확인용)")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = f"/v2/providers/openapi/apis/api/v4/vendors/{v}/ordersheets"
    q = f"createdAtFrom={today}&createdAtTo={today}&status=ACCEPT&maxPerPage=1"
    code, body = call("GET", path, q)
    print(f"   HTTP {code}\n   {body[:400]}\n")


if __name__ == "__main__":
    main()
