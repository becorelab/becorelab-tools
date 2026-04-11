#!/usr/bin/env python3
"""쿠팡 상위 압축팩 상품 정보 크롤"""
import asyncio
import json
import re
from playwright.async_api import async_playwright

PRODUCTS = [
    ("1. 리빙스냅 특대형", "https://www.coupang.com/vp/products/9205946807?itemId=27187387995&vendorItemId=95026131657"),
    ("2. 헤인느 진공+펌프", "https://www.coupang.com/vp/products/8180957872?itemId=23388372570&vendorItemId=90404261155"),
    ("3. 리브맘 옷걸이", "https://www.coupang.com/vp/products/5620199346?itemId=9108286117&vendorItemId=76395171594"),
    ("4. 모노피커 패딩 옷걸이", "https://www.coupang.com/vp/products/9052180941?itemId=26811829725&vendorItemId=93526563312"),
    ("5. 펠코스 이불 정리함", "https://www.coupang.com/vp/products/9369362817?itemId=27806736550&vendorItemId=94766629245"),
    ("6. 맥맨 옷걸이 진공", "https://www.coupang.com/vp/products/8623275315?itemId=25018330052&vendorItemId=92023147295"),
    ("7. 아케이 여행용", "https://www.coupang.com/vp/products/7473190761?itemId=19504249357&vendorItemId=87196853065"),
    ("8. 니드잇 여행용 4종", "https://www.coupang.com/vp/products/9387839799?itemId=27875825736&vendorItemId=94834967818"),
    ("9. 메리달 옷걸이", "https://www.coupang.com/vp/products/9319113163?itemId=27619176830&vendorItemId=94586062293"),
    ("10. 초대용량 진공+펌프", "https://www.coupang.com/vp/products/8425262289?itemId=24374576945&vendorItemId=91389733337"),
    ("12. 타리홈스 4P+펌프", "https://www.coupang.com/vp/products/8633573474?itemId=25049015881&vendorItemId=92053505154"),
    ("13. 오웨테 4종", "https://www.coupang.com/vp/products/8863594728?itemId=25849086512&vendorItemId=94643484788"),
]

async def fetch_one(browser, name, url):
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="ko-KR",
        extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
        viewport={"width": 1280, "height": 900},
    )
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(1800)
        title = (await page.title()).replace(" - 쿠팡!", "").strip()
        # 가격
        price_el = await page.query_selector(".total-price, .prod-price .total-price strong, .price-value, [class*='sale-price']")
        price = ""
        if price_el:
            price = (await price_el.inner_text()).strip()
        # 대표 옵션 / 구성 텍스트
        body_html = await page.content()
        # 옵션 버튼들
        opts = []
        opt_els = await page.query_selector_all("ul.prod-option__item button, .prod-option__item, [class*='option'] button")
        for o in opt_els[:20]:
            t = (await o.inner_text()).strip()
            if t and len(t) < 80:
                opts.append(t)
        # 수량/구성 키워드 추출
        kw_hits = re.findall(r'(\d+매|\d+P|\d+개입|\d+종\s*세트|\d+종|\d+\+\d+|특대형|대형|중형|소형|XL|\d+[×x]\d+|\d+cm|\d+L)', title + " " + " ".join(opts))
        return {
            "name": name,
            "url": url,
            "title": title,
            "price_text": price,
            "options_found": list(dict.fromkeys(opts))[:15],
            "composition_hints": list(dict.fromkeys(kw_hits))[:15],
        }
    except Exception as e:
        return {"name": name, "url": url, "error": str(e)[:200]}
    finally:
        await ctx.close()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        # 순차 실행 (봇 감지 회피)
        results = []
        for name, url in PRODUCTS:
            r = await fetch_one(browser, name, url)
            results.append(r)
            print(json.dumps(r, ensure_ascii=False))
            await asyncio.sleep(1.0)
        await browser.close()
        with open("/tmp/sourcing_debate/coupang_fetch_result.json", "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

asyncio.run(main())
