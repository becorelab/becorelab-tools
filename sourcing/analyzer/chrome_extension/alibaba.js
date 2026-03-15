/**
 * alibaba.js — 알리바바 RFQ 폼 자동 채우기
 * URL에 ?mf_rfq_id=N 파라미터가 있으면 마켓 파인더에서 RFQ 데이터를 가져와 폼에 자동 입력
 */
(function() {
    'use strict';

    const fullUrl = window.location.href;
    const rfqIdMatch = fullUrl.match(/mf_rfq_id=(\d+)/);
    const rfqId = rfqIdMatch ? rfqIdMatch[1] : null;
    if (!rfqId) return;

    console.log('[마켓파인더] 알리바바 RFQ 자동 채움 시작 (rfq_id=' + rfqId + ')');

    setTimeout(async () => {
        try {
            // "+Post an RFQ" 버튼 클릭
            const postBtn = document.querySelector('button[class*="post"], a[class*="post"], .btn-post, [class*="Post"]');
            if (postBtn) {
                postBtn.click();
                console.log('[마켓파인더] Post RFQ 버튼 클릭');
                await sleep(3000);
            } else {
                // 텍스트로 찾기
                document.querySelectorAll('button, a, span').forEach(el => {
                    if (el.textContent.includes('Post') && el.textContent.includes('RFQ')) {
                        el.click();
                        console.log('[마켓파인더] Post RFQ 텍스트 매칭 클릭');
                    }
                });
                await sleep(3000);
            }

            // 마켓 파인더에서 영문 RFQ 데이터 가져오기
            const res = await fetch('http://localhost:8090/api/rfq/' + rfqId + '/publish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: '{}'
            });
            const data = await res.json();

            if (!data.success || !data.english_rfq) {
                console.error('[마켓파인더] RFQ 데이터 가져오기 실패');
                return;
            }

            const rfq = data.english_rfq;
            const productName = rfq.product_name_en || rfq.product_name || '';
            const message = rfq.message || '';
            const subject = rfq.subject || '';

            console.log('[마켓파인더] RFQ 데이터:', productName);

            // 알리바바 RFQ 폼 필드 채우기
            await sleep(2000);

            // 제품명 / 제목
            fillInput(['input[name*="subject"]', 'input[name*="productName"]', 'input[name*="title"]',
                       'input[placeholder*="product"]', 'input[placeholder*="What"]', '#subject',
                       'input[class*="product-name"]', 'input[class*="subject"]'],
                      subject || productName);

            // 상세 내용
            fillInput(['textarea[name*="detail"]', 'textarea[name*="description"]', 'textarea[name*="content"]',
                       'textarea[placeholder*="detail"]', 'textarea[placeholder*="describe"]',
                       'textarea', '.detail-textarea'],
                      message);

            // 수량
            fillInput(['input[name*="quantity"]', 'input[name*="qty"]', 'input[name*="amount"]',
                       'input[placeholder*="quantity"]', 'input[placeholder*="Quantity"]'],
                      params.get('mf_qty') || '1000');

            console.log('[마켓파인더] 폼 자동 채움 완료!');

            // 상단에 알림 배너 표시
            const banner = document.createElement('div');
            banner.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#ff6b2b;color:#fff;padding:12px 20px;font-size:14px;font-weight:700;z-index:99999;text-align:center;';
            banner.textContent = '마켓 파인더에서 RFQ가 자동 입력되었습니다. 내용을 확인하고 제출해주세요!';
            document.body.prepend(banner);
            setTimeout(() => banner.remove(), 10000);

        } catch(e) {
            console.error('[마켓파인더] 자동 채움 실패:', e);
        }
    }, 3000);

    function fillInput(selectors, value) {
        if (!value) return;
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) {
                el.focus();
                el.value = value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                console.log('[마켓파인더] 입력:', sel, value.substring(0, 30) + '...');
                return true;
            }
        }
        return false;
    }

    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
})();
