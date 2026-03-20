/**
 * bridge.js — localhost:8090 (소싱콕) ↔ 확장프로그램 통신 브릿지
 * 웹 페이지의 postMessage를 받아서 background.js로 전달
 */

// 웹 페이지 → 확장프로그램
window.addEventListener('message', (event) => {
    if (event.source !== window) return;

    if (event.data.type === 'MARKET_FINDER_COLLECT_REVIEWS') {
        console.log('[Bridge] 리뷰 수집 요청 수신:', event.data.products?.length, '개 상품');
        chrome.runtime.sendMessage(event.data, (response) => {
            if (response) {
                window.postMessage({ type: 'MARKET_FINDER_REVIEW_ACK', status: 'started' }, '*');
            }
        });
    }

    if (event.data.type === 'MARKET_FINDER_PING') {
        chrome.runtime.sendMessage({ type: 'PING' }, (response) => {
            window.postMessage({ type: 'MARKET_FINDER_PONG', version: response?.version || '1.0' }, '*');
        });
    }
});

// 확장프로그램 → 웹 페이지 (진행 상황 전달)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'REVIEW_PROGRESS') {
        window.postMessage({ type: 'MARKET_FINDER_REVIEW_PROGRESS', ...message }, '*');
    }
});

// 페이지에 확장 설치 플래그 설정
window.__MARKET_FINDER_EXT_INSTALLED__ = true;
console.log('[소싱콕 리뷰 수집기] Bridge 로드 완료');
