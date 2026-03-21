import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import time

url = 'https://www.coupang.com/vp/products/9194383920?itemId=27137302036&vendorItemId=94105231715'

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp('http://127.0.0.1:9222')
    context = browser.contexts[0]
    page = context.new_page()

    page.goto(url, wait_until='domcontentloaded', timeout=20000)
    time.sleep(3)

    # 1. 기본 상품 정보
    info = page.evaluate("""() => {
        const title = document.querySelector('.prod-buy-header__title, h1, [class*="title"]')?.textContent?.trim() || '';
        const price = document.querySelector('.total-price strong, [class*="sale-price"], [class*="total-price"]')?.textContent?.trim() || '';
        const rating = document.querySelector('.rating-star-num, [class*="rating"]')?.style?.width || '';
        const reviewCount = document.querySelector('.count, [class*="review-count"]')?.textContent?.trim() || '';
        return { title, price, rating, reviewCount };
    }""")
    print("=== 상품 기본 정보 ===")
    print(f"상품명: {info['title']}")
    print(f"가격: {info['price']}")
    print(f"평점: {info['rating']}")
    print(f"리뷰수: {info['reviewCount']}")

    # 2. 상세페이지 영역으로 스크롤
    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
    time.sleep(2)

    # 3. 상세페이지 텍스트 추출
    detail_text = page.evaluate("""() => {
        // 상세페이지 영역 탐색
        const selectors = [
            '.product-detail-content',
            '#productDetail',
            '.product-detail',
            '[class*="detail-item"]',
            '.prod-description',
            '.vendorPage iframe',
        ];

        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.textContent.trim().length > 50) {
                return { selector: sel, text: el.textContent.trim().substring(0, 2000), length: el.textContent.trim().length };
            }
        }

        // iframe 확인
        const iframes = document.querySelectorAll('iframe');
        const iframeInfo = [];
        iframes.forEach(f => {
            iframeInfo.push({ src: f.src?.substring(0, 100) || 'no-src', id: f.id || 'no-id' });
        });

        return { selector: 'none', text: '', iframes: iframeInfo };
    }""")

    print(f"\n=== 상세페이지 텍스트 ===")
    print(f"셀렉터: {detail_text.get('selector')}")
    print(f"길이: {detail_text.get('length', 0)}자")
    if detail_text.get('text'):
        print(f"내용:\n{detail_text['text'][:1000]}")
    if detail_text.get('iframes'):
        print(f"iframe: {detail_text['iframes']}")

    # 4. 상세페이지 이미지 URL 추출
    images = page.evaluate("""() => {
        const imgs = document.querySelectorAll('.product-detail-content img, #productDetail img, .prod-description img');
        return Array.from(imgs).slice(0, 10).map(img => ({
            src: img.src?.substring(0, 150) || '',
            alt: img.alt?.substring(0, 50) || '',
            width: img.naturalWidth,
            height: img.naturalHeight
        }));
    }""")

    print(f"\n=== 상세페이지 이미지 ({len(images)}개) ===")
    for i, img in enumerate(images[:5]):
        print(f"  {i+1}. {img['src'][:100]} ({img['width']}x{img['height']})")

    # 5. 전체 페이지 텍스트 (상세 영역 못 찾으면)
    if not detail_text.get('text'):
        full_text = page.evaluate("""() => {
            return document.body.innerText.substring(0, 3000);
        }""")
        print(f"\n=== 페이지 전체 텍스트 (상세 못 찾음) ===")
        print(full_text[:1500])

    page.close()
except Exception as e:
    print(f'FAIL: {e}')
finally:
    pw.stop()
