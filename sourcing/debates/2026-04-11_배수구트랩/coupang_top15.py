#!/usr/bin/env python3
"""쿠팡 검색 Top 15 정확한 가격/구성 추출"""
import asyncio, json, re
from playwright.async_api import async_playwright

async def extract_products(page):
    cards = await page.query_selector_all("[class^='ProductUnit_productUnit']")
    results = []
    for c in cards[:20]:
        try:
            data = await c.evaluate("""el => {
                const nameEl = el.querySelector('[class*=productName]');
                const priceEl = el.querySelector('[class*=Price] strong, [class*=priceValue], [class*=PriceValue]');
                const allText = el.innerText || '';
                const link = el.querySelector('a');
                const href = link ? link.getAttribute('href') : '';
                return {
                    name: nameEl ? nameEl.innerText.trim() : '',
                    text: allText.substring(0, 500),
                    href: href,
                };
            }""")
            results.append(data)
        except Exception as e:
            results.append({"error": str(e)[:100]})
    return results

def parse_card(c):
    """카드 텍스트에서 가격 / 매수 / 리뷰 / 평점 파싱"""
    text = c.get('text', '')
    name = c.get('name', '')
    # 모든 가격 추출
    prices = re.findall(r'(\d{1,3}(?:,\d{3})+)\s*원', text)
    # 할인전/후 식별: 할인 표시가 있으면 첫번째가 할인전
    has_discount = '할인' in text or '%' in text
    if has_discount and len(prices) >= 2:
        original_price = int(prices[0].replace(',',''))
        sale_price = int(prices[1].replace(',',''))
    elif prices:
        original_price = None
        sale_price = int(prices[0].replace(',',''))
    else:
        original_price = sale_price = None
    # 매수 추출 (상품명에서)
    cnt_match = re.search(r'(\d+)\s*(?:개|매|개입|세트|팩|p)\b', name, re.IGNORECASE)
    cnt = int(cnt_match.group(1)) if cnt_match else 1
    # 리뷰 수 추출
    review_match = re.search(r'\((\d{1,3}(?:,\d{3})*)\)', text)
    review = int(review_match.group(1).replace(',','')) if review_match else 0
    # 평점
    rating_match = re.search(r'([0-5]\.\d)\s*점', text) or re.search(r'별점\s*([0-5]\.\d)', text)
    rating = float(rating_match.group(1)) if rating_match else None

    unit_price = sale_price // cnt if (sale_price and cnt > 0) else None

    return {
        'name': name,
        'sale_price': sale_price,
        'original_price': original_price,
        'set_count': cnt,
        'unit_price': unit_price,
        'reviews': review,
        'rating': rating,
        'href': c.get('href','')[:120],
    }

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0]
        page = await ctx.new_page()

        all_results = {}
        for kw in ["하수구 트랩", "배수구 트랩"]:
            url = f"https://www.coupang.com/np/search?q={kw.replace(' ','+')}&channel=user"
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(4000)
            try:
                await page.wait_for_selector("[class^='ProductUnit_productUnit']", timeout=10000)
            except:
                pass
            raw = await extract_products(page)
            parsed = [parse_card(c) for c in raw if c.get('name')]
            all_results[kw] = parsed
            print(f"\n=== {kw} Top {len(parsed)} ===")
            print(f"{'순':>3} {'표시가':>9} {'단가':>9} {'매수':>3} {'리뷰':>6} | 상품명")
            print("-"*120)
            for i, p in enumerate(parsed, 1):
                sp = f"{p['sale_price']:,}원" if p['sale_price'] else '-'
                up = f"{p['unit_price']:,}원" if p['unit_price'] else '-'
                print(f"{i:>3} {sp:>9} {up:>9} {p['set_count']:>3} {p['reviews']:>6} | {p['name'][:75]}")

        with open("/Users/kymac/claude/sourcing/debates/2026-04-11_배수구트랩/coupang_real_top15.json", "w") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        await page.close()
        print("\n✅ 저장 완료")

asyncio.run(main())
