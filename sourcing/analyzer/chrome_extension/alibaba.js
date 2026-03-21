/**
 * alibaba.js — 알리바바 RFQ 폼 자동 채우기
 */
(function() {
    'use strict';

    const fullUrl = window.location.href;
    const rfqIdMatch = fullUrl.match(/mf_rfq_id=(\d+)/);
    const qtyMatch = fullUrl.match(/mf_qty=(\d+)/);
    const rfqId = rfqIdMatch ? rfqIdMatch[1] : null;
    const qty = qtyMatch ? qtyMatch[1] : '1000';

    if (!rfqId) return;

    console.log('[소싱콕] 알리바바 RFQ 자동 채움 시작 (rfq_id=' + rfqId + ')');

    setTimeout(async () => {
        try {
            // 소싱콕에서 영문 RFQ 데이터 가져오기
            const res = await fetch('http://localhost:8090/api/rfq/' + rfqId + '/publish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: '{}'
            });
            const data = await res.json();

            if (!data.success || !data.english_rfq) {
                console.error('[소싱콕] RFQ 데이터 가져오기 실패:', data);
                return;
            }

            const rfq = data.english_rfq;
            const productName = rfq.product_name_en || rfq.subject || '';
            const message = rfq.message || '';

            console.log('[소싱콕] RFQ 데이터 수신:', productName.substring(0, 50));

            await sleep(2000);

            // Product name — "Please enter" placeholder input
            const nameInput = document.querySelector('input[placeholder*="enter"], input[placeholder*="product"], input[placeholder*="Product"]');
            if (nameInput) {
                nameInput.focus();
                nameInput.value = productName.replace('RFQ: ', '');
                nameInput.dispatchEvent(new Event('input', { bubbles: true }));
                nameInput.dispatchEvent(new Event('change', { bubbles: true }));
                console.log('[소싱콕] 제품명 입력 완료');
            } else {
                // 모든 input 시도
                document.querySelectorAll('input[type="text"], input:not([type])').forEach(inp => {
                    if (!inp.value && inp.offsetParent !== null) {
                        inp.focus();
                        inp.value = productName.replace('RFQ: ', '');
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        console.log('[소싱콕] input 폴백 입력');
                    }
                });
            }

            // Detailed requirements — "I am looking for..." textarea
            const detailArea = document.querySelector('textarea[placeholder*="looking"], textarea[placeholder*="detail"], textarea[placeholder*="describe"], textarea');
            if (detailArea) {
                detailArea.focus();
                detailArea.value = message;
                detailArea.dispatchEvent(new Event('input', { bubbles: true }));
                detailArea.dispatchEvent(new Event('change', { bubbles: true }));
                console.log('[소싱콕] 상세 내용 입력 완료');
            }

            // 수량 필드 (있으면)
            const qtyInput = document.querySelector('input[placeholder*="uantity"], input[name*="quantity"]');
            if (qtyInput) {
                qtyInput.focus();
                qtyInput.value = qty;
                qtyInput.dispatchEvent(new Event('input', { bubbles: true }));
            }

            console.log('[소싱콕] 폼 자동 채움 완료!');

            // 상단 알림 배너
            const banner = document.createElement('div');
            banner.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#ff6b2b;color:#fff;padding:12px 20px;font-size:14px;font-weight:700;z-index:99999;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,0.3);';
            banner.textContent = '✅ 소싱콕에서 RFQ가 자동 입력되었습니다. 내용을 확인하고 제출해주세요!';
            document.body.prepend(banner);
            setTimeout(() => banner.remove(), 15000);

        } catch(e) {
            console.error('[소싱콕] 자동 채움 실패:', e);
        }
    }, 5000); // 페이지 로드 후 5초 대기

    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
})();
