// =============================================================
// 마켓 파인더 리뷰 수집기 — Content Script (Coupang 상품 페이지)
// =============================================================

(function () {
    'use strict';

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

        // Try multiple selectors (Coupang changes DOM frequently)
        const reviewSelectors = [
            '.sdp-review__article__list__review',
            '.js_reviewArticle',
            '[class*="ReviewArticle"]',
            '.sdp-review__article__list > article',
            'article.sdp-review__article__list__review'
        ];

        let reviewEls = [];
        for (const sel of reviewSelectors) {
            reviewEls = document.querySelectorAll(sel);
            if (reviewEls.length > 0) break;
        }

        if (reviewEls.length === 0) {
            // Last resort: look for any article inside a review container
            const container = document.querySelector('.sdp-review__article__list, [class*="review-list"]');
            if (container) {
                reviewEls = container.querySelectorAll('article');
            }
        }

        reviewEls.forEach(el => {
            try {
                const review = parseSingleReview(el);
                if (review) reviews.push(review);
            } catch (err) {
                console.warn('[MarketFinder Content] Parse error:', err);
            }
        });

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
