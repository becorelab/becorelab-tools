"""CDP(Playwright)로 1688 상세 페이지 읽기"""
import json
import sys
from playwright.sync_api import sync_playwright

CDP_PORT = 9222


def fetch_1688_detail(product_url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        ctx = browser.contexts[0] if browser.contexts else None
        cookies = []
        if ctx:
            cookies = ctx.cookies(["https://detail.1688.com", "https://1688.com"])

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
        page.goto(product_url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        data = page.evaluate("""() => {
            const qs = (sel) => {
                for (const s of sel.split(',')) {
                    const el = document.querySelector(s.trim());
                    if (el) return el.innerText.trim();
                }
                return '';
            };
            const imgs = Array.from(
                document.querySelectorAll('.detail-gallery img, .tab-img-item img, .main-image img, img[data-role="img"]')
            ).map(i => i.src || i.dataset.src).filter(Boolean).slice(0, 8);

            return {
                page_title: document.title,
                title: qs('.title-text, .mod-detail-title, h1.title'),
                price: qs('.price-text, .price-num, .price-original-text'),
                moq: qs('.unit-text, .mod-detail-purchasing, .start-amount'),
                attrs: (document.querySelector('.offer-attr-list, .mod-detail-description, .obj-attrs')
                    || {innerText: ''}).innerText.trim().substring(0, 2000),
                shop: qs('.shop-name, .company-name, .seller-name'),
                images: imgs,
                body_preview: document.body.innerText.substring(0, 3000)
            };
        }""")

        work_browser.close()
        return data


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://detail.1688.com/offer/987266748920.html"
    print(f"CDP reading: {url}\n")
    data = fetch_1688_detail(url)
    for k, v in data.items():
        if k == "body_preview":
            print(f"\n[body_preview] (first 500 chars)")
            print(v[:500])
        elif k == "images":
            print(f"[images] {len(v)}장")
            for img in v:
                print(f"  - {img[:100]}")
        else:
            val = v[:200] if isinstance(v, str) else v
            print(f"[{k}] {val}")
