// =============================================================
// 소싱콕 리뷰 수집기 — Background Service Worker
// =============================================================

// Listen for messages from web pages (localhost:8090)
chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
    if (message.type === 'PING') {
        sendResponse({ status: 'ok', version: '1.0' });
        return true;
    }

    if (message.type === 'COLLECT_REVIEWS') {
        const products = message.products || [];
        const scanId = message.scanId || null;

        if (!products.length) {
            sendResponse({ status: 'error', message: 'No products provided' });
            return true;
        }

        collectReviews(products, scanId)
            .then(() => console.log('[소싱콕] Review collection finished'))
            .catch(err => console.error('[소싱콕] Collection failed:', err));

        sendResponse({ status: 'started', count: products.length });
        return true;
    }
});

// ----------------------------------------------------------
// Pending review resolution (from content script messages)
// ----------------------------------------------------------
let _pendingReviews = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'REVIEWS_COLLECTED') {
        if (_pendingReviews) {
            _pendingReviews.resolve(message.reviews || []);
            _pendingReviews = null;
        }
        return false;
    }

    if (message.type === 'MARKET_FINDER_COLLECT_REVIEWS') {
        const products = message.products || [];
        const scanId = message.scanId || null;

        if (!products.length) {
            sendResponse({ status: 'error', message: 'No products provided' });
            return false;
        }

        collectReviews(products, scanId)
            .then(() => console.log('[소싱콕] Review collection finished'))
            .catch(err => console.error('[소싱콕] Collection failed:', err));

        sendResponse({ status: 'started', count: products.length });
        return false;
    }

    return false;
});

// ----------------------------------------------------------
// Core collection logic
// ----------------------------------------------------------
async function collectReviews(products, scanId) {
    const allReviews = [];
    const maxProducts = Math.min(products.length, 10);

    // Notify server that collection started
    await notifyProgress(scanId, 'started', 0, maxProducts);

    for (let i = 0; i < maxProducts; i++) {
        const product = products[i];
        const url = product.url;

        if (!url || !url.includes('coupang.com')) {
            console.warn(`[소싱콕] Skipping invalid URL: ${url}`);
            continue;
        }

        try {
            // Open product page in a background tab
            const tab = await chrome.tabs.create({ url, active: false });

            // Wait for page load
            await sleep(3000);

            // Collect reviews via content script
            const reviews = await collectFromTab(tab.id);

            if (reviews.length > 0) {
                allReviews.push(
                    ...reviews.map(r => ({
                        ...r,
                        productName: product.name || '',
                        productUrl: url,
                        rank: product.rank || 0
                    }))
                );
            }

            console.log(`[소싱콕] Product ${i + 1}/${maxProducts}: ${reviews.length} reviews`);

            // Close the tab
            try { await chrome.tabs.remove(tab.id); } catch (_) {}

            // Notify progress
            await notifyProgress(scanId, 'collecting', i + 1, maxProducts);

            // Delay between products to avoid detection
            if (i < maxProducts - 1) {
                await sleep(1500 + Math.random() * 1500);
            }
        } catch (err) {
            console.error(`[소싱콕] Error on product ${i + 1}:`, err);
        }
    }

    // Send all reviews to the 소싱콕 server
    await sendToServer(scanId, allReviews);
}

// ----------------------------------------------------------
// Communicate with content script in a tab
// ----------------------------------------------------------
function collectFromTab(tabId) {
    return new Promise((resolve) => {
        const timeout = setTimeout(() => {
            _pendingReviews = null;
            resolve([]);
        }, 15000);

        _pendingReviews = {
            resolve: (reviews) => {
                clearTimeout(timeout);
                resolve(reviews);
            }
        };

        chrome.tabs.sendMessage(tabId, { type: 'COLLECT' }, (response) => {
            if (chrome.runtime.lastError) {
                // Content script might not be ready — retry once after 2s
                setTimeout(() => {
                    chrome.tabs.sendMessage(tabId, { type: 'COLLECT' }, (retryResp) => {
                        if (chrome.runtime.lastError) {
                            console.warn('[소싱콕] Content script unreachable:', chrome.runtime.lastError.message);
                            clearTimeout(timeout);
                            _pendingReviews = null;
                            resolve([]);
                            return;
                        }
                        if (retryResp && retryResp.reviews) {
                            clearTimeout(timeout);
                            _pendingReviews = null;
                            resolve(retryResp.reviews);
                        }
                    });
                }, 2000);
                return;
            }
            if (response && response.reviews) {
                clearTimeout(timeout);
                _pendingReviews = null;
                resolve(response.reviews);
            }
            // Otherwise wait for REVIEWS_COLLECTED message
        });
    });
}

// ----------------------------------------------------------
// Send collected reviews to localhost:8090
// ----------------------------------------------------------
async function sendToServer(scanId, reviews) {
    try {
        const response = await fetch('http://localhost:8090/api/reviews/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                scan_id: scanId,
                reviews: reviews,
                total: reviews.length
            })
        });
        const result = await response.json();
        console.log('[소싱콕] Reviews sent to server:', result);
    } catch (err) {
        console.error('[소싱콕] Failed to send reviews to server:', err);
    }
}

// ----------------------------------------------------------
// Notify progress to server (optional endpoint)
// ----------------------------------------------------------
async function notifyProgress(scanId, status, current, total) {
    try {
        await fetch('http://localhost:8090/api/reviews/progress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scan_id: scanId, status, current, total })
        });
    } catch (_) {
        // Progress endpoint is optional — ignore failures
    }
}

// ----------------------------------------------------------
// Utility
// ----------------------------------------------------------
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
