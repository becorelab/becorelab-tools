#!/usr/bin/env python3
"""쿠팡 검색 페이지 구조 inspection"""
import asyncio, re
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0]
        page = await ctx.new_page()

        await page.goto("https://www.coupang.com/np/search?q=하수구+트랩&channel=user", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # 다양한 selector 시도
        selectors = [
            "li[data-product-id]",
            "li.search-product",
            "ul.search-product-list li",
            "[class*='ProductUnit']",
            "[class*='SearchProductUnit']",
            "[class*='productUnit']",
            "a[href*='/vp/products/']",
        ]
        for sel in selectors:
            count = await page.locator(sel).count()
            print(f"  {sel}: {count}")

        # 첫 상품의 HTML 일부 출력
        first_link = await page.query_selector("a[href*='/vp/products/']")
        if first_link:
            parent_html = await first_link.evaluate("el => el.closest('li, [class*=\"product\"]')?.outerHTML?.substring(0, 2000) || el.outerHTML.substring(0,2000)")
            print("\n=== 첫 상품 카드 HTML ===")
            print(parent_html[:2500])

        # 가격/이름이 보이는 클래스 패턴 찾기
        page_text = await page.content()
        # 가격 패턴 찾기
        prices = re.findall(r'(\d{1,3}(?:,\d{3})+)\s*원', page_text)
        print(f"\n페이지 내 가격 패턴 {len(prices)}개. 처음 10개: {prices[:10]}")

        await page.close()

asyncio.run(main())
