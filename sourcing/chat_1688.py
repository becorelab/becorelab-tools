"""CDP로 1688 판매자 채팅 시도"""
import json
import sys
import time
from playwright.sync_api import sync_playwright

CDP_PORT = 9222


def chat_1688(product_url: str, message: str = ""):
    with sync_playwright() as p:
        # 1) 기존 Chrome에서 1688 쿠키 가져오기
        browser = p.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        ctx = browser.contexts[0] if browser.contexts else None
        cookies = []
        if ctx:
            cookies = ctx.cookies([
                "https://detail.1688.com",
                "https://1688.com",
                "https://www.1688.com",
                "https://login.1688.com",
                "https://message.1688.com",
            ])
            print(f"1688 cookies: {len(cookies)}개")

        # 2) 화면 밖 브라우저
        work_browser = p.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--window-position=-10000,0",
                "--window-size=1280,900",
            ],
        )
        work_ctx = work_browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36"
            ),
        )
        if cookies:
            work_ctx.add_cookies(cookies)

        page = work_ctx.new_page()

        # 3) 상품 페이지 열기
        print(f"Opening: {product_url}")
        page.goto(product_url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        # 4) 로그인 상태 확인
        login_status = page.evaluate("""() => {
            const loginBtn = document.querySelector('.login-text, .login-btn, a[href*="login"]');
            const userInfo = document.querySelector('.user-name, .member-name, .buyer-name');
            return {
                logged_in: !!userInfo,
                login_btn: loginBtn ? loginBtn.innerText : '',
                user: userInfo ? userInfo.innerText : '',
                title: document.title
            };
        }""")
        print(f"Login status: {json.dumps(login_status, ensure_ascii=False)}")

        # 5) 판매자 연락 버튼 찾기
        contact_info = page.evaluate("""() => {
            const results = {};

            // 왕왕 채팅 버튼
            const wangwang = document.querySelector(
                'a[href*="wangwang"], a[data-role="im"], .im-ww, ' +
                '.wangwang-btn, .contact-ww, [class*="wangwang"], ' +
                'a[href*="mos.m.taobao"], .im-container a'
            );
            results.wangwang = wangwang ? {
                text: wangwang.innerText.trim(),
                href: wangwang.href || '',
                class: wangwang.className
            } : null;

            // 联系供应商 버튼
            const contact = document.querySelector(
                'a[href*="contact"], button[class*="contact"], ' +
                '.supplier-contact, .contact-btn, ' +
                '[class*="inquiry"], a[href*="inquiry"], ' +
                'a[href*="message"], .btn-contact'
            );
            results.contact_btn = contact ? {
                text: contact.innerText.trim(),
                href: contact.href || '',
                class: contact.className
            } : null;

            // 전화번호
            const phone = document.querySelector('[class*="phone"], [class*="tel"]');
            results.phone = phone ? phone.innerText.trim() : null;

            // 가게 이름/링크
            const shop = document.querySelector(
                '.shop-name a, .company-name a, .seller-name a, ' +
                'a[href*="shop"], a[href*="winport"]'
            );
            results.shop = shop ? {
                text: shop.innerText.trim(),
                href: shop.href || ''
            } : null;

            // 페이지 내 모든 "联系" 또는 "咨询" 관련 요소
            const allLinks = Array.from(document.querySelectorAll('a, button'));
            results.contact_links = allLinks
                .filter(el => {
                    const t = el.innerText || '';
                    return t.includes('联系') || t.includes('咨询') ||
                           t.includes('立即') || t.includes('contact') ||
                           t.includes('chat') || t.includes('询价');
                })
                .map(el => ({
                    tag: el.tagName,
                    text: el.innerText.trim().substring(0, 50),
                    href: el.href || '',
                    class: el.className.substring(0, 80)
                }))
                .slice(0, 10);

            return results;
        }""")
        print(f"\nContact info:")
        print(json.dumps(contact_info, ensure_ascii=False, indent=2))

        # 6) 페이지 하단 연락 영역 캡처
        body_snippet = page.evaluate("""() => {
            const body = document.body.innerText;
            // 연락/채팅 관련 텍스트 주변 추출
            const idx = body.indexOf('联系');
            if (idx > -1) return body.substring(Math.max(0, idx-100), idx+200);
            const idx2 = body.indexOf('立即');
            if (idx2 > -1) return body.substring(Math.max(0, idx2-100), idx2+200);
            return body.substring(0, 500);
        }""")
        print(f"\nBody snippet around contact:\n{body_snippet[:500]}")

        work_browser.close()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://detail.1688.com/offer/858054829289.html"
    chat_1688(url)
