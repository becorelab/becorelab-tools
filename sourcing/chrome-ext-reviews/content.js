let collecting = false;

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'startCollect') {
    if (collecting) { sendResponse({ started: false }); return true; }
    startCollection(msg.productId, msg.productTitle);
    sendResponse({ started: true });
    return true;
  }
  if (msg.action === 'stopCollect') {
    collecting = false;
    sendResponse({ stopped: true });
    return true;
  }
  if (msg.action === 'ping') {
    sendResponse({ alive: true, collecting });
    return true;
  }
});

function reviewKey(r) {
  return `${r.member_id || r.user_name}|${r.created_at}|${(r.content || r.headline || '').substring(0, 50)}`;
}

async function saveProgress(data) {
  await chrome.storage.local.set({ reviewProgress: data });
}

async function fetchPage(pid, rating, page, sortBy = 'ORDER_SCORE_ASC') {
  const ratingParam = rating ? `&ratings=${rating}` : '';
  const url = `https://www.coupang.com/vp/product/reviews?productId=${pid}&page=${page}&size=30&sortBy=${sortBy}&ratingSummary=true&viRoleCode=2${ratingParam}`;

  try {
    const resp = await fetch(url, {
      method: 'GET',
      headers: {
        'accept': '*/*',
        'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'sec-ch-ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
      },
      referrer: `https://www.coupang.com/vp/products/${pid}?isAddedCart=`,
      referrerPolicy: 'strict-origin-when-cross-origin',
      mode: 'cors',
      credentials: 'include',
    });

    const html = await resp.text();
    if (html.includes('301 Moved') || html.includes('Access Denied')) {
      return { error: 'blocked' };
    }

    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    const totalEl = doc.querySelector('.js_reviewArticleTotalCountHiddenValue');
    const total = totalEl ? parseInt(totalEl.dataset.totalCount || '0', 10) : 0;

    const countEls = doc.querySelectorAll('.js_reviewArticleHiddenValue');
    const counts = {};
    countEls.forEach((el, i) => {
      counts[5 - i] = parseInt(el.dataset.count || '0', 10);
    });

    const items = doc.querySelectorAll('.js_reviewArticleReviewList');
    const parsed = [];

    items.forEach(item => {
      const ratingEl = item.querySelector('.js_reviewArticleRatingValue');
      const r = ratingEl ? parseInt(ratingEl.dataset.rating || '0', 10) : 0;

      const userEl = item.querySelector('.sdp-review__article__list__info__user');
      let userName = '';
      let memberId = '';
      if (userEl) {
        userName = userEl.textContent.trim();
        if (userEl.children[0]) memberId = userEl.children[0].dataset.memberId || '';
      }

      const dateEl = item.querySelector('.sdp-review__article__list__info__product-info__reg-date');
      const createdAt = dateEl ? dateEl.textContent.trim() : '';

      const sellerEl = item.querySelector('.sdp-review__article__list__info__product-info__seller_name');
      const seller = sellerEl ? sellerEl.textContent.trim() : '';

      const optionEl = item.querySelector('.sdp-review__article__list__info__product-info__name');
      const option = optionEl ? optionEl.textContent.trim() : '';

      const headlineEl = item.querySelector('.sdp-review__article__list__headline');
      const headline = headlineEl ? headlineEl.textContent.trim() : '';

      let content = '';
      const contentEl = item.querySelector('.sdp-review__article__list__review__content');
      if (contentEl) {
        content = contentEl.textContent.trim();
      } else {
        const contentEl2 = item.querySelector('.sdp-review__article__list__review');
        if (contentEl2) content = contentEl2.textContent.trim();
      }

      const attachEl = item.querySelector('.sdp-review__article__list__attachment__list');
      const photoCount = attachEl ? attachEl.querySelectorAll('li').length : 0;

      let helpfulCount = 0;
      const helpEl = item.querySelector('.js_reviewArticleHelpfulBtn, .sdp-review__article__list__help__count');
      if (helpEl) {
        const hm = helpEl.textContent.match(/(\d+)/);
        if (hm) helpfulCount = parseInt(hm[1], 10);
      }

      let answer = '';
      const answerEl = item.querySelector('.js_reviewArticleReplyArea, .sdp-review__article__list__seller-reply');
      if (answerEl) answer = answerEl.textContent.trim();

      parsed.push({
        rating: r, headline, content, created_at: createdAt,
        helpful_count: helpfulCount, user_name: userName, member_id: memberId,
        option, seller, photo_count: photoCount, answer,
      });
    });

    return { total, counts, reviews: parsed };
  } catch (e) {
    return { error: e.toString() };
  }
}

async function startCollection(productId, productTitle) {
  collecting = true;
  const reviews = [];
  const seen = new Set();
  const logs = [];

  function addLog(msg) {
    logs.unshift(msg);
    if (logs.length > 50) logs.pop();
  }

  addLog('수집 시작...');
  await saveProgress({ status: 'collecting', reviews: [], logs, totalCount: 0, productId, productTitle });

  const info = await fetchPage(productId, '', 1);
  if (!info || info.error) {
    addLog(`에러: ${info?.error || 'empty'}`);
    await saveProgress({ status: 'error', reviews: [], logs, totalCount: 0, productId, productTitle });
    collecting = false;
    return;
  }

  const totalCount = info.total || 0;
  const ratingCounts = info.counts || {};

  let sumR = 0, sumC = 0;
  for (const [r, c] of Object.entries(ratingCounts)) {
    sumR += parseInt(r) * c;
    sumC += c;
  }
  const avgRating = sumC > 0 ? (sumR / sumC).toFixed(1) : '0';
  const ratingSummary = { averageRating: parseFloat(avgRating), ratingCounts };

  addLog(`총 ${totalCount}건 (⭐5: ${ratingCounts[5]||0}, 4: ${ratingCounts[4]||0}, 3: ${ratingCounts[3]||0}, 2: ${ratingCounts[2]||0}, 1: ${ratingCounts[1]||0})`);

  if (totalCount === 0) {
    await saveProgress({ status: 'done', reviews: [], logs, totalCount, ratingSummary, productId, productTitle, progress: '리뷰 없음' });
    collecting = false;
    return;
  }

  for (let rating = 1; rating <= 5; rating++) {
    if (!collecting) break;
    const count = ratingCounts[rating] || 0;
    if (count === 0) continue;

    addLog(`⭐${rating}점 수집 중... (${count}건)`);
    let page = 1;

    while (collecting) {
      const res = await fetchPage(productId, rating, page);

      if (!res || res.error) {
        addLog(`  p${page} 에러`);
        break;
      }

      if (!res.reviews || res.reviews.length === 0) break;

      for (const r of res.reviews) {
        const key = reviewKey(r);
        if (!seen.has(key)) {
          seen.add(key);
          reviews.push(r);
        }
      }

      await saveProgress({
        status: 'collecting', reviews, logs, totalCount, ratingSummary,
        productId, productTitle,
        progress: `${reviews.length} / ${totalCount}건 (⭐${rating}점 p${page})`,
      });

      if (res.reviews.length < 30) break;
      page++;

      await new Promise(r => setTimeout(r, 300 + Math.random() * 400));
    }

    addLog(`⭐${rating}점 완료 — 누적 ${reviews.length}건`);
    await new Promise(r => setTimeout(r, 500 + Math.random() * 500));
  }

  const pct = totalCount > 0 ? Math.round(reviews.length / totalCount * 100) : 0;
  addLog(`수집 완료: ${reviews.length} / ${totalCount}건 (${pct}%)`);

  await saveProgress({
    status: 'done', reviews, logs, totalCount, ratingSummary,
    productId, productTitle,
    progress: `✅ ${reviews.length}건 수집 완료!`,
  });

  collecting = false;
}
