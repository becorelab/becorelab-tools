#!/usr/bin/env python3
"""네이버 스마트스토어 고체 탈취제 리뷰 수집 (Playwright + Stealth)"""

import asyncio, json, os, re
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

OUTPUT_DIR = "/Users/macmini_ky/ClaudeAITeam/sourcing/review_output/고체탈취제_네이버"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SEARCH_QUERY = "고체 탈취제"


async def get_products_from_search(page):
    """네이버 쇼핑 검색 결과에서 상품 목록 추출"""
    url = f"https://search.shopping.naver.com/search/all?query={SEARCH_QUERY}&sort=rel&pagingIndex=1&pagingSize=80"
    await page.goto(url, wait_until="networkidle", timeout=60000)
    await asyncio.sleep(5)

    await page.screenshot(path=os.path.join(OUTPUT_DIR, "_search_page.png"))

    products = await page.evaluate("""() => {
        const data = document.querySelector('#__NEXT_DATA__');
        if (!data) return [];
        try {
            const json = JSON.parse(data.textContent);
            const products = json?.props?.pageProps?.initialState?.products?.list || [];
            return products.map(p => {
                const item = p.item || p;
                return {
                    productTitle: item.productTitle || '',
                    mallName: item.mallName || '',
                    merchantNo: item.merchantNo || '',
                    originProductNo: item.originProductNo || '',
                    channel: item.channel || '',
                    reviewCount: item.reviewCount || 0,
                    mallProductUrl: item.mallProductUrl || item.crUrl || '',
                    price: item.price || '',
                    category: item.category1Name || '',
                    imageUrl: item.imageUrl || '',
                };
            });
        } catch(e) { return []; }
    }""")

    if not products:
        print("  __NEXT_DATA__ 파싱 실패, DOM에서 직접 추출 시도...")

        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

        products = await page.evaluate("""() => {
            const items = document.querySelectorAll('[class*="product_item"]');
            const results = [];
            items.forEach(el => {
                const titleEl = el.querySelector('[class*="product_title"]') || el.querySelector('a[title]');
                const title = titleEl ? (titleEl.getAttribute('title') || titleEl.textContent.trim()) : '';
                const linkEl = el.querySelector('a[href*="smartstore"], a[href*="brand.naver"]');
                const url = linkEl ? linkEl.href : '';
                if (title && url) {
                    results.push({
                        productTitle: title,
                        mallProductUrl: url,
                        reviewCount: 0,
                    });
                }
            });
            return results;
        }""")

    smartstore_products = [p for p in products if p.get("merchantNo") or
        ("smartstore" in str(p.get("mallProductUrl","")) or "brand.naver" in str(p.get("mallProductUrl","")))]

    print(f"  전체 {len(products)}개 중 스마트스토어 {len(smartstore_products)}개")
    return smartstore_products


async def collect_reviews_for_product(page, product):
    """개별 상품의 리뷰 전량 수집"""
    merchant_no = product.get("merchantNo", "")
    product_no = product.get("originProductNo", "")
    product_url = product.get("mallProductUrl", "")

    if not merchant_no or not product_no:
        if product_url:
            await page.goto(product_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            info = await page.evaluate("""() => {
                try {
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        const text = s.textContent || '';
                        const mMatch = text.match(/"merchantNo"\\s*:\\s*"?(\\d+)"?/);
                        const pMatch = text.match(/"originProductNo"\\s*:\\s*"?(\\d+)"?/);
                        if (mMatch && pMatch) return { merchantNo: mMatch[1], productNo: pMatch[1] };
                    }
                    const payMatch = document.body.innerHTML.match(/payReferenceKey.*?(\\d{8,})/);
                    const prodMatch = document.body.innerHTML.match(/originProductNo.*?(\\d{8,})/);
                    if (payMatch && prodMatch) return { merchantNo: payMatch[1], productNo: prodMatch[1] };
                } catch(e) {}
                return null;
            }""")
            if info:
                merchant_no = info["merchantNo"]
                product_no = info["productNo"]
            else:
                print(f"    → merchantNo/productNo 추출 실패")
                return []

    if "brand.naver" in product_url:
        api_url = "https://brand.naver.com/n/v1/contents/reviews/query-pages"
    else:
        api_url = "https://smartstore.naver.com/i/v1/contents/reviews/query-pages"

    if not product_url or ("smartstore" not in product_url and "brand" not in product_url):
        api_url = "https://smartstore.naver.com/i/v1/contents/reviews/query-pages"

    # 리뷰 API 호출 전에 해당 스토어 페이지에 먼저 방문해서 CORS origin 확보
    if product_url and not page.url.startswith(product_url[:30]):
        try:
            await page.goto(product_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
        except Exception:
            pass

    # 쿠키 삭제 (SMART DATA의 secretOn() 패턴 — 익명 접근)
    try:
        ctx = page.context
        cookies = await ctx.cookies(["https://smartstore.naver.com", "https://brand.naver.com"])
        if cookies:
            await ctx.clear_cookies()
    except Exception:
        pass

    all_reviews = []

    first_result = await page.evaluate("""async (args) => {
        const [apiUrl, merchantNo, productNo] = args;
        try {
            const resp = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'x-client-version': '20240729102925',
                },
                body: JSON.stringify({
                    checkoutMerchantNo: merchantNo,
                    originProductNo: productNo,
                    page: 1,
                    pageSize: 20,
                    reviewSearchSortType: 'REVIEW_RANKING'
                }),
                credentials: 'omit'
            });
            if (!resp.ok) return { error: resp.status };
            return await resp.json();
        } catch(e) { return { error: e.toString() }; }
    }""", [api_url, merchant_no, product_no])

    if not first_result or first_result.get("error"):
        for alt_url in [
            "https://smartstore.naver.com/i/v1/contents/reviews/query-pages",
            "https://brand.naver.com/n/v1/contents/reviews/query-pages",
        ]:
            if alt_url == api_url:
                continue
            first_result = await page.evaluate("""async (args) => {
                const [apiUrl, merchantNo, productNo] = args;
                try {
                    const resp = await fetch(apiUrl, {
                        method: 'POST',
                        headers: { 'accept': 'application/json', 'content-type': 'application/json' },
                        body: JSON.stringify({
                            checkoutMerchantNo: merchantNo,
                            originProductNo: productNo,
                            page: 1, pageSize: 20,
                            reviewSearchSortType: 'REVIEW_RANKING'
                        }),
                        credentials: 'omit'
                    });
                    if (!resp.ok) return { error: resp.status };
                    return await resp.json();
                } catch(e) { return { error: e.toString() }; }
            }""", [alt_url, merchant_no, product_no])
            if first_result and not first_result.get("error"):
                api_url = alt_url
                break

    if not first_result or first_result.get("error"):
        print(f"    → API 에러: {first_result}")
        return []

    total_pages = first_result.get("totalPages", 0)
    total_count = first_result.get("totalElements", 0)
    contents = first_result.get("contents", [])
    all_reviews.extend(contents)

    print(f"    → 총 {total_count}건, {total_pages}페이지")

    for pg in range(2, total_pages + 1):
        result = await page.evaluate("""async (args) => {
            const [apiUrl, merchantNo, productNo, pg] = args;
            try {
                const resp = await fetch(apiUrl, {
                    method: 'POST',
                    headers: { 'accept': 'application/json', 'content-type': 'application/json' },
                    body: JSON.stringify({
                        checkoutMerchantNo: merchantNo,
                        originProductNo: productNo,
                        page: pg, pageSize: 20,
                        reviewSearchSortType: 'REVIEW_RANKING'
                    }),
                    credentials: 'omit'
                });
                if (!resp.ok) return { error: resp.status };
                return await resp.json();
            } catch(e) { return { error: e.toString() }; }
        }""", [api_url, merchant_no, product_no, pg])

        if result and not result.get("error"):
            contents = result.get("contents", [])
            all_reviews.extend(contents)
        else:
            print(f"    → p{pg} 에러: {result}")
            break

        if pg % 50 == 0:
            print(f"    → {len(all_reviews)}/{total_count}건 수집 중...")

        await asyncio.sleep(0.3 + (0.2 * (pg % 5 == 0)))

    return all_reviews


async def main():
    print(f"=== 네이버 스마트스토어 고체 탈취제 리뷰 수집 ===\n")

    stealth = Stealth()
    async with stealth.use_async(async_playwright()) as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ko-KR",
        )
        page = await context.new_page()

        print("[1/3] 네이버 쇼핑 검색 결과 가져오는 중...")
        products = await get_products_from_search(page)

        if not products:
            page_title = await page.title()
            page_url = page.url
            print(f"  현재 페이지: {page_url}")
            print(f"  페이지 제목: {page_title}")
            print("상품 목록을 가져올 수 없습니다. 스크린샷 저장됨.")
            await browser.close()
            return

        products_sorted = sorted(products, key=lambda x: x.get("reviewCount", 0))
        print(f"\n[2/3] 상품 {len(products_sorted)}개 리뷰 수집 시작...\n")

        total_collected = 0
        results_summary = []

        for i, prod in enumerate(products_sorted):
            title = prod.get("productTitle", "")[:35]
            rc = prod.get("reviewCount", 0)
            pno = prod.get("originProductNo", "unknown")
            out_file = os.path.join(OUTPUT_DIR, f"{pno}.json")

            if os.path.exists(out_file):
                with open(out_file) as f:
                    existing = json.load(f)
                if existing.get("reviews"):
                    cnt = len(existing["reviews"])
                    print(f"[{i+1}/{len(products_sorted)}] {title} — 이미 수집됨 ({cnt}건), 스킵")
                    total_collected += cnt
                    results_summary.append({"title": title, "collected": cnt, "pno": pno})
                    continue

            print(f"[{i+1}/{len(products_sorted)}] {title} (리뷰 {rc}건)")

            try:
                reviews = await collect_reviews_for_product(page, prod)
            except Exception as e:
                print(f"    → 예외: {e}")
                reviews = []

            if reviews:
                save_data = {
                    "product_title": prod.get("productTitle", ""),
                    "product_no": pno,
                    "merchant_no": prod.get("merchantNo", ""),
                    "mall_name": prod.get("mallName", ""),
                    "mall_url": prod.get("mallProductUrl", ""),
                    "review_count_listed": rc,
                    "collected_count": len(reviews),
                    "reviews": reviews,
                }
                with open(out_file, "w") as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=1)

                total_collected += len(reviews)
                print(f"    → {len(reviews)}건 수집 완료 (누적 {total_collected}건)")
            else:
                print(f"    → 수집 실패 또는 리뷰 없음")

            results_summary.append({"title": title, "collected": len(reviews), "pno": pno})
            await asyncio.sleep(1)

        await browser.close()

        print(f"\n[3/3] 완료! 총 {total_collected}건 수집")

        summary = {
            "query": SEARCH_QUERY,
            "total_products": len(products_sorted),
            "total_collected": total_collected,
            "products": results_summary,
        }
        with open(os.path.join(OUTPUT_DIR, "_summary.json"), "w") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
