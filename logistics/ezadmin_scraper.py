#!/usr/bin/env python3
"""
이지어드민 데이터 자동 수집 스크래퍼
- 재고현황 + 주문내역을 Playwright로 스크래핑
"""
import json
import logging
from datetime import date, timedelta
from playwright.sync_api import sync_playwright

from config import EZADMIN

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


def get_browser(p):
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1440, "height": 900},
    )
    page = context.new_page()
    page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, page


def ezadmin_login(page):
    log.info("이지어드민 로그인 중...")
    page.goto(EZADMIN["url"], timeout=30000)
    page.wait_for_timeout(3000)
    page.evaluate(f"document.getElementById('login-domain').value = '{EZADMIN['domain']}'")
    page.evaluate(f"document.getElementById('login-id').value = '{EZADMIN['id']}'")
    page.evaluate(f"document.getElementById('login-pwd').value = '{EZADMIN['pw']}'")
    page.evaluate("document.querySelector('input[type=\"button\"]').click()")
    page.wait_for_timeout(6000)
    # 오버레이 제거
    page.evaluate("document.querySelectorAll('.dim').forEach(el => el.remove())")
    page.wait_for_timeout(500)
    log.info("이지어드민 로그인 완료")


def discover_menu(page):
    """사이드바 메뉴 구조를 탐색해서 페이지 코드 목록 추출"""
    log.info("메뉴 구조 탐색 중...")
    menu_data = page.evaluate("""
    () => {
        const results = [];
        // 메뉴 항목에서 onclick 이벤트의 move_page35 호출 찾기
        const allEls = document.querySelectorAll('*[onclick]');
        allEls.forEach(el => {
            const onclick = el.getAttribute('onclick') || '';
            const text = el.textContent.trim().substring(0, 50);
            if (onclick.includes('move_page')) {
                results.push({text, onclick});
            }
        });
        // 사이드바 메뉴 링크도 확인
        const links = document.querySelectorAll('a[href], span[onclick], div[onclick], li[onclick]');
        links.forEach(el => {
            const onclick = el.getAttribute('onclick') || '';
            const text = el.textContent.trim().substring(0, 50);
            if (text && (onclick.includes('move') || onclick.includes('page'))) {
                results.push({text, onclick});
            }
        });
        return results;
    }
    """)
    return menu_data


if __name__ == "__main__":
    with sync_playwright() as p:
        browser, page = get_browser(p)
        try:
            ezadmin_login(page)
            menu = discover_menu(page)
            print("\n=== 이지어드민 메뉴 구조 ===")
            for item in menu:
                print(f"  {item['text'][:40]:40s} → {item['onclick']}")
            print(f"\n총 {len(menu)}개 메뉴 항목 발견")

            # 페이지 HTML도 저장해서 분석
            page.screenshot(path="/tmp/ezadmin_menu.png")
            print("\n스크린샷 저장: /tmp/ezadmin_menu.png")

            input("\n[Enter] 를 누르면 브라우저를 닫습니다...")
        finally:
            browser.close()
