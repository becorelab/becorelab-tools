/* 경쟁사 레이더 — 프론트 로직 */
const CHART_COLORS = ['#b25839','#5e7d3a','#a86a1c','#5d7da6','#a13a2f','#7b6b8d','#3a7d6e','#c47a2b'];
const $ = s => document.querySelector(s);
const won = v => v == null ? '-' : '₩' + Number(v).toLocaleString();
const num = v => v == null ? '-' : Number(v).toLocaleString();

function toast(msg, err) {
  const t = document.createElement('div');
  t.className = 'toast' + (err ? ' err' : '');
  t.textContent = msg;
  $('#toasts').appendChild(t);
  setTimeout(() => t.remove(), 3500);
}
async function api(url, opt) {
  const r = await fetch(url, opt);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

/* ---------- 대시보드 ---------- */
async function loadAll() {
  await Promise.all([loadSummary(), loadAlerts(), loadProducts()]);
}

async function loadSummary() {
  const s = await api('/api/summary');
  const cards = [
    { label: '추적 제품', value: s.total, sub: `쿠팡 ${s.coupang} · 네이버 ${s.naver}` },
    { label: '오늘 변동 알림', value: s.today_alerts, sub: `누적 ${s.total_alerts}건`, accent: s.today_alerts > 0 },
    { label: '우리 평균가', value: s.avg_price_mine != null ? won(s.avg_price_mine) : '-', sub: `일비아 ${s.mine}개` },
    { label: '경쟁사 평균가', value: s.avg_price_competitors != null ? won(s.avg_price_competitors) : '-', sub: `${s.competitors}개 비교` },
  ];
  $('#summary').innerHTML = cards.map(c => `
    <div class="card">
      <div class="card-label">${c.label}</div>
      <div class="card-value ${c.accent ? 'accent' : ''}">${c.value}</div>
      <div class="card-sub">${c.sub}</div>
    </div>`).join('');
}

async function loadAlerts() {
  const a = await api('/api/alerts');
  $('#alertCount').textContent = a.length;
  if (!a.length) { $('#alerts').innerHTML = '<div class="alert-empty">아직 감지된 변동이 없어요. 내일 수집부터 가격·리뷰 변화가 표시됩니다 📈</div>'; return; }
  $('#alerts').innerHTML = a.slice(0, 12).map(x => `
    <div class="alert-item ${x.type}">
      <span class="msg">${x.message}</span>
      <span class="when">${(x.snap_date || '').slice(5)}</span>
    </div>`).join('');
}

function deltaTag(v, invert) {
  // invert=true: 가격은 내려가면 좋음(green), 올라가면 red
  if (v == null || v === 0) return '<span class="delta flat">―</span>';
  const down = v < 0;
  const good = invert ? down : !down;
  const arrow = down ? '▼' : '▲';
  return `<span class="delta ${good ? 'down' : 'up'}">${arrow}${num(Math.abs(v))}</span>`;
}

async function loadProducts() {
  const items = await api('/api/products');
  $('#prodCount').textContent = items.length;
  if (!items.length) {
    $('#grid').innerHTML = '<div class="card" style="grid-column:1/-1;text-align:center;color:var(--ink-3);padding:40px;">추적할 경쟁사 제품을 추가해보세요 →<br><br><button class="btn btn-primary" onclick="document.getElementById(\'btnAdd\').click()">+ 첫 제품 추가</button></div>';
    return;
  }
  $('#grid').innerHTML = items.map(cardHTML).join('');
  items.forEach(p => { if (p.spark && p.spark.length > 1) drawSpark(p); });
  document.querySelectorAll('.product-card').forEach(el =>
    el.onclick = () => openDetail(el.dataset.id));
}

function cardHTML(p) {
  const plat = p.platform === 'coupang'
    ? '<span class="badge badge-coupang">쿠팡</span>'
    : '<span class="badge badge-naver">네이버</span>';
  const mine = p.is_mine ? '<span class="badge badge-mine">우리 제품</span>' : '';
  const hasData = p.price != null || p.review_count != null;
  const body = hasData ? `
    <div class="pc-metrics">
      <div>
        <div class="pc-metric-label">현재가</div>
        <div class="pc-price">${won(p.price)}</div>
      </div>
      <div>${deltaTag(p.price_change, true)}</div>
      <div style="margin-left:auto;text-align:right;">
        <div class="pc-metric-label">리뷰</div>
        <div class="pc-review">${num(p.review_count)} ${p.review_change ? deltaTag(p.review_change, false) : ''}</div>
      </div>
    </div>
    ${p.ranking ? `<div class="pc-metric-label">${p.platform === 'coupang' ? '쿠팡' : '네이버'} 순위 ${p.ranking}위 ${p.rank_change ? deltaTag(p.rank_change, true) : ''}</div>` : ''}
    <div class="spark"><canvas id="spark${p.id}"></canvas></div>`
    : `<div class="pc-empty">아직 수집 데이터가 없어요. '전체 수집'을 눌러 첫 스냅샷을 찍어보세요.</div>`;
  return `
    <div class="product-card ${p.is_mine ? 'mine' : ''}" data-id="${p.id}">
      <div class="pc-top">
        <div>
          <div class="pc-label">${p.label}</div>
          ${p.brand ? `<div class="pc-brand">${p.brand}</div>` : ''}
        </div>
        <div style="display:flex;flex-direction:column;gap:4px;align-items:flex-end;">${plat}${mine}</div>
      </div>
      ${body}
    </div>`;
}

function drawSpark(p) {
  const el = document.getElementById('spark' + p.id);
  if (!el) return;
  const data = p.spark.filter(s => s.price != null);
  if (data.length < 2) return;
  new Chart(el, {
    type: 'line',
    data: {
      labels: data.map(s => s.d.slice(5)),
      datasets: [{
        data: data.map(s => s.price),
        borderColor: '#b25839', backgroundColor: 'rgba(178,88,57,0.08)',
        fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
    },
  });
}

/* ---------- 제품 추가 ---------- */
$('#btnAdd').onclick = () => $('#addModal').classList.add('open');
document.querySelectorAll('[data-close]').forEach(b =>
  b.onclick = e => e.target.closest('.modal-overlay').classList.remove('open'));

$('#btnSave').onclick = async () => {
  const body = {
    platform: $('#f_platform').value,
    label: $('#f_label').value.trim(),
    keyword: $('#f_keyword').value.trim() || null,
    match_name: $('#f_match').value.trim() || null,
    product_url: $('#f_url').value.trim() || null,
    brand: $('#f_brand').value.trim() || null,
    is_mine: $('#f_mine').checked ? 1 : 0,
  };
  if (!body.label) { toast('별칭을 입력해주세요', true); return; }
  if (!body.keyword && !body.product_url) { toast('키워드 또는 URL이 필요해요', true); return; }
  try {
    const r = await api('/api/products', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    $('#addModal').classList.remove('open');
    ['f_label', 'f_keyword', 'f_match', 'f_url', 'f_brand'].forEach(i => $('#' + i).value = '');
    $('#f_mine').checked = false;
    toast('추가 완료! 첫 수집 중...');
    await api(`/api/products/${r.id}/refresh`, { method: 'POST' });
    toast('첫 스냅샷 수집 완료 ✅');
    loadAll();
  } catch (e) { toast('추가 실패: ' + e.message, true); }
};

/* ---------- 전체 수집 ---------- */
$('#btnSnapshot').onclick = async () => {
  const btn = $('#btnSnapshot');
  btn.innerHTML = '<span class="spin"></span> 수집 중...';
  btn.disabled = true;
  try {
    const r = await api('/api/snapshot', { method: 'POST' });
    toast(`수집 완료: 성공 ${r.ok} / 실패 ${r.fail} / 알림 ${r.alerts}건`);
    loadAll();
  } catch (e) { toast('수집 실패: ' + e.message, true); }
  finally { btn.innerHTML = '🔄 전체 수집'; btn.disabled = false; }
};

$('#btnSeen').onclick = async () => { await api('/api/alerts/seen', { method: 'POST' }); loadAlerts(); };

/* ---------- 상세 ---------- */
let detailCharts = [];
let curDetailId = null;

async function openDetail(id) {
  curDetailId = id;
  $('#detailModal').classList.add('open');
  $('#d_body').innerHTML = '<div class="loading"><span class="spin"></span> 불러오는 중...</div>';
  const d = await api('/api/products/' + id);
  const p = d.product;
  $('#d_title').textContent = p.label;
  const snaps = d.snapshots;
  const last = snaps[snaps.length - 1] || {};

  detailCharts.forEach(c => c.destroy()); detailCharts = [];

  const metrics = `
    <div class="detail-metrics">
      <div class="dm"><div class="dm-label">현재가</div><div class="dm-value">${won(last.price)}</div></div>
      <div class="dm"><div class="dm-label">리뷰수</div><div class="dm-value">${num(last.review_count)}</div></div>
      <div class="dm"><div class="dm-label">평점</div><div class="dm-value">${last.rating ? last.rating.toFixed(2) + '★' : '-'}</div></div>
      <div class="dm"><div class="dm-label">${p.platform === 'coupang' ? '쿠팡 순위' : '검색 순위'}</div><div class="dm-value">${last.ranking ? last.ranking + '위' : '-'}</div></div>
    </div>`;

  const hasTrend = snaps.filter(s => s.price != null).length > 1;
  const trendBox = hasTrend
    ? `<div class="sub-h">📈 가격 추이</div><div class="chart-box"><canvas id="cPrice"></canvas></div>
       <div class="sub-h">💬 리뷰수 추이</div><div class="chart-box"><canvas id="cReview"></canvas></div>`
    : `<div class="muted" style="padding:10px 0;">추이 그래프는 2일치 이상 수집되면 표시됩니다. (현재 ${snaps.length}일)</div>`;

  const opts = d.latest_options;
  let optBox = '';
  if (opts && opts.length) {
    optBox = `<div class="sub-h">🧩 옵션 구성 (리뷰 기준 점유율)</div><div class="opt-list">` +
      opts.map(o => `<div class="opt-row">
        <span class="opt-name">${o.name}</span>
        <span class="opt-bar"><i style="width:${o.share}%"></i></span>
        <span class="opt-pct">${o.share}%</span></div>`).join('') + `</div>`;
  } else if (p.platform === 'coupang') {
    optBox = `<div class="sub-h">🧩 옵션 구성</div><div class="muted">상단 '⭐ 평점·옵션 분석' 버튼으로 리뷰를 분석하면 옵션 구성이 표시됩니다.</div>`;
  }

  const alertsBox = d.alerts.length
    ? `<div class="sub-h">🔔 변동 이력</div><div class="alerts">` +
      d.alerts.slice(0, 15).map(a => `<div class="alert-item ${a.type}"><span class="msg">${a.message}</span><span class="when">${(a.snap_date || '').slice(5)}</span></div>`).join('') + `</div>`
    : '';

  $('#d_body').innerHTML = metrics + trendBox + optBox + alertsBox;

  if (hasTrend) {
    const labels = snaps.map(s => s.snap_date.slice(5));
    detailCharts.push(lineChart('cPrice', labels, snaps.map(s => s.price), '가격', true));
    detailCharts.push(lineChart('cReview', labels, snaps.map(s => s.review_count), '리뷰수', false));
  }
}

function lineChart(canvasId, labels, data, label, isPrice) {
  const el = document.getElementById(canvasId);
  if (!el) return { destroy() {} };
  return new Chart(el, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label, data,
        borderColor: '#b25839', backgroundColor: 'rgba(178,88,57,0.08)',
        fill: true, tension: 0.3, pointRadius: 3, pointHoverRadius: 7,
        pointBackgroundColor: '#b25839', borderWidth: 2.5,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#2a241f', cornerRadius: 8, padding: 10,
          callbacks: { label: c => (isPrice ? '₩' : '') + Number(c.raw).toLocaleString() + (isPrice ? '' : '건') },
        },
      },
      scales: {
        y: { grid: { color: '#f0eadf' }, ticks: { callback: v => isPrice ? (v >= 1e4 ? (v / 1e4).toFixed(1) + '만' : v) : Number(v).toLocaleString() } },
        x: { grid: { display: false } },
      },
    },
  });
}

$('#d_reviews').onclick = async () => {
  if (!curDetailId) return;
  const btn = $('#d_reviews');
  btn.innerHTML = '<span class="spin"></span> 분석 중...'; btn.disabled = true;
  try {
    await api(`/api/products/${curDetailId}/reviews`, { method: 'POST' });
    toast('평점·옵션 분석 완료 ✅');
    openDetail(curDetailId);
  } catch (e) { toast('분석 실패(쿠팡 리뷰 다운로드는 시간이 걸려요): ' + e.message, true); }
  finally { btn.innerHTML = '⭐ 평점·옵션 분석'; btn.disabled = false; }
};

$('#d_delete').onclick = async () => {
  if (!curDetailId || !confirm('이 제품과 모든 추적 기록을 삭제할까요?')) return;
  await api('/api/products/' + curDetailId, { method: 'DELETE' });
  $('#detailModal').classList.remove('open');
  toast('삭제 완료'); loadAll();
};

loadAll();
