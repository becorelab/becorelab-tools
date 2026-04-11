#!/usr/bin/env python3
"""CDP로 쿠팡 배수구 트랩 Top 상품 실제 페이지 크롤"""
import asyncio, json, re
from playwright.async_api import async_playwright

CDP_URL = "http://localhost:9222"

PRODUCTS = [
    ("18. 냄새제로 SM-50D (1등, 리뷰 33K)", "https://www.coupang.com/vp/products/198789547"),
    ("23. 리빙트리 (저가 7,090원)", "https://www.coupang.com/vp/products/2098148935"),
    ("4. 에코바스 (저가 7,900원)", "https://www.coupang.com/vp/products/188789547"),
]

async def fetch_search(page, keyword):
    """검색 결과 페이지에서 상위 상품 가격/구성 추출"""
    url = f"https://www.coupang.com/np/search?q={keyword}&channel=user"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2500)
        title = await page.title()
        if "Access Denied" in title or "Error" in title:
            return {"error": "blocked", "title": title}
        # 검색 결과 카드 추출
        cards = await page.query_selector_all("li.search-product, [class*='search-product']")
        results = []
        for c in cards[:15]:
            try:
                name_el = await c.query_selector(".name, [class*='product-name']")
                price_el = await c.query_selector(".price-value, [class*='price-value']")
                rating_el = await c.query_selector(".rating-total-count, [class*='rating']")
                if not name_el:
                    continue
                name = (await name_el.inner_text()).strip()[:120]
                price = (await price_el.inner_text()).strip() if price_el else ""
                rating = (await rating_el.inner_text()).strip() if rating_el else ""
                results.append({"name": name, "price": price, "rating": rating})
            except:
                continue
        return {"title": title, "results": results}
    except Exception as e:
        return {"error": str(e)[:200]}

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
            print(f"✅ CDP 연결 성공: {browser.version}")
        except Exception as e:
            print(f"❌ CDP 연결 실패: {e}")
            return

        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await ctx.new_page()

        # 1) 검색 결과 페이지
        print("\n=== 쿠팡 검색: '배수구 트랩' ===")
        result = await fetch_search(page, "배수구+트랩")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:3000])
        with open("/Users/kymac/claude/sourcing/debates/2026-04-11_배수구트랩/coupang_search_배수구트랩.json", "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 2) 두 번째 키워드: 하수구 트랩
        print("\n=== 쿠팡 검색: '하수구 트랩' ===")
        result2 = await fetch_search(page, "하수구+트랩")
        print(json.dumps(result2, ensure_ascii=False, indent=2)[:2000])
        with open("/Users/kymac/claude/sourcing/debates/2026-04-11_배수구트랩/coupang_search_하수구트랩.json", "w") as f:
            json.dump(result2, f, ensure_ascii=False, indent=2)

        await page.close()
        print("\n✅ 완료")

asyncio.run(main())
