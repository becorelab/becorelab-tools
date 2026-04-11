#!/usr/bin/env python3
"""Playwright stealth로 쿠팡 상품 크롤"""
import asyncio
import json
import re
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

PRODUCTS = [
    ("1. 리빙스냅 특대형", "https://www.coupang.com/vp/products/9205946807?itemId=27187387995&vendorItemId=95026131657"),
    ("2. 헤인느 진공+펌프", "https://www.coupang.com/vp/products/8180957872?itemId=23388372570&vendorItemId=90404261155"),
    ("3. 리브맘 옷걸이", "https://www.coupang.com/vp/products/5620199346?itemId=9108286117&vendorItemId=76395171594"),
    ("4. 모노피커 패딩 옷걸이", "https://www.coupang.com/vp/products/9052180941?itemId=26811829725&vendorItemId=93526563312"),
    ("6. 맥맨 옷걸이 진공", "https://www.coupang.com/vp/products/8623275315?itemId=25018330052&vendorItemId=92023147295"),
    ("7. 아케이 여행용", "https://www.coupang.com/vp/products/7473190761?itemId=19504249357&vendorItemId=87196853065"),
    ("8. 니드잇 여행용 4종", "https://www.coupang.com/vp/products/9387839799?itemId=27875825736&vendorItemId=94834967818"),
    ("9. 메리달 옷걸이", "https://www.coupang.com/vp/products/9319113163?itemId=27619176830&vendorItemId=94586062293"),
    ("10. 초대용량 진공+펌프", "https://www.coupang.com/vp/products/8425262289?itemId=24374576945&vendorItemId=91389733337"),
    ("12. 타리홈스 4P+펌프", "https://www.coupang.com/vp/products/8633573474?itemId=25049015881&vendorItemId=92053505154"),
    ("13. 오웨테 4종", "https://www.coupang.com/vp/products/8863594728?itemId=25849086512&vendorItemId=94643484788"),
]

async def fetch_one(page, name, url):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2500)
        title = await page.title()
        if "Access Denied" in title or "Error" in title:
            return {"name": name, "title": title, "error": "blocked"}
        # 상품명
        prod_title = ""
        el = await page.query_selector("h1.prod-buy-header__title, h2.prod-buy-header__title")
        if el:
            prod_title = (await el.inner_text()).strip()
        # 가격
        price_text = ""
        for sel in [".total-price strong", ".prod-price .total-price", ".price-value", "[class*='salePrice']"]:
            el = await page.query_selector(sel)
            if el:
                price_text = (await el.inner_text()).strip()
                if price_text:
                    break
        # 옵션들
        opts = []
        opt_els = await page.query_selector_all("li.prod-option__item, [class*='option-list'] button, [data-option-name]")
        for o in opt_els[:25]:
            t = (await o.inner_text()).strip()
            t = re.sub(r'\s+', ' ', t)
            if t and 2 < len(t) < 150 and t not in opts:
                opts.append(t)
        return {
            "name": name,
            "title": prod_title or title,
            "price": price_text,
            "options": opts[:20],
        }
    except Exception as e:
        return {"name": name, "error": str(e)[:150]}

async def main():
    stealth = Stealth()
    async with stealth.use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
        )
        page = await ctx.new_page()
        results = []
        for name, url in PRODUCTS:
            r = await fetch_one(page, name, url)
            results.append(r)
            print(json.dumps(r, ensure_ascii=False)[:400])
            await asyncio.sleep(1.5)
        with open("/tmp/sourcing_debate/coupang_fetch_result.json", "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        await browser.close()

asyncio.run(main())
