const WING = 'https://wing.coupang.com';
const AD = 'https://advertising.coupang.com';
const COUPANG = 'https://www.coupang.com';
const SOURCING_API = 'http://localhost:8090';

const state = {
  productId: '',
  productTitle: '',
  vendorItemId: '',
  itemId: '',
  categoryId: '',
  isCoupangPage: false,
  tabId: null,
};

let progressInterval = null;

// ============================
// Utilities
// ============================
const $ = id => document.getElementById(id);
const show = el => { if (typeof el === 'string') el = $(el); el?.classList.remove('hidden'); };
const hide = el => { if (typeof el === 'string') el = $(el); el?.classList.add('hidden'); };

function fmt(n) {
  if (n == null || isNaN(n)) return '-';
  return Number(n).toLocaleString('ko-KR');
}

function fmtWon(n) {
  if (n == null || isNaN(n)) return '-';
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(1) + '억';
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(0) + '만';
  return fmt(n);
}

function fmtPct(n) {
  if (n == null || isNaN(n)) return '-';
  return Number(n).toFixed(1) + '%';
}

function today() { return new Date().toISOString().slice(0, 10); }
function daysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function setMsg(id, text, type = 'info') {
  const el = $(id);
  if (!el) return;
  el.className = `msg msg-${type}`;
  el.textContent = text;
  show(el);
}

function csvEsc(str) {
  if (!str) return '';
  str = String(str).replace(/"/g, '""');
  if (str.includes(',') || str.includes('\n') || str.includes('"')) return `"${str}"`;
  return str;
}

// ============================
// API Helpers
// ============================
function waitForTab(tabId, timeout = 15000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error('페이지 로딩 타임아웃'));
    }, timeout);
    function listener(id, info) {
      if (id === tabId && info.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        clearTimeout(timer);
        setTimeout(resolve, 500);
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

async function coupangFetch(url) {
  if (state.tabId) {
    try {
      const [result] = await chrome.scripting.executeScript({
        target: { tabId: state.tabId },
        func: async (fetchUrl) => {
          try {
            const r = await fetch(fetchUrl, { credentials: 'include' });
            return { ok: r.ok, status: r.status, text: await r.text() };
          } catch (e) { return { ok: false, error: e.message }; }
        },
        args: [url],
      });
      if (result?.result) return result.result;
    } catch {}
  }
  try {
    const r = await fetch(url, { credentials: 'include' });
    return { ok: r.ok, status: r.status, text: await r.text() };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

async function executeInTab(tabUrl, scriptFn, args = []) {
  let tabs = await chrome.tabs.query({ url: tabUrl });
  if (tabs.length === 0) {
    const domain = tabUrl.replace('/*', '').replace('https://', '');
    throw new Error(`${domain} 탭을 열고 로그인해주세요`);
  }
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tabs[0].id },
    func: scriptFn,
    args,
  });
  return result?.result;
}

async function wingAPI(path, options = {}) {
  const method = options.method || 'GET';
  const body = options.body || null;
  const res = await executeInTab('https://wing.coupang.com/*', async (apiUrl, m, b) => {
    try {
      const opts = { method: m, credentials: 'include', headers: { 'Content-Type': 'application/json' } };
      if (b) opts.body = b;
      const r = await fetch(apiUrl, opts);
      const text = await r.text();
      try { return { ok: r.ok, data: JSON.parse(text) }; } catch { return { ok: r.ok, data: text }; }
    } catch (e) { return { ok: false, error: e.message }; }
  }, [`${WING}${path}`, method, body]);
  if (!res?.ok) throw new Error(res?.error || 'Wing API 오류');
  return res.data;
}

async function adAPI(path, options = {}) {
  const method = options.method || 'GET';
  const body = options.body || null;
  const res = await executeInTab('https://advertising.coupang.com/*', async (apiUrl, m, b) => {
    try {
      const opts = { method: m, credentials: 'include', headers: { 'Content-Type': 'application/json' } };
      if (b) opts.body = b;
      const r = await fetch(apiUrl, opts);
      const text = await r.text();
      try { return { ok: r.ok, data: JSON.parse(text) }; } catch { return { ok: r.ok, data: text }; }
    } catch (e) { return { ok: false, error: e.message }; }
  }, [`${AD}${path}`, method, body]);
  if (!res?.ok) throw new Error(res?.error || '광고 API 오류');
  return res.data;
}

// ============================
// Tab Management
// ============================
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === `panel-${tabId}`));
}

// ============================
// Init
// ============================
async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab?.url || '';
  state.tabId = tab?.id;

  const m = url.match(/coupang\.com\/vp\/products\/(\d+)/);
  if (m) {
    state.productId = m[1];
    state.isCoupangPage = true;

    const vm = url.match(/vendorItemId=(\d+)/);
    if (vm) state.vendorItemId = vm[1];
    const im = url.match(/itemId=(\d+)/);
    if (im) state.itemId = im[1];

    try {
      const [result] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          let title = '', vid = '', iid = '', price = '', delivery = '', brand = '';
          let optionData = null;

          const titleSels = ['h2.prod-buy-header__title', 'h1.prod-buy-header__title', '.prod-buy-header__title', '.product-buy-header h1 span', 'h1'];
          for (const s of titleSels) {
            const el = document.querySelector(s);
            if (el?.textContent.trim().length > 3) { title = el.textContent.trim(); break; }
          }

          try {
            const scripts = document.querySelectorAll('script');
            for (const s of scripts) {
              const t = s.textContent || '';
              const sdpMatch = t.match(/exports\.sdp\s*=\s*(\{[\s\S]+?\});?\s*(?:exports\.|<\/script)/);
              if (sdpMatch) {
                const sdp = JSON.parse(sdpMatch[1]);
                if (sdp.title) title = sdp.title;
                if (sdp.vendorItemId) vid = String(sdp.vendorItemId);
                if (sdp.itemId) iid = String(sdp.itemId);
                if (sdp.quantityBase?.[0]?.price?.salePrice) price = sdp.quantityBase[0].price.salePrice;
                if (sdp.options) optionData = sdp.options;
                break;
              }
              const pidMatch = t.match(/productId['":\s]+(\d{5,})/);
              if (pidMatch && !vid) {
                const vidMatch2 = t.match(/vendorItemId['":\s]+(\d{5,})/);
                const iidMatch2 = t.match(/itemId['":\s]+(\d{5,})/);
                if (vidMatch2) vid = vidMatch2[1];
                if (iidMatch2) iid = iidMatch2[1];
              }
            }
          } catch {}

          const priceEl = document.querySelector('.total-price strong, .prod-price .total-price, .final-price-amount');
          if (!price && priceEl) price = priceEl.textContent.replace(/[^\d]/g, '');

          const delivEl = document.querySelector('[class*="rocket"], [alt*="로켓"], .delivery-badge-text');
          if (delivEl) delivery = delivEl.textContent?.trim() || delivEl.alt || '로켓배송';
          if (!delivery) {
            const allText = document.body.innerText;
            if (allText.includes('로켓배송')) delivery = '로켓배송';
            else if (allText.includes('로켓직구')) delivery = '로켓직구';
            else delivery = '일반배송';
          }

          const brandSels = ['.prod-brand-name a', '.prod-brand-name', '[class*="brandName"]'];
          for (const s of brandSels) {
            const el = document.querySelector(s);
            if (el?.textContent.trim()) { brand = el.textContent.trim(); break; }
          }

          return { title, vid, iid, price, delivery, brand, optionData };
        },
      });
      const info = result?.result || {};
      state.productTitle = info.title || `상품 ${state.productId}`;
      if (info.vid) state.vendorItemId = info.vid;
      if (info.iid) state.itemId = info.iid;

      $('header-title').textContent = state.productTitle;
      $('header-pid').textContent = `ID: ${state.productId}`;
      show('header-product');

      show('review-content');
      hide('review-empty');
      show('compete-content');
      hide('compete-empty');

      $('compete-price').textContent = info.price ? fmt(info.price) + '원' : '-';
      $('compete-delivery').textContent = info.delivery || '-';
      $('compete-brand').textContent = info.brand || '-';

      if (info.optionData) renderOptions(info.optionData);

      switchTab('review');
    } catch {
      state.productTitle = `상품 ${state.productId}`;
      $('header-title').textContent = state.productTitle;
      $('header-pid').textContent = `ID: ${state.productId}`;
      show('header-product');
    }

    await checkReviewProgress();
  } else {
    switchTab('keyword');
  }

  $('sales-start').value = daysAgo(7);
  $('sales-end').value = daysAgo(1);
  $('ads-start').value = daysAgo(7);
  $('ads-end').value = daysAgo(1);

  setupListeners();
}

function setupListeners() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  $('kw-search-btn').addEventListener('click', () => searchKeyword());
  $('kw-input').addEventListener('keydown', e => { if (e.key === 'Enter') searchKeyword(); });

  $('compete-load-btn').addEventListener('click', loadCompetitors);

  $('btn-review-start').addEventListener('click', collectReviews);
  $('btn-review-json').addEventListener('click', downloadJSON);
  $('btn-review-csv').addEventListener('click', downloadCSV);
  $('btn-review-send').addEventListener('click', sendToApp);

  $('sales-fetch-btn').addEventListener('click', fetchSales);
  $('ads-fetch-btn').addEventListener('click', fetchAds);
  $('margin-calc-btn').addEventListener('click', calculateMargin);
  $('cat-search-btn').addEventListener('click', fetchCategory);
  $('cat-input').addEventListener('keydown', e => { if (e.key === 'Enter') fetchCategory(); });
}

// ============================
// 1. KEYWORD ANALYSIS
// ============================
async function searchKeyword() {
  const kw = $('kw-input').value.trim();
  if (!kw) return;

  show('kw-loading');
  hide('kw-result');
  hide('kw-related');
  hide('kw-ranking');

  try {
    const [searchResult, autoResult] = await Promise.allSettled([
      searchCoupang(kw),
      getAutocomplete(kw),
    ]);

    if (searchResult.status === 'fulfilled' && searchResult.value) {
      const s = searchResult.value;
      $('kw-total-count').textContent = fmt(s.totalCount);
      $('kw-rocket-pct').textContent = fmtPct(s.rocketPct);
      $('kw-avg-price').textContent = fmtWon(s.avgPrice);
      $('kw-cpc-price').textContent = '-';
      show('kw-result');

      if (s.products?.length) {
        const tbody = $('kw-ranking-body');
        tbody.innerHTML = '';
        s.products.slice(0, 20).forEach((p, i) => {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${i + 1}</td><td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.name}</td><td>${fmtWon(p.price)}</td><td>${fmt(p.reviewCount)}</td><td style="font-size:10px">${p.delivery}</td>`;
          tbody.appendChild(tr);
        });
        show('kw-ranking');
      }
    }

    if (autoResult.status === 'fulfilled' && autoResult.value?.length) {
      const list = $('kw-related-list');
      list.innerHTML = '';
      autoResult.value.forEach(word => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.textContent = word;
        tag.addEventListener('click', () => { $('kw-input').value = word; searchKeyword(); });
        list.appendChild(tag);
      });
      show('kw-related');
    }

    try { await getCPC(kw); } catch {}
  } catch (e) {
    setMsg('kw-result', `검색 실패: ${e.message}`, 'error');
    show('kw-result');
  } finally {
    hide('kw-loading');
  }
}

async function searchCoupang(keyword) {
  const searchUrl = `${COUPANG}/np/search?q=${encodeURIComponent(keyword)}&channel=user&sorter=scoreDesc&listSize=36&page=1&rating=0`;
  const tab = await chrome.tabs.create({ url: searchUrl, active: false });

  try {
    await waitForTab(tab.id);

    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        let totalCount = 0;

        const countSels = ['#product-count strong', '.search-result-count', '#productCount', '[class*="resultCount"]'];
        for (const sel of countSels) {
          const el = document.querySelector(sel);
          if (el) {
            const m = el.textContent.match(/([\d,]+)/);
            if (m) { totalCount = parseInt(m[1].replace(/,/g, '')); break; }
          }
        }
        if (!totalCount) {
          const body = document.body.innerText || '';
          const m = body.match(/(\d[\d,]+)\s*개의?\s*(?:검색|상품)/);
          if (m) totalCount = parseInt(m[1].replace(/,/g, ''));
        }

        const itemSels = ['li.search-product', 'ul.search-content > li', '[class*="SearchResult"]', '.baby-product-link'];
        let items = [];
        for (const sel of itemSels) {
          items = document.querySelectorAll(sel);
          if (items.length > 0) break;
        }
        if (items.length === 0) {
          items = document.querySelectorAll('a[href*="/vp/products/"]');
          const parents = new Set();
          items.forEach(a => { if (a.closest('li')) parents.add(a.closest('li')); });
          if (parents.size > 0) items = parents;
        }

        const products = [];
        let rocketCount = 0, priceSum = 0, priceN = 0;

        items.forEach(item => {
          const el = item instanceof HTMLElement ? item : item;
          const nameSels = ['.name', '[class*="productName"]', '.descriptions-inner__name', 'a[data-product-name]'];
          let name = '';
          for (const s of nameSels) {
            const n = el.querySelector(s);
            if (n?.textContent.trim()) { name = n.textContent.trim(); break; }
          }
          if (!name) {
            const a = el.querySelector('a[href*="/vp/products/"]');
            if (a) name = a.textContent.trim().substring(0, 80);
          }

          let price = 0;
          const pSels = ['.price-value', 'strong.base-price', '[class*="priceValue"]', '.price em'];
          for (const s of pSels) {
            const p = el.querySelector(s);
            if (p) { const m = p.textContent.match(/([\d,]+)/); if (m) { price = parseInt(m[1].replace(/,/g, '')); break; } }
          }

          let reviewCount = 0;
          const rSels = ['.rating-total-count', '[class*="ratingCount"]', '.count'];
          for (const s of rSels) {
            const r = el.querySelector(s);
            if (r) { const m = r.textContent.match(/(\d[\d,]*)/); if (m) { reviewCount = parseInt(m[1].replace(/,/g, '')); break; } }
          }

          const isRocket = !!(el.querySelector('[class*="rocket"], img[alt*="로켓"], .badge--rocket, [class*="Rocket"]') ||
            el.innerHTML?.includes('로켓'));
          if (isRocket) rocketCount++;

          const isAd = !!(el.querySelector('[class*="adMark"], .ad-badge, [class*="AdBadge"]') ||
            el.innerHTML?.includes('광고'));

          if (price > 0) { priceSum += price; priceN++; }
          if (name) {
            products.push({
              name: name.substring(0, 80),
              price, reviewCount,
              delivery: (isRocket ? '로켓' : '일반') + (isAd ? ' (광고)' : ''),
            });
          }
        });

        return {
          totalCount,
          rocketPct: items.length > 0 ? (rocketCount / items.length * 100) : 0,
          avgPrice: priceN > 0 ? Math.round(priceSum / priceN) : 0,
          products,
          debug: { itemsFound: items.length, url: location.href },
        };
      },
    });

    return result?.result;
  } finally {
    try { chrome.tabs.remove(tab.id); } catch {}
  }
}

async function getAutocomplete(keyword) {
  try {
    const url = `${COUPANG}/np/search/autoComplete?keyword=${encodeURIComponent(keyword)}`;
    const res = await coupangFetch(url);
    if (!res?.ok) return [];
    const text = (res.text || '').trim();
    if (!text) return [];

    let parsed;
    const jsonpMatch = text.match(/\((\[[\s\S]*\])\)/) || text.match(/\((\{[\s\S]*\})\)/);
    if (jsonpMatch) parsed = JSON.parse(jsonpMatch[1]);
    else parsed = JSON.parse(text);

    if (Array.isArray(parsed)) return parsed.map(i => typeof i === 'string' ? i : i.keyword || i.text || '').filter(Boolean);
    if (parsed?.keywords) return parsed.keywords;
    if (parsed?.suggestions) return parsed.suggestions.map(s => s.keyword || s.text || String(s)).filter(Boolean);
    return [];
  } catch { return []; }
}

async function getCPC(keyword) {
  try {
    const data = await adAPI('/marketing/cmg-api/recommendation/keyword', {
      method: 'POST',
      body: JSON.stringify({ keyword }),
    });
    if (data?.suggestedBid) {
      $('kw-cpc-price').textContent = fmt(data.suggestedBid) + '원';
    }
  } catch {}
}

// ============================
// 2. COMPETITOR ANALYSIS
// ============================
async function loadCompetitors() {
  if (!state.productId) return;
  const btn = $('compete-load-btn');
  btn.disabled = true;
  btn.textContent = '조회 중...';

  try {
    let url = `${COUPANG}/next-api/products/other-seller-info?productId=${state.productId}`;
    if (state.vendorItemId) url += `&selectedId=${state.vendorItemId}`;
    if (state.itemId) url += `&itemId=${state.itemId}`;

    const res = await coupangFetch(url);
    if (!res.ok) throw new Error('조회 실패');

    let data;
    try { data = JSON.parse(res.text); } catch { throw new Error('응답 파싱 실패'); }

    const sellers = data?.otherSellers || data?.data?.otherSellers || data || [];
    if (!Array.isArray(sellers) || sellers.length === 0) {
      setMsg('compete-sellers-msg', '다른 판매자 없음 (단독 판매)', 'info');
      show('compete-sellers-msg');
      hide('compete-sellers-wrap');
    } else {
      hide('compete-sellers-msg');
      const tbody = $('compete-sellers-body');
      tbody.innerHTML = '';
      sellers.forEach(s => {
        const tr = document.createElement('tr');
        const name = s.sellerName || s.vendorName || '-';
        const price = s.price || s.salePrice || '-';
        const deliv = s.rocketBadge ? '로켓' : (s.deliveryType || '일반');
        tr.innerHTML = `<td>${name}</td><td>${typeof price === 'number' ? fmt(price) + '원' : price}</td><td>${deliv}</td>`;
        tbody.appendChild(tr);
      });
      show('compete-sellers-wrap');
    }
  } catch (e) {
    setMsg('compete-sellers-msg', e.message, 'error');
    show('compete-sellers-msg');
  } finally {
    btn.disabled = false;
    btn.textContent = '판매자 비교 조회';
  }
}

function renderOptions(optionData) {
  if (!optionData?.attributeVendorItemMap) return;
  const tbody = $('compete-options-body');
  tbody.innerHTML = '';

  const attrMap = optionData.attributeVendorItemMap;
  for (const [key, val] of Object.entries(attrMap)) {
    const tr = document.createElement('tr');
    const price = val.quantityBase?.[0]?.price?.salePrice;
    const soldOut = val.soldOut ? '품절' : '판매중';
    const soldClass = val.soldOut ? 'color:var(--error)' : 'color:var(--success)';
    tr.innerHTML = `<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${key}</td><td>${price ? fmt(price) + '원' : '-'}</td><td style="${soldClass}">${soldOut}</td>`;
    tbody.appendChild(tr);
  }

  if (tbody.children.length > 0) show('compete-options-wrap');
}

// ============================
// 3. REVIEW COLLECTION
// ============================
async function checkReviewProgress() {
  const data = await chrome.storage.local.get('reviewProgress');
  const p = data.reviewProgress;
  if (!p || p.productId !== state.productId) return;

  if (p.status === 'collecting') {
    showReviewCollecting();
    startReviewPolling();
  } else if (p.status === 'done') {
    showReviewDone(p);
  }
}

function showReviewCollecting() {
  const btn = $('btn-review-start');
  btn.disabled = true;
  btn.textContent = '수집 중... (탭 전환 OK)';
  show('review-progress');
}

function showReviewDone(p) {
  const btn = $('btn-review-start');
  const count = p.reviews?.length || 0;
  btn.disabled = false;
  btn.textContent = `다시 수집 (${fmt(count)}건)`;
  show('review-progress');
  $('review-progress-text').textContent = p.progress || `${fmt(count)}건 완료`;
  $('review-fill').style.width = '100%';

  if (p.totalCount) { $('review-total').textContent = fmt(p.totalCount); }
  if (p.ratingSummary?.averageRating) { $('review-avg').textContent = p.ratingSummary.averageRating.toFixed(1); }

  if (count > 0) {
    show('btn-review-json');
    show('btn-review-csv');
    show('btn-review-send');
  }
  if (p.logs) { $('review-log').textContent = p.logs.slice(0, 10).join('\n'); }
}

function startReviewPolling() {
  if (progressInterval) clearInterval(progressInterval);
  progressInterval = setInterval(async () => {
    const data = await chrome.storage.local.get('reviewProgress');
    const p = data.reviewProgress;
    if (!p) return;

    if (p.totalCount) $('review-total').textContent = fmt(p.totalCount);
    if (p.ratingSummary?.averageRating) $('review-avg').textContent = p.ratingSummary.averageRating.toFixed(1);

    const count = p.reviews?.length || 0;
    const total = p.totalCount || 1;
    const pct = Math.min(100, Math.round(count / total * 100));
    $('review-progress-text').textContent = p.progress || `${count} / ${total}건`;
    $('review-fill').style.width = `${pct}%`;

    if (p.logs) $('review-log').textContent = p.logs.slice(0, 10).join('\n');

    if (p.status === 'done' || p.status === 'error') {
      clearInterval(progressInterval);
      progressInterval = null;
      showReviewDone(p);
    }
  }, 1000);
}

async function collectReviews() {
  if (!state.tabId) return;
  showReviewCollecting();
  try {
    await chrome.tabs.sendMessage(state.tabId, {
      action: 'startCollect',
      productId: state.productId,
      productTitle: state.productTitle,
    });
  } catch (e) {
    $('review-log').textContent = `content script 연결 실패: ${e.message}\n페이지 새로고침 후 다시 시도해주세요`;
    $('btn-review-start').disabled = false;
    $('btn-review-start').textContent = '전체 리뷰 수집';
    return;
  }
  startReviewPolling();
}

async function getReviewData() {
  const data = await chrome.storage.local.get('reviewProgress');
  const p = data.reviewProgress;
  if (!p?.reviews?.length) return null;
  return {
    product_id: p.productId || state.productId,
    product_title: p.productTitle || state.productTitle,
    product_url: `${COUPANG}/vp/products/${p.productId || state.productId}`,
    total_count: p.totalCount || 0,
    collected_count: p.reviews.length,
    downloaded_at: new Date().toISOString(),
    rating_summary: p.ratingSummary || {},
    reviews: p.reviews,
  };
}

async function downloadJSON() {
  const data = await getReviewData();
  if (!data) return;
  const pid = data.product_id;
  const title = data.product_title.substring(0, 30).replace(/[^\w가-힣]/g, '_');
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  chrome.downloads.download({ url, filename: `reviews/${pid}_${title}/reviews_${today()}.json` });
}

async function downloadCSV() {
  const data = await getReviewData();
  if (!data) return;
  const pid = data.product_id;
  const title = data.product_title.substring(0, 30).replace(/[^\w가-힣]/g, '_');
  const BOM = '﻿';
  const headers = ['번호', '별점', '제목', '내용', '작성일', '작성자', '옵션', '도움됨', '사진수', '판매자답변'];
  const rows = data.reviews.map((r, i) => [
    i + 1, r.rating, csvEsc(r.headline), csvEsc(r.content),
    (r.created_at || '').slice(0, 10), csvEsc(r.user_name), csvEsc(r.option),
    r.helpful_count, r.photo_count, csvEsc(r.answer),
  ].join(','));
  const csv = BOM + headers.join(',') + '\n' + rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  chrome.downloads.download({ url, filename: `reviews/${pid}_${title}/reviews_${today()}.csv` });
}

async function sendToApp() {
  const btn = $('btn-review-send');
  btn.disabled = true;
  btn.textContent = '전송 중...';
  try {
    const data = await getReviewData();
    const resp = await fetch(`${SOURCING_API}/api/reviews/import-bulk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const result = await resp.json();
    btn.textContent = result.success ? '저장 완료!' : '실패';
  } catch (e) {
    btn.textContent = '연결 실패';
  }
  btn.disabled = false;
}

// ============================
// 4. SALES ANALYSIS
// ============================
async function fetchSales() {
  const startDate = $('sales-start').value;
  const endDate = $('sales-end').value;
  if (!startDate || !endDate) return;

  const btn = $('sales-fetch-btn');
  btn.disabled = true;
  btn.textContent = '조회 중...';
  show('sales-loading');
  hide('sales-result');
  hide('sales-info');

  try {
    const data = await wingAPI('/tenants/rfm-ss/api/business-insight/vi-detail-search', {
      method: 'POST',
      body: JSON.stringify({
        startDate, endDate,
        registrationTypes: ['RFM'],
        pageNumber: 1,
        pageSize: 100,
        sortBy: 'GMV',
      }),
    });

    const items = data?.data?.content || data?.content || [];
    if (items.length === 0) {
      setMsg('sales-info', '판매 데이터가 없습니다', 'info');
      hide('sales-loading');
      btn.disabled = false;
      return;
    }

    let totalGmv = 0, totalUnits = 0, totalPv = 0;
    const tbody = $('sales-table-body');
    tbody.innerHTML = '';

    if (state.vendorItemId) {
      const detail = await wingAPI('/tenants/rfm-ss/api/business-insight/vendor-item-summary', {
        method: 'POST',
        body: JSON.stringify({ startDate, endDate, vendorItemId: parseInt(state.vendorItemId) }),
      });

      const salesByDate = detail?.data?.saleSummaryByDate || detail?.saleSummaryByDate || [];
      const trafficByDate = detail?.data?.trafficSummaryByDate || detail?.trafficSummaryByDate || [];
      const convByDate = detail?.data?.conversionSummaryByDate || detail?.conversionSummaryByDate || [];

      salesByDate.forEach((s, i) => {
        const gmv = s.gmv || s.salePrice || 0;
        const units = s.unitsSold || s.saleCount || 0;
        const traffic = trafficByDate[i] || {};
        const conv = convByDate[i] || {};
        const pv = traffic.productView || traffic.pv || 0;
        const cvr = conv.conversionRate || conv.cvr || 0;

        totalGmv += gmv;
        totalUnits += units;
        totalPv += pv;

        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${s.date || '-'}</td><td>${fmtWon(gmv)}</td><td>${fmt(units)}</td><td>${fmt(pv)}</td><td>${fmtPct(cvr)}</td>`;
        tbody.appendChild(tr);
      });
    } else {
      items.slice(0, 20).forEach(item => {
        const gmv = item.gmv || 0;
        const units = item.unitsSold || 0;
        const pv = item.productView || 0;
        totalGmv += gmv;
        totalUnits += units;
        totalPv += pv;

        const tr = document.createElement('tr');
        tr.innerHTML = `<td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${item.vendorItemName || '-'}</td><td>${fmtWon(gmv)}</td><td>${fmt(units)}</td><td>${fmt(pv)}</td><td>${fmtPct(item.cvr || 0)}</td>`;
        tbody.appendChild(tr);
      });
    }

    $('sales-gmv').textContent = fmtWon(totalGmv);
    $('sales-units').textContent = fmt(totalUnits);
    $('sales-pv').textContent = fmt(totalPv);
    $('sales-cvr').textContent = totalPv > 0 ? fmtPct(totalUnits / totalPv * 100) : '-';
    show('sales-result');

  } catch (e) {
    const msg = e.message.includes('탭을 열고')
      ? '⚠️ wing.coupang.com 탭을 열고 로그인한 상태에서 다시 시도해주세요'
      : `조회 실패: ${e.message}`;
    setMsg('sales-info', msg, 'error');
  } finally {
    hide('sales-loading');
    btn.disabled = false;
    btn.textContent = '조회';
  }
}

// ============================
// 5. AD ANALYSIS
// ============================
async function fetchAds() {
  const startDate = $('ads-start').value;
  const endDate = $('ads-end').value;
  if (!startDate || !endDate) return;

  const btn = $('ads-fetch-btn');
  btn.disabled = true;
  show('ads-loading');
  hide('ads-result');

  try {
    const campaignsData = await adAPI('/marketing/tetris-api/campaigns', {
      method: 'POST',
      body: JSON.stringify({ page: 0, size: 50 }),
    });

    const campaigns = campaignsData?.content || campaignsData?.data?.content || campaignsData || [];
    if (!Array.isArray(campaigns) || campaigns.length === 0) {
      setMsg('ads-info', '광고 캠페인이 없습니다', 'info');
      hide('ads-loading');
      btn.disabled = false;
      return;
    }

    const campaignIds = campaigns.map(c => c.campaignId || c.id).filter(Boolean);
    const reportData = await adAPI('/marketing-reporting/v2/graphql', {
      method: 'POST',
      body: JSON.stringify({
        query: `query { generateCustomReport(input: { startDate: "${startDate}", endDate: "${endDate}", campaignIds: [${campaignIds.join(',')}], metrics: ["impressions","clicks","cost","ctr","roas14d","orders14d","revenue14d"], groupBy: ["CAMPAIGN"], page: 0, size: 500 }) { content { campaignName impressions clicks cost ctr roas14d orders14d revenue14d } totalElements } }`,
      }),
    });

    const rows = reportData?.data?.generateCustomReport?.content || [];
    let totalImpr = 0, totalClicks = 0, totalCost = 0, totalRev = 0;

    const tbody = $('ads-table-body');
    tbody.innerHTML = '';

    rows.forEach(r => {
      totalImpr += r.impressions || 0;
      totalClicks += r.clicks || 0;
      totalCost += r.cost || 0;
      totalRev += r.revenue14d || 0;

      const tr = document.createElement('tr');
      tr.innerHTML = `<td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.campaignName || '-'}</td><td>${fmt(r.impressions)}</td><td>${fmt(r.clicks)}</td><td>${fmtWon(r.cost)}</td><td>${r.roas14d ? (r.roas14d * 100).toFixed(0) + '%' : '-'}</td>`;
      tbody.appendChild(tr);
    });

    if (rows.length === 0) {
      campaigns.slice(0, 20).forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.campaignName || c.name || '-'}</td><td>-</td><td>-</td><td>-</td><td>-</td>`;
        tbody.appendChild(tr);
      });
    }

    $('ads-impressions').textContent = fmt(totalImpr);
    $('ads-clicks').textContent = fmt(totalClicks);
    $('ads-spend').textContent = fmtWon(totalCost);
    $('ads-roas').textContent = totalCost > 0 ? ((totalRev / totalCost) * 100).toFixed(0) + '%' : '-';
    show('ads-result');

  } catch (e) {
    const msg = e.message.includes('탭을 열고')
      ? '⚠️ advertising.coupang.com 탭을 열고 로그인한 상태에서 다시 시도해주세요'
      : `조회 실패: ${e.message}`;
    setMsg('ads-info', msg, 'error');
  } finally {
    hide('ads-loading');
    btn.disabled = false;
  }
}

// ============================
// 6. MARGIN CALCULATOR
// ============================
function calculateMargin() {
  const price = parseFloat($('margin-price').value) || 0;
  const cost = parseFloat($('margin-cost').value) || 0;
  const commRate = parseFloat($('margin-commission-rate').value) || 10.8;
  const fulfillment = parseFloat($('margin-fulfillment').value) || 0;
  const warehouse = parseFloat($('margin-warehouse').value) || 0;
  const dailyQty = parseFloat($('margin-daily-qty').value) || 1;

  if (price <= 0) return;

  const commission = Math.round(price * commRate / 100);
  const netProfit = price - cost - commission - fulfillment;
  const marginRate = (netProfit / price) * 100;
  const roi = cost > 0 ? (netProfit / cost) * 100 : 0;
  const monthlyProfit = netProfit * dailyQty * 30 - warehouse;
  const breakeven = netProfit > 0 ? Math.ceil((cost * dailyQty * 30 + warehouse) / netProfit) : 0;

  $('margin-fee').textContent = fmt(commission);
  $('margin-profit').textContent = fmt(netProfit);
  const rateEl = $('margin-rate');
  rateEl.textContent = fmtPct(marginRate);
  rateEl.className = `stat-value sm ${marginRate >= 30 ? 'success' : marginRate >= 15 ? '' : 'error'}`;
  $('margin-roi').textContent = fmtPct(roi);
  $('margin-monthly').textContent = fmtWon(monthlyProfit);
  $('margin-breakeven').textContent = breakeven > 0 ? `${fmt(breakeven)}개/월` : '-';

  show('margin-result');
}

// ============================
// 7. CATEGORY ANALYSIS
// ============================
async function fetchCategory() {
  const code = $('cat-input').value.trim();
  if (!code) return;

  const btn = $('cat-search-btn');
  btn.disabled = true;
  show('cat-loading');
  hide('cat-result');

  try {
    const [summaryResult, keywordsResult] = await Promise.allSettled([
      wingAPI(`/tenants/rfm-ss/api/trends/summary?input=${encodeURIComponent(code)}&inputType=DISPLAY_CATEGORY_CODE`),
      wingAPI(`/tenants/rfm-ss/api/trends/category/top-keywords?categoryCode=${encodeURIComponent(code)}`),
    ]);

    if (summaryResult.status === 'fulfilled') {
      const s = summaryResult.value?.data || summaryResult.value || {};
      $('cat-pv').textContent = fmt(s.pvLast28Day || s.pv || 0);
      $('cat-products').textContent = fmt(s.productCount || s.totalProducts || 0);
      const trend = s.trendDirection || s.trend || '';
      const trendEl = $('cat-trend');
      trendEl.textContent = trend || '-';
      if (trend.includes('UP') || trend.includes('상승')) trendEl.className = 'stat-value sm success';
      else if (trend.includes('DOWN') || trend.includes('하락')) trendEl.className = 'stat-value sm error';
    }

    if (keywordsResult.status === 'fulfilled') {
      const kws = keywordsResult.value?.data || keywordsResult.value || [];
      const list = $('cat-keywords-list');
      list.innerHTML = '';
      const arr = Array.isArray(kws) ? kws : kws.keywords || [];
      arr.slice(0, 30).forEach(kw => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.textContent = typeof kw === 'string' ? kw : kw.keyword || kw.name || '';
        tag.addEventListener('click', () => { switchTab('keyword'); $('kw-input').value = tag.textContent; searchKeyword(); });
        if (tag.textContent) list.appendChild(tag);
      });
    }

    show('cat-result');
  } catch (e) {
    setMsg('cat-result', e.message, 'error');
    show('cat-result');
  } finally {
    hide('cat-loading');
    btn.disabled = false;
  }
}

// ============================
// Boot
// ============================
document.addEventListener('DOMContentLoaded', init);
