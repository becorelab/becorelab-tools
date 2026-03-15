// =============================================================
// 마켓 파인더 리뷰 수집기 — Content Script (Coupang 상품 페이지)
// =============================================================

(function () {
    'use strict';

    // ----------------------------------------------------------
    // 자동 수집 모드: URL에 ?mf_collect=1&mf_scan=123 있으면 자동 실행
    // ----------------------------------------------------------
    const urlParams = new URLSearchParams(window.location.search);
    const autoCollect = urlParams.get('mf_collect');
    const scanId = urlParams.get('mf_scan');
    const productIndex = urlParams.get('mf_idx');
    const totalProducts = urlParams.get('mf_total');

    if (autoCollect === '1' && scanId) {
        console.log(`[마켓파인더] 자동 리뷰 수집 시작 (scan=${scanId}, idx=${productIndex}/${totalProducts})`);
        setTimeout(async () => {
            // 1) 리뷰 탭 클릭 (쿠팡은 리뷰가 별도 탭에 있음)
            const reviewTabSelectors = [
                'a[href*="btfTab"]',
                'li[data-tab="review"] a',
                'a[href*="#review"]',
                '[class*="tab"][class*="review"]',
                'a[data-tab="review"]',
                'li.tab-item:nth-child(2) a',
                'button[data-tab="review"]'
            ];
            // "상품평" 텍스트로 탭 찾기
            document.querySelectorAll('a, button, li').forEach(el => {
                if (el.textContent.includes('상품평') && !el.classList.contains('_found')) {
                    el.classList.add('_found');
                    el.click();
                    console.log('[마켓파인더] 상품평 탭 클릭 (텍스트 매칭)');
                }
            });
            for (const sel of reviewTabSelectors) {
                const tab = document.querySelector(sel);
                if (tab) {
                    tab.click();
                    console.log('[마켓파인더] 리뷰 탭 클릭:', sel);
                    await sleep(3000);
                    break;
                }
            }

            // 2) 상품평 로드 대기 + 스크롤
            await sleep(4000);
            window.scrollTo(0, document.body.scrollHeight * 0.3);
            await sleep(2000);

            // 3) article 태그에서 직접 수집
            let reviews = [];
            const articles = document.querySelectorAll('article');
            console.log(`[마켓파인더] article 요소: ${articles.length}개`);
            articles.forEach(el => {
                const text = el.innerText.trim();
                if (text.length > 30) {
                    reviews.push({ rating: 5, headline: '', content: text.substring(0, 800), date: '', option: '' });
                }
            });

            // 폴백: 텍스트 기반
            if (reviews.length === 0) {
                const bodyText = document.body.innerText;
                const si = bodyText.indexOf('상품 리뷰');
                if (si > -1) {
                    const chunks = bodyText.substring(si, si + 15000).split(/\d{4}\.\d{2}\.\d{2}/);
                    for (let i = 1; i < chunks.length && i <= 30; i++) {
                        if (chunks[i].trim().length > 30) reviews.push({ rating: 5, headline: '', content: chunks[i].trim().substring(0, 800), date: '', option: '' });
                    }
                    console.log(`[마켓파인더] 텍스트 기반: ${reviews.length}개`);
                }
            }
            console.log(`[마켓파인더] 최종 리뷰: ${reviews.length}개`);

            // 상품명 추출 (페이지 타이틀에서)
            const productName = document.title.replace(' - 쿠팡!', '').replace(' | 쿠팡', '').trim();
            reviews.forEach(r => r.productName = productName);

            // 서버로 전송
            try {
                await fetch('http://localhost:8090/api/reviews/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        scan_id: parseInt(scanId),
                        reviews: reviews,
                        product_name: productName,
                        product_index: parseInt(productIndex || '0'),
                        total_products: parseInt(totalProducts || '1'),
                        partial: true
                    })
                });
            } catch(e) { console.error('[마켓파인더] 전송 실패:', e); }

            // 수집 완료 후 탭 닫기
            setTimeout(() => window.close(), 1000);
        }, 5000); // 페이지 로드 후 5초 대기
    }

    // ----------------------------------------------------------
    // Listen for collection request from background script
    // ----------------------------------------------------------
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === 'COLLECT') {
            handleCollect(sendResponse);
            return true; // keep channel open for async response
        }
    });

    // ----------------------------------------------------------
    // Main handler
    // ----------------------------------------------------------
    async function handleCollect(sendResponse) {
        try {
            // Scroll to the review section so lazy-loaded content appears
            await scrollToReviews();

            // Load additional review pages / "more" button clicks
            await loadMoreReviews();

            // Parse all visible reviews
            const reviews = parseReviews();

            // Send via both paths for reliability
            try {
                chrome.runtime.sendMessage({ type: 'REVIEWS_COLLECTED', reviews });
            } catch (_) {}

            sendResponse({ reviews });
        } catch (err) {
            console.error('[MarketFinder Content] Error:', err);
            sendResponse({ reviews: [] });
        }
    }

    // ----------------------------------------------------------
    // Scroll to the review section
    // ----------------------------------------------------------
    async function scrollToReviews() {
        const selectors = [
            '#btfTab',
            '.sdp-review',
            '[class*="review-section"]',
            '[data-title="상품리뷰"]',
            '.tab-contents__review'
        ];

        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
                el.scrollIntoView({ behavior: 'instant', block: 'start' });
                await sleep(2000);
                return;
            }
        }

        // Fallback: scroll down a lot to trigger lazy loading
        window.scrollTo(0, document.body.scrollHeight * 0.6);
        await sleep(2000);
    }

    // ----------------------------------------------------------
    // Click "more reviews" / pagination to load extra pages
    // ----------------------------------------------------------
    async function loadMoreReviews() {
        // 1) Click "more reviews" button up to 5 times
        for (let i = 0; i < 5; i++) {
            const moreBtn = findVisible([
                '.sdp-review__article__list__more',
                '[class*="more-review"]',
                'button[class*="more"]'
            ]);

            if (moreBtn) {
                moreBtn.click();
                await sleep(1500);
            } else {
                break;
            }
        }

        // 2) Click through pagination (up to 5 pages)
        const pageBtns = document.querySelectorAll(
            '.sdp-review__article__page button, [class*="pagination"] button, .sdp-review__article__page a'
        );

        for (let i = 1; i < Math.min(pageBtns.length, 5); i++) {
            try {
                pageBtns[i].click();
                await sleep(1500);
            } catch (_) {}
        }
    }

    // ----------------------------------------------------------
    // Parse review elements from DOM
    // ----------------------------------------------------------
    function parseReviews() {
        const reviews = [];

        // 방법1: 리뷰 섹션 전체 텍스트를 청크로 수집
        const reviewSection = document.querySelector('.sdp-review__article__list, [class*="review-list"], [class*="ReviewList"]');
        if (reviewSection) {
            // article 요소 찾기
            let reviewEls = reviewSection.querySelectorAll('article');
            if (reviewEls.length === 0) {
                // article이 없으면 직계 자식 div들
                reviewEls = reviewSection.children;
            }

            for (const el of reviewEls) {
                try {
                    const review = parseSingleReview(el);
                    if (review) reviews.push(review);
                } catch (err) {}
            }
        }

        // 방법2: 셀렉터 못 찾으면 텍스트 기반 수집
        if (reviews.length === 0) {
            const allText = document.body.innerText;
            // "상품 리뷰" 섹션 이후 텍스트 추출
            const reviewStart = allText.indexOf('상품 리뷰');
            const reviewEnd = allText.indexOf('상품문의');
            if (reviewStart > -1) {
                const reviewText = allText.substring(reviewStart, reviewEnd > reviewStart ? reviewEnd : reviewStart + 10000);
                // 텍스트를 리뷰 단위로 분할 (날짜 패턴으로)
                const chunks = reviewText.split(/\d{4}\.\d{2}\.\d{2}/);
                for (let i = 1; i < chunks.length && i <= 30; i++) {
                    const text = chunks[i].trim();
                    if (text.length > 20) {
                        reviews.push({
                            rating: 5,
                            headline: '',
                            content: text.substring(0, 500),
                            date: '',
                            option: ''
                        });
                    }
                }
                console.log(`[마켓파인더] 텍스트 기반 수집: ${reviews.length}개`);
            }
        }

        return reviews;
    }

    // ----------------------------------------------------------
    // Parse a single review element
    // ----------------------------------------------------------
    function parseSingleReview(el) {
        // --- Rating ---
        let rating = 5;
        const ratingSelectors = [
            '.sdp-review__article__list__info__product-info__star-orange',
            '.js_reviewArticleRatingValue',
            '[class*="star-orange"]',
            '[class*="StarRating"]',
            '[data-rating]'
        ];

        for (const sel of ratingSelectors) {
            const ratingEl = el.querySelector(sel);
            if (!ratingEl) continue;

            // data-rating attribute
            const dataRating = ratingEl.getAttribute('data-rating');
            if (dataRating) {
                const parsed = parseInt(dataRating, 10);
                if (parsed >= 1 && parsed <= 5) { rating = parsed; break; }
            }

            // width style (star fill percentage)
            const width = ratingEl.style.width;
            if (width && width.includes('%')) {
                rating = Math.round(parseInt(width, 10) / 20);
                break;
            }

            // Text content
            const text = ratingEl.textContent.trim();
            if (text) {
                const parsed = parseInt(text, 10);
                if (parsed >= 1 && parsed <= 5) { rating = parsed; break; }
            }
        }

        // --- Headline ---
        const headline = getTextFrom(el, [
            '.sdp-review__article__list__review__headline',
            '[class*="headline"]',
            'h4', 'h5'
        ]);

        // --- Content ---
        const content = getTextFrom(el, [
            '.sdp-review__article__list__review__content .sdp-review__article__list__review__content__review',
            '.sdp-review__article__list__review__content',
            '.js_reviewArticleContent',
            '[class*="content"] > div',
            '[class*="ReviewContent"]'
        ]);

        // --- Date ---
        const date = getTextFrom(el, [
            '.sdp-review__article__list__info__product-info__reg-date',
            '[class*="reg-date"]',
            '[class*="date"]',
            'time'
        ]);

        // --- Option / variant ---
        const option = getTextFrom(el, [
            '.sdp-review__article__list__info__product-info__option',
            '[class*="option"]',
            '[class*="variant"]'
        ]);

        // --- User name ---
        const userName = getTextFrom(el, [
            '.sdp-review__article__list__info__user__name',
            '[class*="user-name"]',
            '[class*="nickname"]'
        ]);

        // --- Helpful count ---
        let helpfulCount = 0;
        const helpfulEl = el.querySelector('[class*="helpful"] [class*="count"], [class*="like-count"]');
        if (helpfulEl) {
            helpfulCount = parseInt(helpfulEl.textContent.trim(), 10) || 0;
        }

        // Skip empty reviews
        if (!content && !headline) return null;

        return { rating, headline, content, date, option, userName, helpfulCount };
    }

    // ----------------------------------------------------------
    // Helpers
    // ----------------------------------------------------------
    function getTextFrom(parent, selectors) {
        for (const sel of selectors) {
            const el = parent.querySelector(sel);
            if (el) {
                const text = el.innerText.trim();
                if (text) return text;
            }
        }
        return '';
    }

    function findVisible(selectors) {
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) return el;
        }
        return null;
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
})();
