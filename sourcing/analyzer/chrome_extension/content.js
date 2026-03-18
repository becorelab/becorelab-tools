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

    // ----------------------------------------------------------
    // 소싱 분석 버튼 (쿠팡 상품 페이지에 플로팅 버튼 추가)
    // ----------------------------------------------------------
    if (!autoCollect) {
        setTimeout(() => injectSourcingButton(), 2000);
    }

    function injectSourcingButton() {
        if (document.getElementById('mf-sourcing-btn')) return;

        const btn = document.createElement('div');
        btn.id = 'mf-sourcing-btn';
        btn.innerHTML = '🔍 소싱 분석';
        btn.style.cssText = `
            position: fixed; bottom: 80px; right: 20px; z-index: 99999;
            background: #1a1a2e; color: #fff; border: 1px solid #4a4aff;
            padding: 10px 16px; border-radius: 6px; cursor: pointer;
            font-size: 13px; font-weight: 600; font-family: sans-serif;
            box-shadow: 0 4px 12px rgba(74,74,255,0.4);
            transition: all 0.2s;
        `;
        btn.onmouseenter = () => btn.style.background = '#2a2a4e';
        btn.onmouseleave = () => btn.style.background = '#1a1a2e';
        btn.onclick = extractAndSendProductInfo;
        document.body.appendChild(btn);
    }

    async function extractAndSendProductInfo() {
        const btn = document.getElementById('mf-sourcing-btn');
        btn.innerHTML = '⏳ 추출 중...';

        // 상품명 추출
        const nameSelectors = [
            'h1.prod-buy-header__title',
            'h2.prod-buy-header__title',
            '.prod-buy-header__title',
            'h1[class*="title"]',
            'h1'
        ];
        let productName = '';
        for (const sel of nameSelectors) {
            const el = document.querySelector(sel);
            if (el && el.innerText.trim()) {
                productName = el.innerText.trim();
                break;
            }
        }
        if (!productName) {
            productName = document.title.replace(/[-|].*쿠팡.*$/i, '').trim();
        }

        // 메인 이미지 URL 추출 (src + data-src lazy loading 대응)
        function getImgSrc(el) {
            if (!el) return '';
            const src = el.src || el.getAttribute('data-src') || el.getAttribute('data-lazy-src') || '';
            if (src.startsWith('http') && !src.includes('icon') && !src.includes('logo')) return src;
            return '';
        }

        const imgSelectors = [
            '.prod-image__detail img',
            '.prod-image__item--first img',
            '.prod-image__item img',
            'img.prod-image__detail',
            '[class*="prod-image"] img',
            '.main-image img',
            '#prodImage img',
            '.thumbnail-image img',
            'img[class*="prod-image"]'
        ];
        let imageUrl = '';
        for (const sel of imgSelectors) {
            const el = document.querySelector(sel);
            const src = getImgSrc(el);
            if (src) { imageUrl = src; break; }
        }
        // 폴백: 페이지 내 가장 큰 이미지 (src + data-src 모두 체크)
        if (!imageUrl) {
            const allImgs = document.querySelectorAll('img');
            let maxArea = 0;
            allImgs.forEach(img => {
                const src = getImgSrc(img);
                if (!src) return;
                const w = img.naturalWidth || img.width || 0;
                const h = img.naturalHeight || img.height || 0;
                if (w > 200 && h > 200 && w * h > maxArea) {
                    maxArea = w * h;
                    imageUrl = src;
                }
            });
        }

        // 상품 스펙 추출 (사이즈, 소재, 색상 등)
        let specs = [];
        const specSelectors = [
            '.prod-attr-item',
            '[class*="prod-attr"]',
            '.detail-item',
            'table.prod-table tr',
            '[class*="spec"] li',
            '.item-options li'
        ];
        for (const sel of specSelectors) {
            const els = document.querySelectorAll(sel);
            if (els.length > 0) {
                els.forEach(el => {
                    const text = el.innerText.trim().replace(/\s+/g, ' ');
                    if (text && text.length < 100) specs.push(text);
                });
                if (specs.length > 0) break;
            }
        }
        // 폴백: 색상/사이즈 옵션에서 추출
        if (specs.length === 0) {
            const optionText = document.querySelector('.prod-buy-header__info, [class*="prod-option"]');
            if (optionText) specs = [optionText.innerText.trim().substring(0, 200)];
        }
        specs = specs.slice(0, 8); // 최대 8개

        const data = {
            name: productName,
            imageUrl: imageUrl,
            specs: specs,
            pageUrl: window.location.href,
            source: 'coupang'
        };

        try {
            await fetch('http://localhost:8095/api/product-info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            btn.innerHTML = '✅ 전송 완료!';
            btn.style.background = '#0a3a1a';
            btn.style.borderColor = '#3fb950';
            setTimeout(() => {
                btn.innerHTML = '🔍 소싱 분석';
                btn.style.background = '#1a1a2e';
                btn.style.borderColor = '#4a4aff';
            }, 3000);
        } catch (e) {
            btn.innerHTML = '❌ 실패 (서버 확인)';
            btn.style.background = '#3a0a0a';
            btn.style.borderColor = '#f85149';
            setTimeout(() => {
                btn.innerHTML = '🔍 소싱 분석';
                btn.style.background = '#1a1a2e';
                btn.style.borderColor = '#4a4aff';
            }, 3000);
        }
    }

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

            // 3) 모든 페이지를 넘기면서 리뷰 전부 수집
            let reviews = [];
            const seenTexts = new Set(); // 중복 방지

            function collectCurrentPage() {
                let count = 0;
                const articles = document.querySelectorAll('article');
                articles.forEach(el => {
                    const text = el.innerText.trim();
                    const key = text.substring(0, 100);
                    if (text.length > 30 && !seenTexts.has(key)) {
                        seenTexts.add(key);
                        // 별점 추출
                        let rating = 5;
                        const starEl = el.querySelector('[class*="star-orange"], [data-rating], [class*="StarRating"]');
                        if (starEl) {
                            const w = starEl.style.width;
                            if (w && w.includes('%')) rating = Math.round(parseInt(w, 10) / 20);
                            const dr = starEl.getAttribute('data-rating');
                            if (dr) rating = parseInt(dr, 10) || 5;
                        }
                        // 날짜 추출
                        let date = '';
                        const dateMatch = text.match(/\d{4}\.\d{2}\.\d{2}/);
                        if (dateMatch) date = dateMatch[0];
                        reviews.push({ rating, headline: '', content: text.substring(0, 800), date, option: '' });
                        count++;
                    }
                });
                return count;
            }

            // 첫 페이지 수집
            collectCurrentPage();
            console.log(`[마켓파인더] 1페이지: ${reviews.length}개`);

            // 페이지네이션으로 모든 페이지 순회 (최대 50페이지)
            for (let page = 2; page <= 50; page++) {
                // 페이지 버튼 찾기
                const pageBtns = document.querySelectorAll(
                    '.sdp-review__article__page button, [class*="pagination"] button, .sdp-review__article__page a, [class*="page"] button, [class*="page"] a'
                );
                let clicked = false;

                // 페이지 번호 버튼 클릭
                for (const btn of pageBtns) {
                    const txt = btn.textContent.trim();
                    if (txt === String(page)) {
                        btn.click();
                        clicked = true;
                        break;
                    }
                }

                // "다음" 버튼 (10페이지 단위 넘김)
                if (!clicked) {
                    for (const btn of pageBtns) {
                        const txt = btn.textContent.trim();
                        if (txt === '다음' || txt === 'Next' || btn.getAttribute('aria-label') === 'next' || btn.classList.contains('next')) {
                            btn.click();
                            clicked = true;
                            break;
                        }
                    }
                }

                if (!clicked) {
                    console.log(`[마켓파인더] ${page}페이지 버튼 없음 — 수집 종료`);
                    break;
                }

                await sleep(2000);
                // 리뷰 영역으로 스크롤
                const reviewSection = document.querySelector('.sdp-review, [class*="review-section"], #btfTab');
                if (reviewSection) reviewSection.scrollIntoView({ behavior: 'instant', block: 'start' });
                await sleep(1500);

                const before = reviews.length;
                collectCurrentPage();
                const added = reviews.length - before;
                console.log(`[마켓파인더] ${page}페이지: +${added}개 (누적 ${reviews.length}개)`);

                // 새 리뷰가 없으면 종료
                if (added === 0) {
                    console.log(`[마켓파인더] 새 리뷰 없음 — 수집 종료`);
                    break;
                }
            }

            // 폴백: article 못 찾으면 텍스트 기반
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
        // 1) Click "more reviews" button until exhausted
        for (let i = 0; i < 20; i++) {
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

        // 2) Click through all pagination pages (최대 50페이지)
        for (let page = 2; page <= 50; page++) {
            const pageBtns = document.querySelectorAll(
                '.sdp-review__article__page button, [class*="pagination"] button, .sdp-review__article__page a, [class*="page"] button, [class*="page"] a'
            );
            let clicked = false;

            for (const btn of pageBtns) {
                if (btn.textContent.trim() === String(page)) {
                    btn.click();
                    clicked = true;
                    break;
                }
            }

            if (!clicked) {
                for (const btn of pageBtns) {
                    const txt = btn.textContent.trim();
                    if (txt === '다음' || txt === 'Next' || btn.getAttribute('aria-label') === 'next' || btn.classList.contains('next')) {
                        btn.click();
                        clicked = true;
                        break;
                    }
                }
            }

            if (!clicked) break;
            await sleep(2000);
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
