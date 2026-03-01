#!/usr/bin/env python3
"""이지어드민 v6 — dim 제거 후 move_page35로 직접 페이지 탐색"""
from playwright.sync_api import sync_playwright
from config import EZADMIN

with sync_playwright() as p:
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

    page.goto(EZADMIN["url"], timeout=30000)
    page.wait_for_timeout(3000)
    page.evaluate(
        f"document.getElementById('login-domain').value = '{EZADMIN['domain']}'"
    )
    page.evaluate(f"document.getElementById('login-id').value = '{EZADMIN['id']}'")
    page.evaluate(f"document.getElementById('login-pwd').value = '{EZADMIN['pw']}'")
    page.evaluate('document.querySelector(\'input[type="button"]\').click()')
    page.wait_for_timeout(8000)

    # 모든 dim + blockUI 제거
    page.evaluate(
        """
        (() => {
            document.querySelectorAll('.dim').forEach(el => el.remove());
            for (const child of document.body.children) {
                if (child.id !== 'wrap') child.style.display = 'none';
            }
            const wrap = document.getElementById('wrap');
            if (wrap) {
                wrap.className = 'wrapper';
                wrap.querySelectorAll('.blockUI, .blockOverlay, .blockMsg, .blockPage').forEach(el => {
                    el.classList.remove('blockUI', 'blockOverlay', 'blockMsg', 'blockPage');
                });
            }
        })()
        """
    )
    page.wait_for_timeout(1000)
    page.screenshot(path="/tmp/ez_v6_clean.png")
    print("S1: cleaned - /tmp/ez_v6_clean.png")

    # 직접 move_page35로 주요 페이지 코드 탐색
    codes = [
        "DC10", "DC20", "DC30", "DC40", "DC50",
        "ST10", "ST20", "ST30",
        "OD10", "OD20", "OD30",
        "PP10", "PP20", "PP30",
        "SA10", "SA20",
        "IV10", "IV20",
        "IM10", "IM20",
    ]

    # 먼저 재고 관련 페이지 직접 이동
    page.evaluate("move_page35('ST10')")
    page.wait_for_timeout(5000)
    page.screenshot(path="/tmp/ez_v6_ST10.png")

    # 현재 페이지의 tab 메뉴 확인 (이지어드민은 탭 구조)
    tabs = page.evaluate(
        """
        (() => {
            const result = [];
            document.querySelectorAll('.tab a, .tabs a, [class*="tab"] a, .tapmenu a, .tap-menu a, ul.tab li a').forEach(a => {
                const text = a.textContent.trim();
                const onclick = a.getAttribute('onclick') || '';
                const href = a.getAttribute('href') || '';
                if (text.length > 0 && text.length < 30) {
                    result.push({text, onclick: onclick.substring(0, 120), href: href.substring(0, 80)});
                }
            });
            return result;
        })()
        """
    )
    bodyText = page.evaluate("document.body.innerText.substring(0, 800)")
    print(f"\n=== ST10 PAGE ===")
    print(f"URL: {page.url}")
    print(f"Tabs ({len(tabs)}): {[t['text'] for t in tabs]}")
    print(f"Text: {bodyText[:300]}")

    # 주문 관련 페이지
    page.evaluate("move_page35('DC10')")
    page.wait_for_timeout(5000)
    page.screenshot(path="/tmp/ez_v6_DC10.png")
    tabs2 = page.evaluate(
        """
        (() => {
            const result = [];
            document.querySelectorAll('.tab a, .tabs a, [class*="tab"] a, .tapmenu a, .tap-menu a, ul.tab li a').forEach(a => {
                const text = a.textContent.trim();
                const onclick = a.getAttribute('onclick') || '';
                if (text.length > 0 && text.length < 30) {
                    result.push({text, onclick: onclick.substring(0, 120)});
                }
            });
            return result;
        })()
        """
    )
    bodyText2 = page.evaluate("document.body.innerText.substring(0, 800)")
    print(f"\n=== DC10 PAGE ===")
    print(f"URL: {page.url}")
    print(f"Tabs ({len(tabs2)}): {[t['text'] for t in tabs2]}")
    print(f"Text: {bodyText2[:300]}")

    # PP10 (상품관리)
    page.evaluate("move_page35('PP10')")
    page.wait_for_timeout(5000)
    tabs3 = page.evaluate(
        """
        (() => {
            const result = [];
            document.querySelectorAll('.tab a, .tabs a, [class*="tab"] a, .tapmenu a, .tap-menu a, ul.tab li a').forEach(a => {
                const text = a.textContent.trim();
                const onclick = a.getAttribute('onclick') || '';
                if (text.length > 0 && text.length < 30) {
                    result.push({text, onclick: onclick.substring(0, 120)});
                }
            });
            return result;
        })()
        """
    )
    bodyText3 = page.evaluate("document.body.innerText.substring(0, 800)")
    print(f"\n=== PP10 PAGE ===")
    print(f"URL: {page.url}")
    print(f"Tabs ({len(tabs3)}): {[t['text'] for t in tabs3]}")
    print(f"Text: {bodyText3[:300]}")

    browser.close()
