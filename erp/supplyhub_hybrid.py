#!/usr/bin/env python3
"""
쿠팡 서플라이허브 크롤러 - 하이브리드
1. curl_cffi로 로그인 (Akamai 우회)
2. 세션 쿠키를 Playwright에 전달
3. Playwright로 SPA 렌더링 → 입고상세내역 페이지 접근 → 데이터 수집
"""

import json
import os
import re
import time
from datetime import datetime
from html import unescape

from curl_cffi import requests as cf_requests
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


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


def screenshot(page, name):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    try:
        page.screenshot(path=path, full_page=False, timeout=10000)
        print(f"  [screenshot] {path}")
    except:
        print(f"  [screenshot failed] {name}")
    return path


def login_curl_cffi():
    """curl_cffi로 로그인하고 세션 쿠키 반환"""
    print("=" * 60)
    print("curl_cffi 로그인")
    print("=" * 60)

    session = cf_requests.Session(impersonate="chrome131")

    resp0 = session.get("https://supplier.coupang.com", allow_redirects=False, timeout=30)
    redirect_url = resp0.headers.get("Location", "")

    if redirect_url:
        resp1 = session.get(redirect_url, allow_redirects=True, timeout=30)
        login_html = resp1.text
        login_url = resp1.url
    else:
        resp1 = session.get("https://supplier.coupang.com", allow_redirects=True, timeout=30)
        login_html = resp1.text
        login_url = resp1.url

    kc_match = re.search(r'"loginAction"\s*:\s*"([^"]+)"', login_html)
    if not kc_match:
        print("  ❌ loginAction 못 찾음")
        return None, None

    action_url = unescape(kc_match.group(1))

    resp2 = session.post(action_url, data={
        "username": os.environ.get("SUPPLYHUB_ID", ""),
        "password": os.environ.get("SUPPLYHUB_PW", ""),
        "credentialId": "",
    }, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://xauth.coupang.com",
        "Referer": login_url,
    }, allow_redirects=False, timeout=30)

    while resp2.status_code in (301, 302, 303, 307):
        redir = resp2.headers.get("Location", "")
        if not redir:
            break
        if redir.startswith("/"):
            base = re.match(r'(https?://[^/]+)', resp2.url or action_url)
            if base:
                redir = base.group(1) + redir
        resp2 = session.get(redir, allow_redirects=False, timeout=30)

    if resp2.status_code == 200:
        print("  ✅ 로그인 성공!")

        # 쿠키 추출
        cookies = []
        for cookie in session.cookies.jar:
            c = {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain or ".coupang.com",
                "path": cookie.path or "/",
            }
            if cookie.secure:
                c["secure"] = True
            cookies.append(c)

        print(f"  쿠키 {len(cookies)}개 추출")
        return cookies, session

    print(f"  ❌ 로그인 실패: {resp2.status_code}")
    return None, None


def crawl_with_playwright(cookies):
    """Playwright로 SPA 렌더링 후 데이터 수집"""
    print("\n" + "=" * 60)
    print("Playwright SPA 렌더링")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        )

        # 쿠키 설정
        context.add_cookies(cookies)
        print(f"  쿠키 {len(cookies)}개 설정")

        page = context.new_page()
        stealth = Stealth()
        stealth.apply_stealth_sync(page)
        page.set_default_timeout(60000)

        # 네트워크 요청 모니터링 (API 호출 감지)
        api_calls = []

        def on_response(response):
            url = response.url
            if "api" in url.lower() or "settlement" in url.lower() or "inbound" in url.lower():
                try:
                    status = response.status
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        api_calls.append({
                            "url": url,
                            "status": status,
                        })
                except:
                    pass

        page.on("response", on_response)

        # 1) 메인 페이지 접속
        print("  메인 페이지 접속...")
        page.goto("https://supplier.coupang.com", wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        screenshot(page, "hybrid_01_main")
        print(f"  URL: {page.url}")

        body = page.inner_text("body")
        if "Access Denied" in body:
            print("  ❌ Access Denied")
            browser.close()
            return None

        if "xauth" in page.url or "login" in page.url.lower():
            print("  아직 로그인 안됨. 쿠키가 적용되지 않았을 수 있음.")
            # 쿠키 확인
            pw_cookies = context.cookies()
            print(f"  Playwright 쿠키: {len(pw_cookies)}개")
            for c in pw_cookies[:5]:
                print(f"    {c['name']}: {c['value'][:30]}...")

            browser.close()
            return None

        print("  ✅ 메인 페이지 접근 성공!")

        # 2) 정산 페이지로 이동
        print("\n  정산 페이지 이동...")

        # SPA 라우터이므로 hash 또는 pushState 방식
        # 메뉴 클릭
        time.sleep(3)  # SPA 완전 로딩 대기

        # 메뉴 탐색 - 스크린샷으로 확인
        screenshot(page, "hybrid_02_loaded")

        # 왼쪽 사이드바 또는 상단 메뉴에서 정산 찾기
        all_text = page.inner_text("body")
        print(f"  페이지 텍스트 길이: {len(all_text)}")

        # 정산 키워드 있는지
        for kw in ["정산", "입고", "Settlement", "물류"]:
            if kw in all_text:
                print(f"  ✅ '{kw}' 포함")

        # 모든 메뉴 아이템 클릭 가능한 것들 확인
        all_links = page.query_selector_all("a, [role='menuitem'], [class*='menu'], [class*='nav'] span")
        menu_texts = []
        for el in all_links:
            try:
                txt = el.inner_text().strip()
                if txt and len(txt) < 30:
                    menu_texts.append(txt)
            except:
                pass

        unique_menus = list(dict.fromkeys(menu_texts))
        print(f"  메뉴 항목 ({len(unique_menus)}개):")
        for m in unique_menus[:30]:
            print(f"    - {m}")

        # 정산 메뉴 클릭
        for kw in ["정산", "정산관리"]:
            try:
                el = page.query_selector(f'text="{kw}"')
                if el:
                    el.click()
                    time.sleep(3)
                    screenshot(page, "hybrid_03_settlement")
                    print(f"  '{kw}' 클릭!")

                    # 하위 메뉴 확인
                    sub_text = page.inner_text("body")
                    for sub_kw in ["입고상세", "입고 상세", "입고내역"]:
                        if sub_kw in sub_text:
                            sub_el = page.query_selector(f'text="{sub_kw}"')
                            if sub_el:
                                sub_el.click()
                                time.sleep(3)
                                print(f"  '{sub_kw}' 클릭!")
                                break
                    break
            except:
                continue

        # SPA 해시 라우팅 시도
        spa_routes = [
            "https://supplier.coupang.com/#/settlement",
            "https://supplier.coupang.com/#/settlement/inbound-detail",
            "https://supplier.coupang.com/settlement",
        ]

        for route in spa_routes:
            try:
                page.goto(route, wait_until="domcontentloaded", timeout=15000)
                time.sleep(3)
                bt = page.inner_text("body")
                if "입고" in bt or "정산" in bt:
                    print(f"  ✅ {route}")
                    screenshot(page, "hybrid_04_settlement_page")
                    break
            except:
                continue

        # 감지된 API 호출 확인
        print(f"\n  감지된 API 호출: {len(api_calls)}개")
        for call in api_calls:
            print(f"    [{call['status']}] {call['url']}")

        # 3) 데이터 수집
        print("\n  데이터 수집...")

        screenshot(page, "hybrid_05_current")
        print(f"  현재 URL: {page.url}")

        # 기간 설정 시도
        date_inputs = page.query_selector_all('input[type="date"], input[class*="date"], input[placeholder*="날짜"], input[placeholder*="YYYY"]')
        print(f"  날짜 필드: {len(date_inputs)}개")

        # 조회 버튼
        for text in ["조회", "검색"]:
            btn = page.query_selector(f'button:has-text("{text}")')
            if btn:
                try:
                    btn.click()
                    time.sleep(5)
                    print(f"  ✅ {text} 클릭")
                except:
                    pass

        # 테이블 수집
        all_data = []
        headers = []

        tables = page.query_selector_all("table")
        print(f"  테이블: {len(tables)}개")

        for table in tables:
            ths = table.query_selector_all("th")
            if ths:
                headers = [th.inner_text().strip() for th in ths]
                print(f"  헤더: {headers}")

            rows = table.query_selector_all("tbody tr")
            for row in rows:
                cells = row.query_selector_all("td")
                if not cells:
                    continue
                values = [c.inner_text().strip() for c in cells]
                if any(values):
                    row_dict = {}
                    for i, v in enumerate(values):
                        key = headers[i] if i < len(headers) else f"col_{i}"
                        row_dict[key] = v
                    all_data.append(row_dict)

        # 그리드
        if not all_data:
            grid_rows = page.query_selector_all('[role="row"]')
            if grid_rows:
                for row in grid_rows:
                    hcells = row.query_selector_all('[role="columnheader"]')
                    if hcells:
                        headers = [c.inner_text().strip() for c in hcells]
                        continue
                    cells = row.query_selector_all('[role="gridcell"]')
                    if cells:
                        values = [c.inner_text().strip() for c in cells]
                        if any(values):
                            row_dict = {}
                            for i, v in enumerate(values):
                                key = headers[i] if i < len(headers) else f"col_{i}"
                                row_dict[key] = v
                            all_data.append(row_dict)

        print(f"  수집: {len(all_data)}건")

        # 최종 API 호출 확인
        print(f"\n  총 감지 API 호출: {len(api_calls)}개")
        for call in api_calls:
            print(f"    [{call['status']}] {call['url']}")

        screenshot(page, "hybrid_final")
        browser.close()

        return all_data, headers, api_calls


def main():
    # 1) curl_cffi로 로그인
    cookies, session = login_curl_cffi()
    if not cookies:
        print("\n❌ 로그인 실패")
        return

    # 2) Playwright에 쿠키 전달하여 SPA 렌더링
    result = crawl_with_playwright(cookies)

    if result is None:
        print("\n❌ Playwright 접근 실패")
        return

    all_data, headers, api_calls = result

    # 3) 저장
    print("\n" + "=" * 60)
    print("저장")
    print("=" * 60)

    total_amount = 0
    for row in all_data:
        for key in ["공급가액", "금액", "총금액"]:
            if key in row:
                try:
                    total_amount += int(row[key].replace(",", "").replace("원", "").strip())
                except:
                    pass
                break

    output = {
        "crawled_at": datetime.now().isoformat(),
        "source": "쿠팡 서플라이허브 - 입고상세내역",
        "period": "2026-05-01 ~ 2026-05-28",
        "total_count": len(all_data),
        "total_amount": total_amount,
        "headers": headers,
        "api_calls_detected": [c["url"] for c in api_calls],
        "data": all_data,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 저장: {OUTPUT_PATH}")
    print(f"  총 건수: {len(all_data)}건")
    print(f"  총 금액: {total_amount:,}원")
    print(f"  감지된 API: {len(api_calls)}개")

    if not all_data and api_calls:
        print("\n  ⚡ API 호출이 감지되었지만 데이터 수집은 실패했습니다.")
        print("  감지된 API URL을 분석하면 직접 데이터를 가져올 수 있습니다:")
        for call in api_calls:
            print(f"    {call['url']}")

    print("\n✅ 완료!")


if __name__ == "__main__":
    main()
