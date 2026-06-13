#!/usr/bin/env python3
"""
쿠팡 서플라이허브 입고상세내역 크롤러 (최종)
- curl_cffi chrome131 TLS impersonation
- 정확한 v7 로그인 패턴 복제 (supplier.coupang.com 먼저 접속 → Akamai 쿠키 → 수동 리다이렉트)
- SPA 페이지이므로 JS 번들 분석 → API 호출
"""

import json
import os
import re
import time
from datetime import datetime
from html import unescape

from curl_cffi import requests as cf_requests


def _load_env(path=os.path.join(os.path.dirname(__file__), ".env")):
    if os.path.exists(path):
        for _l in open(path, encoding="utf-8"):
            _l = _l.strip()
            if "=" in _l and not _l.startswith("#"):
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())


_load_env()

OUTPUT_PATH = "/Users/macmini_ky/ClaudeAITeam/erp/supplyhub_data.json"
SCREENSHOT_DIR = "/Users/macmini_ky/ClaudeAITeam/erp/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

VENDOR_ID = "A00290275"


def login_with_retry(max_retries=3):
    """로그인 (재시도 포함)"""
    for attempt in range(max_retries):
        print(f"\n{'=' * 60}")
        print(f"로그인 시도 {attempt + 1}/{max_retries}")
        print("=" * 60)

        session = cf_requests.Session(impersonate="chrome131")

        # 1) supplier.coupang.com 첫 접속 (allow_redirects=False) → Akamai 쿠키 확보
        print("  1) supplier.coupang.com 접속 (쿠키 확보)...")
        resp0 = session.get("https://supplier.coupang.com", allow_redirects=False, timeout=30)
        print(f"     Status: {resp0.status_code}")

        cookie_names = [c.name if hasattr(c, 'name') else c for c in session.cookies]
        print(f"     쿠키: {cookie_names}")

        # 2) 리다이렉트 URL 추출 후 로그인 페이지 접속
        redirect_url = resp0.headers.get("Location", "")
        if not redirect_url:
            # allow_redirects=True로 다시 시도
            resp0 = session.get("https://supplier.coupang.com", allow_redirects=True, timeout=30)
            login_html = resp0.text
            login_url = resp0.url
        else:
            print(f"     리다이렉트: {redirect_url[:80]}...")
            resp1 = session.get(redirect_url, allow_redirects=True, timeout=30)
            print(f"     로그인 페이지: {resp1.status_code}, {resp1.url[:80]}...")
            login_html = resp1.text
            login_url = resp1.url

        # 3) loginAction URL 추출
        kc_match = re.search(r'"loginAction"\s*:\s*"([^"]+)"', login_html)
        if not kc_match:
            print("     ❌ loginAction 못 찾음")
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return None

        action_url = unescape(kc_match.group(1))
        print(f"     loginAction 확인")

        # 4) 로그인 POST (allow_redirects=False → 수동 리다이렉트)
        print("  2) 로그인 POST...")
        resp2 = session.post(action_url, data={
            "username": os.environ.get("SUPPLYHUB_ID", ""),
            "password": os.environ.get("SUPPLYHUB_PW", ""),
            "credentialId": "",
        }, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://xauth.coupang.com",
            "Referer": login_url,
        }, allow_redirects=False, timeout=30)
        print(f"     Status: {resp2.status_code}")

        if resp2.status_code == 403:
            print("     ❌ 403 Access Denied (Akamai)")
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 5
                print(f"     {wait}초 대기 후 재시도...")
                time.sleep(wait)
                continue
            return None

        # 5) 리다이렉트 체인 따라가기
        max_redir = 10
        while resp2.status_code in (301, 302, 303, 307) and max_redir > 0:
            redir = resp2.headers.get("Location", "")
            if not redir:
                break
            if redir.startswith("/"):
                base = re.match(r'(https?://[^/]+)', resp2.url or action_url)
                if base:
                    redir = base.group(1) + redir
            print(f"     -> {redir[:80]}...")
            resp2 = session.get(redir, allow_redirects=False, timeout=30)
            print(f"     Status: {resp2.status_code}")
            max_redir -= 1

        if resp2.status_code == 200 and "supplier.coupang.com" in (resp2.url or ""):
            print("  ✅ 로그인 성공!")
            return session

        if resp2.status_code == 403:
            print("     ❌ 콜백에서 403")
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 5
                print(f"     {wait}초 대기 후 재시도...")
                time.sleep(wait)
                continue
            return None

        print(f"     로그인 불확실: {resp2.status_code}, {resp2.url}")
        if attempt < max_retries - 1:
            time.sleep(3)

    return None


def analyze_js_bundle(session):
    """JS 번들에서 API 엔드포인트 추출"""
    print("\n" + "=" * 60)
    print("JS 번들 분석")
    print("=" * 60)

    js_url = "https://assets.coupang.com/front/rs_supplier_hub_web/js/main.73b0b894b81a4c260b8e.js"
    resp = session.get(js_url, timeout=30)

    if resp.status_code != 200:
        print(f"  JS 로드 실패: {resp.status_code}")
        return set()

    js = resp.text
    print(f"  JS 크기: {len(js):,} bytes")

    # settlement/inbound/receiving 관련 경로 추출
    patterns = set()

    # API 호출 패턴: "/api/...", "/bff/...", etc.
    for m in re.finditer(r'["\'](/(?:api|bff|wing|v1|v2)/[^"\']{5,100})["\']', js):
        val = m.group(1)
        if any(kw in val.lower() for kw in ["settlement", "inbound", "receiving", "vendor"]):
            patterns.add(val)

    # 문자열 결합 패턴: "/api/" + "settlement/" + ...
    for m in re.finditer(r'["\'](/[^"\']+settlement[^"\']*)["\']', js):
        patterns.add(m.group(1))

    for m in re.finditer(r'["\'](/[^"\']*inbound[^"\']*)["\']', js):
        patterns.add(m.group(1))

    for m in re.finditer(r'["\'](/[^"\']*receiving[^"\']*)["\']', js):
        patterns.add(m.group(1))

    # route 정의 패턴
    for m in re.finditer(r'path\s*:\s*["\'](/[^"\']+)["\']', js):
        val = m.group(1)
        if any(kw in val.lower() for kw in ["settlement", "inbound", "receiving"]):
            patterns.add(val)

    print(f"  관련 패턴 {len(patterns)}개:")
    for p in sorted(patterns):
        print(f"    {p}")

    # 전체 API 패턴 (10개만)
    all_api = set()
    for m in re.finditer(r'["\'](/(?:api|bff)/[^"\']{5,80})["\']', js):
        all_api.add(m.group(1))
    print(f"\n  전체 /api|bff 패턴 ({len(all_api)}개, 처음 20개):")
    for p in sorted(all_api)[:20]:
        print(f"    {p}")

    return patterns


def fetch_data(session, api_patterns):
    """입고상세내역 데이터 가져오기"""
    print("\n" + "=" * 60)
    print("데이터 수집")
    print("=" * 60)

    # 시도할 URL 목록 구성
    candidate_paths = list(api_patterns)

    # 추가 후보
    extra_paths = [
        "/api/v1/settlement/inbound-details",
        "/api/v1/settlement/inbound-detail",
        "/api/v2/settlement/inbound-details",
        "/api/v2/settlement/inbound-detail",
        "/api/v1/settlement/receiving-details",
        "/api/v1/settlement/receiving-detail",
        "/api/v2/settlement/receiving-details",
        "/api/v2/settlement/receiving-detail",
        "/api/settlement/inbound-detail",
        "/api/settlement/inbound-details",
        "/api/settlement/receiving-detail",
        "/api/settlement/receiving-details",
        "/bff/settlement/inbound-detail",
        "/bff/settlement/inbound-details",
        "/bff/settlement/receiving-detail",
        "/bff/settlement/receiving-details",
        f"/api/v1/vendors/{VENDOR_ID}/settlement/inbound-details",
        f"/api/v2/vendors/{VENDOR_ID}/settlement/inbound-details",
        f"/api/v1/vendors/{VENDOR_ID}/settlement/receiving-details",
    ]

    candidate_paths.extend(extra_paths)

    # 중복 제거
    candidate_paths = list(dict.fromkeys(candidate_paths))

    date_params = [
        "?startDate=2026-05-01&endDate=2026-05-28&pageSize=100&pageNum=1",
        "?startDate=20260501&endDate=20260528&pageSize=100&pageNum=1",
        "?searchStartDate=2026-05-01&searchEndDate=2026-05-28&pageSize=100",
        "?from=2026-05-01&to=2026-05-28&pageSize=100",
        "?startDate=2026-05-01&endDate=2026-05-28",
        "?startDate=20260501&endDate=20260528",
        "",
    ]

    all_data = []
    success_url = None

    tested = set()
    for path in candidate_paths:
        if all_data:
            break
        for params in date_params:
            url = f"https://supplier.coupang.com{path}{params}"
            if url in tested:
                continue
            tested.add(url)

            try:
                resp = session.get(url, timeout=10, headers={
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                })

                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "")
                    if "json" in ct:
                        data = resp.json()
                        items = extract_list(data)
                        if items:
                            all_data = items
                            success_url = url
                            print(f"  ✅ {url}")
                            print(f"     {len(all_data)}건")
                            if all_data:
                                sample = json.dumps(all_data[0], ensure_ascii=False)
                                print(f"     샘플: {sample[:300]}")
                            break
                        elif isinstance(data, dict) and len(data) > 0:
                            # 데이터가 있지만 리스트가 아닌 경우
                            keys = list(data.keys())
                            if len(keys) > 1 or (len(keys) == 1 and keys[0] not in ["timestamp", "status", "error", "message", "path"]):
                                print(f"  ? {url} -> keys: {keys[:10]}")
                elif resp.status_code not in (404, 403, 401, 302, 301, 405):
                    print(f"  ? {url} -> {resp.status_code}")

            except Exception:
                pass

    # 메뉴 API로 정확한 경로 찾기
    if not all_data:
        print("\n  메뉴 API 탐색...")
        menu_apis = [
            "/api/v1/menu",
            "/api/v1/menus",
            "/api/menu",
            "/bff/menu",
            "/bff/v1/menu",
            "/api/v1/lnb",
            "/api/v1/gnb/menus",
        ]

        for path in menu_apis:
            url = f"https://supplier.coupang.com{path}"
            try:
                resp = session.get(url, timeout=10, headers={"Accept": "application/json"})
                if resp.status_code == 200 and "json" in resp.headers.get("content-type", ""):
                    data = resp.json()
                    menu_str = json.dumps(data, ensure_ascii=False)

                    # 정산/입고 관련 URL 추출
                    if "정산" in menu_str or "settlement" in menu_str.lower():
                        print(f"  ✅ 메뉴 API: {url}")

                        # 정산 관련 URL들 추출
                        urls_in_menu = re.findall(r'"(?:url|path|href|link)"\s*:\s*"([^"]*(?:settlement|inbound|receiving)[^"]*)"', menu_str, re.IGNORECASE)
                        print(f"     정산 URL: {urls_in_menu}")

                        for menu_path in urls_in_menu:
                            if not menu_path.startswith("http"):
                                menu_path = f"https://supplier.coupang.com{menu_path}"
                            for dp in date_params:
                                try:
                                    r = session.get(menu_path + dp, timeout=10, headers={"Accept": "application/json"})
                                    if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                                        d = r.json()
                                        items = extract_list(d)
                                        if items:
                                            all_data = items
                                            success_url = menu_path + dp
                                            print(f"  ✅ {success_url} -> {len(all_data)}건")
                                            break
                                except:
                                    pass
                                if all_data:
                                    break
                        break
            except:
                pass

    return all_data, success_url


def extract_list(data):
    """JSON에서 리스트 데이터 추출"""
    if isinstance(data, list) and len(data) > 0:
        return data

    if isinstance(data, dict):
        for key in ["data", "content", "list", "items", "result", "rows", "body", "results", "records"]:
            if key in data:
                val = data[key]
                if isinstance(val, list) and len(val) > 0:
                    return val
                if isinstance(val, dict):
                    # 중첩
                    for k2 in ["data", "content", "list", "items", "result", "rows"]:
                        if k2 in val and isinstance(val[k2], list) and len(val[k2]) > 0:
                            return val[k2]

    return []


def main():
    # 로그인
    session = login_with_retry(max_retries=3)
    if not session:
        print("\n❌ 로그인 실패. Akamai 봇 감지에 의해 차단되었습니다.")
        print("  쿠팡 서플라이허브의 Akamai Bot Manager는 매우 강력합니다.")
        print("  대안:")
        print("  1. 쿠팡 Open API(HMAC) 사용 - 이것이 가장 안정적")
        print("  2. 대표님이 직접 CSV 다운로드 후 파싱")
        print("  3. 시간 간격을 두고 재시도")
        return

    # JS 번들 분석
    api_patterns = analyze_js_bundle(session)

    # 데이터 수집
    all_data, success_url = fetch_data(session, api_patterns)

    # 저장
    print("\n" + "=" * 60)
    print("결과 저장")
    print("=" * 60)

    total_amount = 0
    for row in all_data:
        for key in ["공급가액", "금액", "총금액", "합계", "supplyAmount", "amount", "totalAmount", "supplyPrice"]:
            if key in row:
                try:
                    val = str(row[key]).replace(",", "").replace("원", "").strip()
                    total_amount += int(float(val))
                except:
                    pass
                break

    result = {
        "crawled_at": datetime.now().isoformat(),
        "source": "쿠팡 서플라이허브 - 입고상세내역",
        "period": "2026-05-01 ~ 2026-05-28",
        "total_count": len(all_data),
        "total_amount": total_amount,
        "page_url": success_url or "",
        "data": all_data,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 저장: {OUTPUT_PATH}")
    print(f"  총 건수: {len(all_data)}건")
    print(f"  총 금액: {total_amount:,}원")

    if not all_data:
        print("\n  ⚠️ 데이터를 수집하지 못했습니다.")
        print("  서플라이허브는 완전한 SPA이고 API 엔드포인트를 정확히 파악해야 합니다.")
        print("  수집된 API 패턴을 기반으로 대표님이 직접 브라우저에서")
        print("  Network 탭을 확인해서 정확한 API URL을 알려주시면 자동화할 수 있습니다.")

    print("\n✅ 완료!")


if __name__ == "__main__":
    main()
