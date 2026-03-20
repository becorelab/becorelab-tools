import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import time, json

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp('http://127.0.0.1:9222')
    context = browser.contexts[0]
    page = context.new_page()

    page.goto('https://www.coupang.com/vp/products/9357303166', wait_until='domcontentloaded', timeout=15000)
    time.sleep(3)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
    time.sleep(2)

    reviews = page.evaluate("""() => {
        const articles = document.querySelectorAll('article');
        const result = [];
        articles.forEach(a => {
            const text = a.textContent.trim().replace(/\\s+/g, ' ');
            if (text.length > 30 && !text.includes('장바구니') && !text.includes('최근본상품')) {
                // 별 개수로 별점 추출
                const filledStars = a.querySelectorAll('[class*="filled"], [class*="active"]');
                let rating = filledStars.length;
                if (rating === 0) {
                    const ratingEl = a.querySelector('[data-rating]');
                    if (ratingEl) rating = parseInt(ratingEl.getAttribute('data-rating'));
                }
                if (rating > 5) rating = 5;

                result.push({
                    rating: rating,
                    content: text.substring(0, 300),
                });
            }
        });
        return result;
    }""")

    print(f'{len(reviews)} reviews extracted')
    for i, r in enumerate(reviews[:5]):
        print(f'  [{i+1}] ★{r["rating"]} {r["content"][:100]}')

    page.close()
except Exception as e:
    print(f'FAIL: {e}')
finally:
    pw.stop()
