/* 비코어랩 ERP — 프론트엔드 */

const API = '';
let currentUser = null;
let currentPage = 'dashboard';

function setDateRange(preset, prefix) {
  const now = new Date();
  const fromEl = document.getElementById(`${prefix}-from`);
  const toEl = document.getElementById(`${prefix}-to`);
  if (!fromEl || !toEl) return;
  let f, t;
  const iso = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  if (preset === 'yesterday') {
    const y = new Date(now); y.setDate(y.getDate() - 1);
    f = t = iso(y);
  } else if (preset === '7days') {
    const d7 = new Date(now); d7.setDate(d7.getDate() - 6);
    f = iso(d7); t = iso(now);
  } else if (preset === 'thisMonth') {
    f = iso(new Date(now.getFullYear(), now.getMonth(), 1)); t = iso(now);
  } else if (preset === 'lastMonth') {
    f = iso(new Date(now.getFullYear(), now.getMonth() - 1, 1));
    t = iso(new Date(now.getFullYear(), now.getMonth(), 0));
  }
  fromEl.value = f; toEl.value = t;
  if (prefix === 'sales') loadSales();
  else if (prefix === 'summary') loadSalesSummary();
  else if (prefix === 'order') loadOrders();
}

// ── API Helper ──
async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '서버 오류' }));
    throw new Error(err.detail || '요청 실패');
  }
  return res.json();
}

// ── Toast ──
function toast(msg, type = 'success') {
  const c = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ── 숫자 포맷 ──
function fmt(n) {
  return Number(n || 0).toLocaleString('ko-KR');
}

// ── Navigation ──
function navigate(page) {
  currentPage = page;
  try { localStorage.setItem('erp_page', page); } catch (e) {}
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.page === page);
  });
  document.querySelectorAll('.page').forEach(el => {
    el.classList.toggle('hidden', el.id !== `page-${page}`);
  });
  document.getElementById('page-title').textContent = {
    dashboard: '대시보드',
    partners: '거래처 관리',
    products: '품목 관리',
    stock: '재고 현황',
    sales: '매출 관리',
    orders: '발주 관리',
    pricing: '기준판매가',
    calendar: '일정 관리',
    kakao: '🎁 선물 트렌드 — 카카오 선물하기 베스트',
    radar: '📡 경쟁사 레이더 — 광고 품목 경쟁사 가격추적',
    naverad: '📇 네이버 광고 — 검색광고(SA)',
    salesanalysis: '📈 매출 분석 — 정산 확정 기준 (1~6월)',
    sourcing: '🔍 소싱박스',
    users: '사용자 관리',
  }[page] || '';

  const loaders = {
    dashboard: loadDashboard,
    partners: loadPartners,
    products: loadProducts,
    stock: loadStock,
    sales: loadSales,
    orders: loadOrders,
    users: loadUsers,
    pricing: loadPricing,
    calendar: loadCalendar,
    kakao: () => loadKakao(),
    radar: loadRadar,
    naverad: () => loadNaverAd(),
    salesanalysis: () => loadSalesAnalysis(),
  };
  if (loaders[page]) loaders[page]();
}

// ── Dashboard ──
let chartTrend = null;
let chartChannels = null;
let chartSalesSummary = null;

const CHART_COLORS = ['#b25839','#5e7d3a','#a86a1c','#5d7da6','#a13a2f','#7b6b8d','#3a7d6e','#c47a2b','#6b8da1','#8d6b5a'];

async function loadDashboard() {
  try {
    const [d, trend, channels, topProducts] = await Promise.all([
      api('/api/dashboard'),
      api('/api/dashboard/trend?days=30'),
      api('/api/dashboard/channels'),
      api('/api/dashboard/top-products'),
    ]);
    document.getElementById('dash-today-sales').textContent = '₩' + fmt(d.today_sales);
    document.getElementById('dash-month-sales').textContent = '₩' + fmt(d.month_sales);
    document.getElementById('dash-lowstock').textContent = fmt(d.low_stock);
    document.getElementById('dash-pending-po').textContent = fmt(d.pending_po);

    renderTrendChart(trend);
    renderChannelChart(channels);
    renderChannelTable(channels);
  } catch (e) {
    toast(e.message, 'error');
  }
}

function renderTrendChart(data) {
  const ctx = document.getElementById('chart-trend');
  if (chartTrend) chartTrend.destroy();
  chartTrend = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.sale_date.slice(5)),
      datasets: [{
        label: '일매출',
        data: data.map(d => d.total),
        borderColor: '#b25839',
        backgroundColor: 'rgba(178,88,57,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
        pointHoverRadius: 8,
        pointBackgroundColor: '#b25839',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderWidth: 3,
        pointHoverBorderColor: '#b25839',
        borderWidth: 2.5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#2a241f',
          titleFont: { size: 12 },
          bodyFont: { size: 13, weight: '600' },
          padding: 10,
          cornerRadius: 8,
          displayColors: false,
          callbacks: { label: ctx => '₩' + fmt(ctx.raw) },
        },
      },
      scales: {
        y: { ticks: { callback: v => v >= 1e6 ? (v/1e6).toFixed(0) + 'M' : fmt(v) }, grid: { color: '#f0eadf' } },
        x: { grid: { display: false } },
      },
    },
  });
}

function renderChannelChart(data) {
  const ctx = document.getElementById('chart-channels');
  if (chartChannels) chartChannels.destroy();
  if (!data.length) return;
  chartChannels = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(d => d.channel || '기타'),
      datasets: [{
        data: data.map(d => d.total),
        backgroundColor: CHART_COLORS.slice(0, data.length),
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '62%',
      plugins: {
        legend: { position: 'right', labels: { boxWidth: 10, padding: 10, font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => ctx.label + ': ₩' + fmt(ctx.raw) } },
      },
    },
  });
}

function renderChannelTable(data) {
  const tbody = document.getElementById('dash-top-products');
  if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted" style="padding:24px">이번달 매출 데이터 없음</td></tr>'; return; }
  const grandTotal = data.reduce((s, d) => s + d.total, 0) || 1;
  tbody.innerHTML = data.map((ch, i) => {
    const pct = ((ch.total / grandTotal) * 100).toFixed(1);
    return `<tr>
      <td>${i + 1}</td>
      <td><strong>${ch.channel || '기타'}</strong></td>
      <td class="text-right number">${fmt(ch.cnt)}건</td>
      <td class="text-right number">₩${fmt(ch.total)}</td>
      <td><div class="bar-cell"><div class="bar-fill" style="width:${pct}%;background:${CHART_COLORS[i % CHART_COLORS.length]}"></div><span class="bar-pct">${pct}%</span></div></td>
    </tr>`;
  }).join('') + `<tr style="background:var(--bg);font-weight:700">
    <td></td><td>합계</td>
    <td class="text-right number">${fmt(data.reduce((s,d)=>s+d.cnt,0))}건</td>
    <td class="text-right number">₩${fmt(grandTotal)}</td><td></td></tr>`;
}

// ── Partners ──
let partnersPage = 1;
async function loadPartners(page = 1) {
  partnersPage = page;
  const q = document.getElementById('partner-search')?.value || '';
  try {
    const d = await api(`/api/partners?q=${encodeURIComponent(q)}&page=${page}&size=30`);
    const tbody = document.getElementById('partners-tbody');
    tbody.innerHTML = d.items.map(p => `
      <tr>
        <td>${p.partner_code}</td>
        <td><strong>${p.name}</strong></td>
        <td><span class="badge badge-${p.type === 'channel' ? 'info' : p.type === 'both' ? 'warning' : 'default'}">${
          p.type === 'supplier' ? '공급처' : p.type === 'channel' ? '판매채널' : '공급+판매'
        }</span></td>
        <td>${p.business_no || '-'}</td>
        <td>${p.ceo_name || '-'}</td>
        <td>${p.phone || p.mobile || '-'}</td>
        <td>
          <button class="btn btn-sm" onclick="editPartner(${p.id})">수정</button>
          <button class="btn btn-sm btn-danger" onclick="deletePartner(${p.id},'${p.name}')">삭제</button>
        </td>
      </tr>
    `).join('');
    document.getElementById('partners-info').textContent = `총 ${d.total}건`;
    renderPagination('partners-paging', d.total, 30, page, p => loadPartners(p));
  } catch (e) { toast(e.message, 'error'); }
}

async function editPartner(id) {
  const p = id ? await api(`/api/partners/${id}`) : {};
  const isNew = !id;
  const m = document.getElementById('modal');
  m.querySelector('.modal-header span').textContent = isNew ? '거래처 등록' : '거래처 수정';
  m.querySelector('.modal-body').innerHTML = `
    <div class="form-row">
      <div class="form-group"><label>거래처코드</label><input id="m-pcode" value="${p.partner_code || ''}" ${isNew ? '' : 'readonly'} /></div>
      <div class="form-group"><label>거래처명</label><input id="m-pname" value="${p.name || ''}" /></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>유형</label>
        <select id="m-ptype"><option value="supplier" ${p.type==='supplier'?'selected':''}>공급처</option>
          <option value="channel" ${p.type==='channel'?'selected':''}>판매채널</option>
          <option value="both" ${p.type==='both'?'selected':''}>공급+판매</option></select></div>
      <div class="form-group"><label>사업자번호</label><input id="m-pbiz" value="${p.business_no || ''}" /></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>대표자</label><input id="m-pceo" value="${p.ceo_name || ''}" /></div>
      <div class="form-group"><label>연락처</label><input id="m-pphone" value="${p.phone || ''}" /></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>이메일</label><input id="m-pemail" value="${p.email || ''}" /></div>
      <div class="form-group"><label>휴대폰</label><input id="m-pmobile" value="${p.mobile || ''}" /></div>
    </div>
    <div class="form-group"><label>주소</label><input id="m-paddress" value="${p.address || ''}" /></div>
    <div class="form-group"><label>메모</label><textarea id="m-pmemo" rows="2">${p.memo || ''}</textarea></div>
  `;
  m.querySelector('.modal-footer').innerHTML = `
    <button class="btn" onclick="closeModal()">취소</button>
    <button class="btn btn-primary" onclick="savePartner(${id || 0})">저장</button>`;
  openModal();
}

async function savePartner(id) {
  const data = {
    partner_code: document.getElementById('m-pcode').value,
    name: document.getElementById('m-pname').value,
    type: document.getElementById('m-ptype').value,
    business_no: document.getElementById('m-pbiz').value,
    ceo_name: document.getElementById('m-pceo').value,
    phone: document.getElementById('m-pphone').value,
    mobile: document.getElementById('m-pmobile').value,
    email: document.getElementById('m-pemail').value,
    address: document.getElementById('m-paddress').value,
    memo: document.getElementById('m-pmemo').value,
  };
  if (!data.partner_code || !data.name) return toast('코드와 이름은 필수입니다', 'error');
  try {
    if (id) await api(`/api/partners/${id}`, { method: 'PUT', body: data });
    else await api('/api/partners', { method: 'POST', body: data });
    closeModal();
    toast(id ? '거래처가 수정되었습니다' : '거래처가 등록되었습니다');
    loadPartners(partnersPage);
  } catch (e) { toast(e.message, 'error'); }
}

async function deletePartner(id, name) {
  if (!confirm(`"${name}" 거래처를 삭제하시겠습니까?`)) return;
  try {
    await api(`/api/partners/${id}`, { method: 'DELETE' });
    toast('삭제되었습니다');
    loadPartners(partnersPage);
  } catch (e) { toast(e.message, 'error'); }
}

// ── Products ──
let productsPage = 1;
async function loadProducts(page = 1) {
  productsPage = page;
  const q = document.getElementById('product-search')?.value || '';
  try {
    const d = await api(`/api/products?q=${encodeURIComponent(q)}&page=${page}&size=30`);
    const tbody = document.getElementById('products-tbody');
    tbody.innerHTML = d.items.map(p => {
      const stockClass = (p.qty_on_hand ?? 0) <= (p.safety_stock || 10) ? 'text-danger' : '';
      return `
      <tr>
        <td>${p.product_code}</td>
        <td><strong>${p.name}</strong></td>
        <td>${p.spec || '-'}</td>
        <td>${p.unit}</td>
        <td class="text-right number ${stockClass}">${fmt(p.qty_on_hand ?? 0)}</td>
        <td class="text-right number">${fmt(p.purchase_price)}</td>
        <td class="text-right number">${fmt(p.sell_price)}</td>
        <td>
          <button class="btn btn-sm" onclick="editProduct(${p.id})">수정</button>
          <button class="btn btn-sm btn-danger" onclick="deleteProduct(${p.id},'${p.name.replace(/'/g,"\\'")}')">삭제</button>
        </td>
      </tr>`;
    }).join('');
    document.getElementById('products-info').textContent = `총 ${d.total}건`;
    renderPagination('products-paging', d.total, 30, page, p => loadProducts(p));
  } catch (e) { toast(e.message, 'error'); }
}

async function editProduct(id) {
  const p = id ? await api(`/api/products/${id}`) : {};
  const isNew = !id;
  const m = document.getElementById('modal');
  m.querySelector('.modal-header span').textContent = isNew ? '품목 등록' : '품목 수정';
  m.querySelector('.modal-body').innerHTML = `
    <div class="form-row">
      <div class="form-group"><label>품목코드</label><input id="m-prcode" value="${p.product_code || ''}" ${isNew ? '' : 'readonly'} /></div>
      <div class="form-group"><label>품목명</label><input id="m-prname" value="${p.name || ''}" /></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>규격</label><input id="m-prspec" value="${p.spec || ''}" /></div>
      <div class="form-group"><label>단위</label><input id="m-prunit" value="${p.unit || 'EA'}" /></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>매입단가</label><input type="number" id="m-prpurchase" value="${p.purchase_price || 0}" /></div>
      <div class="form-group"><label>판매단가</label><input type="number" id="m-prsell" value="${p.sell_price || 0}" /></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>안전재고</label><input type="number" id="m-prsafety" value="${p.safety_stock || 0}" /></div>
      <div class="form-group"><label>리드타임(일)</label><input type="number" id="m-prlead" value="${p.lead_time_days || 7}" /></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>이카운트코드</label><input id="m-precount" value="${p.ecount_code || ''}" /></div>
      <div class="form-group"><label>이지어드민코드</label><input id="m-prezadmin" value="${p.ezadmin_code || ''}" /></div>
    </div>
  `;
  m.querySelector('.modal-footer').innerHTML = `
    <button class="btn" onclick="closeModal()">취소</button>
    <button class="btn btn-primary" onclick="saveProduct(${id || 0})">저장</button>`;
  openModal();
}

async function saveProduct(id) {
  const data = {
    product_code: document.getElementById('m-prcode').value,
    name: document.getElementById('m-prname').value,
    spec: document.getElementById('m-prspec').value,
    unit: document.getElementById('m-prunit').value,
    purchase_price: Number(document.getElementById('m-prpurchase').value),
    sell_price: Number(document.getElementById('m-prsell').value),
    safety_stock: Number(document.getElementById('m-prsafety').value),
    lead_time_days: Number(document.getElementById('m-prlead').value),
    ecount_code: document.getElementById('m-precount').value,
    ezadmin_code: document.getElementById('m-prezadmin').value,
  };
  if (!data.product_code || !data.name) return toast('코드와 이름은 필수입니다', 'error');
  try {
    if (id) await api(`/api/products/${id}`, { method: 'PUT', body: data });
    else await api('/api/products', { method: 'POST', body: data });
    closeModal();
    toast(id ? '품목이 수정되었습니다' : '품목이 등록되었습니다');
    loadProducts(productsPage);
  } catch (e) { toast(e.message, 'error'); }
}

// ── Product Delete ──
async function deleteProduct(id, name) {
  if (!confirm(`"${name}" 품목을 삭제하시겠습니까?\n(재고 및 매출 이력은 유지됩니다)`)) return;
  try {
    await api(`/api/products/${id}`, { method: 'DELETE' });
    toast('품목이 삭제되었습니다');
    loadProducts(productsPage);
  } catch (e) { toast(e.message, 'error'); }
}

// ── Stock ──
let lastStockClassified = null;
let stockSort = { key: null, dir: 1 };
let outboundMap = {};          // code → 기간 출고량
let outboundLabel = '기간 출고량';
let outboundParams = { preset: 'this_month' };  // 기본값: 이번달

async function loadOutbound() {
  const qs = new URLSearchParams(outboundParams).toString();
  try {
    const data = await api(`/api/stock/outbound?${qs}`);
    outboundMap = {};
    (data.items || []).forEach(it => { outboundMap[String(it.code)] = it.qty; });
    const presetLabels = { this_month: '이번달', last_month: '저번달', last_week: '최근 1주' };
    outboundLabel = outboundParams.preset ? presetLabels[outboundParams.preset] || '기간' : '지정기간';
    const th = document.getElementById('stock-outbound-th');
    if (th) th.innerHTML = `기간 출고량<br><span style="font-size:11px;font-weight:400;color:var(--ink-3)">${outboundLabel} (${data.start}~${data.end})</span>`;
    // 프리셋 버튼 활성화 표시
    ['this_month', 'last_month', 'last_week'].forEach(p => {
      const b = document.getElementById('ob-preset-' + p);
      if (b) b.classList.toggle('btn-primary', outboundParams.preset === p);
    });
  } catch (e) { toast(e.message, 'error'); }
}

function setOutboundPreset(preset) {
  outboundParams = { preset };
  document.getElementById('ob-start').value = '';
  document.getElementById('ob-end').value = '';
  loadOutbound().then(renderStockTable);
}

function setOutboundRange() {
  const start = document.getElementById('ob-start').value;
  const end = document.getElementById('ob-end').value;
  if (!start || !end) { toast('시작일과 종료일을 모두 선택해주세요', 'error'); return; }
  outboundParams = { start, end };
  ['this_month', 'last_month', 'last_week'].forEach(p => {
    const b = document.getElementById('ob-preset-' + p); if (b) b.classList.remove('btn-primary');
  });
  loadOutbound().then(renderStockTable);
}

async function loadStock() {
  const q = document.getElementById('stock-search')?.value || '';
  const alertOnly = document.getElementById('stock-alert')?.checked || false;
  const hideZero = document.getElementById('stock-hide-zero')?.checked || false;
  const showMaterial = document.getElementById('stock-show-material')?.checked || false;
  try {
    const [items_raw, summary] = await Promise.all([
      api(`/api/stock?q=${encodeURIComponent(q)}&alert_only=${alertOnly}&show_material=${showMaterial}`),
      api('/api/stock/summary'),
      loadOutbound(),
    ]);
    let items = items_raw;
    if (hideZero) items = items.filter(s => (s.qty_on_hand ?? 0) > 0);

    const maxQty = Math.max(...items.map(s => s.qty_on_hand ?? 0), 1);

    const classified = items.map(s => {
      const qty = s.qty_on_hand ?? 0;
      const safe = s.safety_stock || 0;
      const avgDaily = s.avg_daily_out || 0;
      const days = (qty > 0 && avgDaily > 0) ? Math.round(qty / avgDaily) : null;

      let status = 'normal';
      if (s.is_discontinued) status = 'discontinued';
      else if (qty <= 0) status = 'out';
      else if (days !== null && days <= 7) status = 'danger';
      else if (qty <= safe && safe > 0) status = 'low';
      else if (days !== null && days <= 14) status = 'warning';
      return { ...s, qty, safe, avgDaily, days, status };
    });

    const active = classified.filter(s => s.status !== 'discontinued');
    const outItems = active.filter(s => s.status === 'out');
    const dangerItems = active.filter(s => s.status === 'danger').sort((a, b) => (a.days ?? 0) - (b.days ?? 0));
    const warningItems = active.filter(s => s.status === 'warning' || s.status === 'low').sort((a, b) => (a.days ?? 999) - (b.days ?? 999));
    const pendingInbound = classified.filter(s => (s.pending_inbound ?? 0) > 0);
    const CARD_LIMIT = 5;

    function renderCardItems(items, badgeFn, emptyMsg) {
      if (!items.length) return `<div class="stock-dash-ok">${emptyMsg}</div>`;
      const show = items.slice(0, CARD_LIMIT);
      const rest = items.length - CARD_LIMIT;
      let html = show.map(s => `<div class="stock-dash-item">
        <span class="stock-dash-name">${s.name.replace(/\[비코어랩\]/g,'').replace(/\(비코어랩\)/g,'').trim()}</span>
        ${badgeFn(s)}
      </div>`).join('');
      if (rest > 0) html += `<div class="stock-dash-more">외 ${rest}건</div>`;
      return html;
    }

    const dashEl = document.getElementById('stock-dashboard');
    if (dashEl) {
      dashEl.innerHTML = `
        <div class="stock-dash-card stock-dash-danger">
          <div class="stock-dash-header">
            <span class="stock-dash-icon">🚨</span>
            <div>
              <div class="stock-dash-title">소진 임박</div>
              <div class="stock-dash-subtitle">7일 이내 소진 예상</div>
            </div>
            <span class="stock-dash-count stock-dash-count-danger">${dangerItems.length}</span>
          </div>
          <div class="stock-dash-body">
            ${renderCardItems(dangerItems, s => `<span class="stock-dash-badge stock-dash-badge-danger">${s.days}일</span>`, '✅ 모두 안전')}
          </div>
          ${outItems.length > 0 ? `<div class="stock-dash-footer stock-dash-footer-danger">품절 ${outItems.length}건</div>` : ''}
        </div>
        <div class="stock-dash-card stock-dash-warning">
          <div class="stock-dash-header">
            <span class="stock-dash-icon">⚠️</span>
            <div>
              <div class="stock-dash-title">주의</div>
              <div class="stock-dash-subtitle">14일 이내 소진 예상</div>
            </div>
            <span class="stock-dash-count stock-dash-count-warning">${warningItems.length}</span>
          </div>
          <div class="stock-dash-body">
            ${renderCardItems(warningItems, s => `<span class="stock-dash-badge stock-dash-badge-warning">${s.days !== null ? s.days + '일' : '부족'}</span>`, '✅ 해당 없음')}
          </div>
        </div>
        <div class="stock-dash-card stock-dash-inbound">
          <div class="stock-dash-header">
            <span class="stock-dash-icon">📦</span>
            <div>
              <div class="stock-dash-title">입고 예정</div>
              <div class="stock-dash-subtitle">발주 후 입고 대기</div>
            </div>
            <span class="stock-dash-count stock-dash-count-inbound">${pendingInbound.length}</span>
          </div>
          <div class="stock-dash-body">
            ${renderCardItems(pendingInbound, s => `<span class="stock-dash-badge stock-dash-badge-inbound">+${fmt(s.pending_inbound)}${s.next_inbound_date ? ' <span style="font-weight:400;opacity:.85">' + s.next_inbound_date.slice(5) + '</span>' : ''}</span>`, '<span style="color:var(--ink-3)">예정 없음</span>')}
          </div>
        </div>`;
    }

    lastStockClassified = classified;
    renderStockTable();
  } catch (e) { toast(e.message, 'error'); }
}

function sortStock(key) {
  if (stockSort.key === key) stockSort.dir *= -1;
  else { stockSort.key = key; stockSort.dir = 1; }
  renderStockTable();
}

function renderStockTable() {
  if (!lastStockClassified) return;
  let rows = lastStockClassified.slice();
  if (stockSort.key === 'name') rows.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'ko') * stockSort.dir);
  else if (stockSort.key === 'qty') rows.sort((a, b) => ((a.qty ?? 0) - (b.qty ?? 0)) * stockSort.dir);
  const arrow = stockSort.dir > 0 ? '▲' : '▼';
  const indName = document.getElementById('sort-ind-name'); if (indName) indName.textContent = stockSort.key === 'name' ? arrow : '';
  const indQty = document.getElementById('sort-ind-qty'); if (indQty) indQty.textContent = stockSort.key === 'qty' ? arrow : '';

  const maxQty = Math.max(...rows.map(s => s.qty_on_hand ?? 0), 1);
  const tbody = document.getElementById('stock-tbody');
  tbody.innerHTML = rows.map(s => {
      const barPct = Math.min((s.qty / maxQty) * 100, 100);
      const safePct = s.safe > 0 ? Math.min((s.safe / maxQty) * 100, 100) : 0;

      const colorMap = { discontinued: 'var(--ink-3)', out: 'var(--red)', danger: 'var(--red)', low: 'var(--amber)', warning: 'var(--amber)', normal: 'var(--green)' };
      const badgeMap = {
        discontinued: '<span class="badge" style="background:var(--ink-4);color:var(--ink-2)">단종</span>',
        out: '<span class="badge badge-danger">품절</span>',
        danger: '<span class="badge badge-danger">위험</span>',
        low: '<span class="badge badge-warning">부족</span>',
        warning: '<span class="badge badge-warning">주의</span>',
        normal: '<span class="badge badge-success">정상</span>'
      };
      const barColor = colorMap[s.status];
      const badge = badgeMap[s.status];

      let depletionText = '-';
      if (s.status === 'discontinued') depletionText = '<span class="text-muted">-</span>';
      else if (s.qty <= 0) depletionText = '<span class="text-danger">품절</span>';
      else if (s.days !== null) {
        if (s.days <= 7) depletionText = `<span class="text-danger">${s.days}일</span>`;
        else if (s.days <= 14) depletionText = `<span class="text-warning">${s.days}일</span>`;
        else depletionText = `${s.days}일`;
      } else depletionText = '<span class="text-muted">-</span>';

      let inboundText = '<span class="text-muted">-</span>';
      if (s.next_inbound_date) {
        const _today = new Date(); _today.setHours(0, 0, 0, 0);
        const _eta = new Date(s.next_inbound_date + 'T00:00:00');
        const _dday = Math.round((_eta - _today) / 86400000);
        const _lbl = _dday === 0 ? '오늘' : (_dday > 0 ? 'D-' + _dday : 'D+' + (-_dday));
        const _clr = _dday < 0 ? 'var(--red)' : (_dday <= 3 ? 'var(--green)' : 'var(--ink-2)');
        const _ddayTxt = _dday < 0 ? `지연 ${-_dday}일` : _lbl;
        inboundText = `<span style="white-space:nowrap;color:${_clr}">📦 ${s.next_inbound_date.slice(5)} <span style="font-size:11px;opacity:.85">${_ddayTxt}</span></span>`;
      }

      const qtyColor = s.status === 'out' ? 'var(--red)' : s.status === 'danger' || s.status === 'low' ? 'var(--amber)' : 'var(--ink)';

      const discBadge = s.is_discontinued ? ' <span class="badge" style="background:var(--ink-4);color:var(--ink-2);font-size:10px">단종</span>' : '';

      const obQty = outboundMap[String(s.ezadmin_code)] ?? outboundMap[String(s.product_code)] ?? 0;

      return `
      <tr style="cursor:pointer">
        <td onclick="event.stopPropagation()"><input type="checkbox" class="stock-check" value="${s.id}" onchange="updateStockBulkBar()" /></td>
        <td onclick="viewStockDetail(${s.id})">${s.product_code}</td>
        <td onclick="viewStockDetail(${s.id})"><strong>${s.name}</strong>${discBadge}</td>
        <td onclick="viewStockDetail(${s.id})" class="text-right number" style="font-size:14px;font-weight:600;color:${qtyColor}">${fmt(s.qty)}</td>
        <td onclick="viewStockDetail(${s.id})" style="min-width:120px">
          <div class="stock-bar">
            <div class="stock-bar-fill" style="width:${barPct}%;background:${barColor}"></div>
            ${safePct > 0 ? `<div class="stock-bar-safe" style="left:${safePct}%" title="안전재고: ${fmt(s.safe)}"></div>` : ''}
          </div>
        </td>
        <td onclick="viewStockDetail(${s.id})" class="text-right number">${s.avgDaily > 0 ? s.avgDaily.toFixed(1) : '-'}</td>
        <td onclick="viewStockDetail(${s.id})" class="text-right number">${obQty > 0 ? fmt(obQty) : '<span class="text-muted">-</span>'}</td>
        <td onclick="viewStockDetail(${s.id})" class="text-right">${depletionText}</td>
        <td onclick="viewStockDetail(${s.id})" class="text-right">${inboundText}</td>
        <td onclick="viewStockDetail(${s.id})">${badge}</td>
        <td><button class="btn btn-sm" onclick="event.stopPropagation();viewStockLedger(${s.id},'${(s.name||'').replace(/'/g,"\\'")}')">수불부</button></td>
      </tr>`;
    }).join('');
  document.getElementById('stock-info').textContent = `총 ${rows.length}건`;
}

function toggleStockCheckAll(el) {
  document.querySelectorAll('.stock-check').forEach(cb => { cb.checked = el.checked; });
  updateStockBulkBar();
}

function updateStockBulkBar() {
  const checked = document.querySelectorAll('.stock-check:checked');
  const bar = document.getElementById('stock-bulk-bar');
  const countEl = document.getElementById('stock-bulk-count');
  if (checked.length > 0) {
    bar.classList.remove('hidden');
    countEl.textContent = `${checked.length}건 선택`;
  } else {
    bar.classList.add('hidden');
  }
}

function clearStockSelection() {
  document.querySelectorAll('.stock-check').forEach(cb => { cb.checked = false; });
  document.getElementById('stock-check-all').checked = false;
  updateStockBulkBar();
}

async function bulkStockAction(action) {
  const checked = document.querySelectorAll('.stock-check:checked');
  const ids = Array.from(checked).map(cb => Number(cb.value));
  if (!ids.length) return;
  const labels = { delete: '삭제', discontinue: '단종 처리', activate: '판매 재개' };
  if (!confirm(`선택된 ${ids.length}건을 ${labels[action]}하시겠습니까?`)) return;
  try {
    const r = await api('/api/products/bulk-action', {
      method: 'POST',
      body: { ids, action },
    });
    toast(`${r.count}건 ${labels[action]} 완료`);
    clearStockSelection();
    loadStock();
  } catch (e) { toast(e.message, 'error'); }
}

async function viewStockDetail(productId) {
  try {
    const p = await api(`/api/products/${productId}`);
    const m = document.getElementById('modal');
    const cleanName = (p.name || '').replace(/\[비코어랩\]/g, '').replace(/\(비코어랩\)/g, '').trim();
    m.querySelector('.modal-header span').textContent = `품목 상세 — ${cleanName}`;

    const statusBadge = p.is_discontinued
      ? '<span class="badge" style="background:#e74c3c;color:#fff">단종</span>'
      : '<span class="badge badge-success">판매중</span>';

    const qtyVal = p.qty_on_hand ?? 0;
    const safeVal = p.safety_stock || 0;
    let stockBadge = '<span class="badge badge-success">정상</span>';
    if (qtyVal <= 0) stockBadge = '<span class="badge badge-danger">품절</span>';
    else if (safeVal > 0 && qtyVal <= safeVal) stockBadge = '<span class="badge badge-warning">부족</span>';

    m.querySelector('.modal-body').innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <div style="display:flex;gap:8px;align-items:center">
          ${statusBadge} ${stockBadge}
        </div>
        <span class="text-muted" style="font-size:12px">코드: ${p.product_code}</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px 24px;margin-bottom:20px">
        <div><span class="text-muted" style="font-size:12px">품목명</span><br><strong>${p.name}</strong></div>
        <div><span class="text-muted" style="font-size:12px">규격</span><br>${p.spec || '-'}</div>
        <div><span class="text-muted" style="font-size:12px">단위</span><br>${p.unit || 'EA'}</div>
        <div><span class="text-muted" style="font-size:12px">카테고리</span><br>${p.category || '-'}</div>
        <div><span class="text-muted" style="font-size:12px">매입가</span><br><strong class="number">₩${fmt(p.purchase_price || 0)}</strong></div>
        <div><span class="text-muted" style="font-size:12px">판매가</span><br><strong class="number">₩${fmt(p.sell_price || 0)}</strong></div>
        <div><span class="text-muted" style="font-size:12px">현재고</span><br><strong class="number" style="font-size:18px;color:${qtyVal <= 0 ? 'var(--red)' : qtyVal <= safeVal ? 'var(--amber)' : 'var(--green)'}">${fmt(qtyVal)}</strong></div>
        <div><span class="text-muted" style="font-size:12px">안전재고</span><br><strong class="number">${fmt(safeVal)}</strong></div>
        <div><span class="text-muted" style="font-size:12px">리드타임</span><br>${p.lead_time_days || 7}일</div>
        <div><span class="text-muted" style="font-size:12px">MOQ</span><br>${fmt(p.moq || 0)}</div>
        <div><span class="text-muted" style="font-size:12px">이지어드민 코드</span><br>${p.ezadmin_code || '-'}</div>
        <div><span class="text-muted" style="font-size:12px">바코드</span><br>${p.barcode || '-'}</div>
      </div>
      ${p.supplier_name ? `<div style="margin-bottom:12px"><span class="text-muted" style="font-size:12px">공급처</span><br>${p.supplier_name}</div>` : ''}
      <div style="border-top:1px solid var(--line);padding-top:16px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn-sm" onclick="event.stopPropagation();closeModal();viewStockLedger(${p.id},'${cleanName.replace(/'/g, "\\'")}')">📊 수불부</button>
        <button class="btn btn-sm" style="margin-left:auto;color:var(--amber)" onclick="toggleDiscontinue(${p.id}, ${p.is_discontinued ? 0 : 1})">${p.is_discontinued ? '🔄 판매 재개' : '⛔ 단종 처리'}</button>
        <button class="btn btn-sm" style="color:var(--red)" onclick="deleteFromStockDetail(${p.id},'${cleanName.replace(/'/g, "\\'")}')">🗑️ 삭제</button>
      </div>
    `;
    m.querySelector('.modal-footer').innerHTML = '<button class="btn" onclick="closeModal()">닫기</button>';
    openModal();
  } catch (e) { toast(e.message, 'error'); }
}

async function toggleDiscontinue(productId, discontinue) {
  const action = discontinue ? '단종 처리' : '판매 재개';
  if (!confirm(`이 품목을 ${action}하시겠습니까?`)) return;
  try {
    await api(`/api/products/${productId}/discontinue`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ discontinue: !!discontinue }),
    });
    toast(`${action} 완료`);
    closeModal();
    loadStock();
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteFromStockDetail(productId, productName) {
  if (!confirm(`"${productName}" 품목을 삭제하시겠습니까?\n(재고 및 매출 이력은 유지됩니다)`)) return;
  try {
    await api(`/api/products/${productId}`, { method: 'DELETE' });
    toast('품목이 삭제되었습니다');
    closeModal();
    loadStock();
  } catch (e) { toast(e.message, 'error'); }
}

async function viewStockLedger(productId, productName) {
  try {
    const data = await api(`/api/stock/sales-outbound/${productId}?days=90&period=daily`);
    const m = document.getElementById('modal');
    m.querySelector('.modal-header span').textContent = `수불부 — ${productName}`;
    const items = data.items || [];
    m.querySelector('.modal-body').innerHTML = `
      <div class="form-row mb-2" style="gap:24px">
        <div><span class="text-muted">최근 90일 출고량</span><br><strong class="number" style="font-size:20px">${fmt(data.total_qty)}개</strong></div>
        <div><span class="text-muted">일평균 출고</span><br><strong class="number" style="font-size:20px">${fmt(data.avg_daily)}개/일</strong></div>
        <div style="margin-left:auto;display:flex;gap:6px;align-items:end">
          <button class="btn btn-sm ${!window._ledgerWeekly?'btn-primary':''}" onclick="viewStockLedger(${productId},'${productName.replace(/'/g,"\\'")}');window._ledgerWeekly=false">일별</button>
          <button class="btn btn-sm ${window._ledgerWeekly?'btn-primary':''}" onclick="window._ledgerWeekly=true;viewStockLedgerWeekly(${productId},'${productName.replace(/'/g,"\\'")}')">주별</button>
        </div>
      </div>
      ${items.length ? `<div style="height:200px;margin-bottom:12px"><canvas id="chart-ledger"></canvas></div>
      <table>
        <thead><tr><th>날짜</th><th class="text-right">출고수량</th><th class="text-center">입고</th><th class="text-right">재고<span style="font-size:10px;font-weight:400;color:var(--ink-3)"> (추정)</span></th><th class="text-right">금액</th></tr></thead>
        <tbody>${items.map(t => `<tr${t.inbound ? ' style="background:rgba(88,150,90,0.08)"' : ''}>
          <td>${t.period}</td>
          <td class="text-right number">${t.qty ? fmt(t.qty) : '-'}</td>
          <td class="text-center number" style="color:#4a8a4c;font-weight:600">${t.inbound ? '📦 +' + fmt(t.inbound) : ''}</td>
          <td class="text-right number">${t.stock != null ? fmt(t.stock) : '-'}</td>
          <td class="text-right number">${t.amount ? '₩' + fmt(t.amount) : '-'}</td>
        </tr>`).join('')}</tbody>
      </table>
      <div style="font-size:11px;color:var(--ink-3);margin-top:6px">※ 재고는 현재고에서 이후 출고·입고를 역산한 <b>추정치</b>입니다 (외부 재고동기화 조정분 미반영). 📦=입고일.</div>` : '<div class="empty-state"><p>최근 90일 출고 이력이 없습니다</p></div>'}
    `;
    m.querySelector('.modal-footer').innerHTML = '<button class="btn" onclick="closeModal()">닫기</button>';
    openModal();
    if (items.length) {
      const reversed = [...items].reverse();
      new Chart(document.getElementById('chart-ledger'), {
        type: 'bar',
        data: { labels: reversed.map(d => d.period.slice(5)), datasets: [{ data: reversed.map(d => d.qty), backgroundColor: 'rgba(178,88,57,0.6)', borderRadius: 3 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => fmt(c.raw) + '개' } } },
          scales: { y: { grid: { color: '#f0eadf' } }, x: { grid: { display: false } } } },
      });
    }
  } catch (e) { toast(e.message, 'error'); }
}

async function viewStockLedgerWeekly(productId, productName) {
  try {
    const data = await api(`/api/stock/sales-outbound/${productId}?days=90&period=weekly`);
    const m = document.getElementById('modal');
    const items = data.items || [];
    m.querySelector('.modal-body').querySelector('table').outerHTML = items.length ? `
      <div style="height:200px;margin-bottom:12px"><canvas id="chart-ledger"></canvas></div>
      <table>
        <thead><tr><th>주차</th><th class="text-right">출고수량</th><th class="text-right">금액</th></tr></thead>
        <tbody>${items.map(t => `<tr>
          <td>${t.period}</td>
          <td class="text-right number">${fmt(t.qty)}</td>
          <td class="text-right number">₩${fmt(t.amount)}</td>
        </tr>`).join('')}</tbody>
      </table>` : '<p class="text-muted text-center">주별 데이터 없음</p>';
    const canvas = document.getElementById('chart-ledger');
    if (canvas && items.length) {
      const reversed = [...items].reverse();
      new Chart(canvas, {
        type: 'bar',
        data: { labels: reversed.map(d => d.period), datasets: [{ data: reversed.map(d => d.qty), backgroundColor: 'rgba(94,125,58,0.6)', borderRadius: 3 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
          scales: { y: { grid: { color: '#f0eadf' } }, x: { grid: { display: false } } } },
      });
    }
  } catch (e) { toast(e.message, 'error'); }
}

async function syncStock() {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = '동기화 중...';
  try {
    const r = await api('/api/stock/sync', { method: 'POST' });
    toast(`재고 ${r.synced}건 동기화 완료`);
    loadStock();
  } catch (e) { toast(e.message, 'error'); }
  btn.disabled = false;
  btn.textContent = '이지어드민 동기화';
}

// ── Sales ──
let salesPage = 1;
let salesChannels = [];
let salesGrouped = true;

async function initSalesFilters() {
  const now = new Date();
  const from = document.getElementById('sales-from');
  const to = document.getElementById('sales-to');
  if (from && !from.value) from.value = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0,10);
  if (to && !to.value) to.value = now.toISOString().slice(0,10);

  try {
    salesChannels = await api('/api/sales/channels');
    const sel = document.getElementById('sales-channel');
    if (sel && sel.options.length <= 1) {
      salesChannels.forEach(ch => { const o = document.createElement('option'); o.value = ch; o.textContent = ch; sel.appendChild(o); });
    }
  } catch(e) {}
}

async function loadSales(page = 1) {
  salesPage = page;
  await initSalesFilters();
  const from = document.getElementById('sales-from')?.value || '';
  const to = document.getElementById('sales-to')?.value || '';
  const channel = document.getElementById('sales-channel')?.value || '';
  const q = document.getElementById('sales-search')?.value || '';
  try {
    const groupParam = salesGrouped ? '&group=channel' : '';
    const d = await api(`/api/sales?date_from=${from}&date_to=${to}&channel=${encodeURIComponent(channel)}&q=${encodeURIComponent(q)}&page=${page}&size=50${groupParam}`);
    const thead = document.getElementById('sales-thead');
    const tbody = document.getElementById('sales-tbody');

    if (d.grouped) {
      thead.innerHTML = '<tr><th>채널</th><th class="text-right">건수</th><th class="text-right">공급가</th><th class="text-right">세액</th><th class="text-right">합계</th></tr>';
      tbody.innerHTML = d.items.length ? d.items.map(s => `
        <tr class="sales-ch-row" style="cursor:pointer" data-channel="${(s.channel||'').replace(/"/g,'&quot;')}" onclick="toggleSalesChannelProducts(this)">
          <td><strong><span class="sales-ch-arrow" style="display:inline-block;width:1.1em;color:var(--text-muted)">▸</span>${s.channel || '-'}</strong></td>
          <td class="text-right number">${s.item_count}건</td>
          <td class="text-right number">${fmt(s.total_supply)}</td>
          <td class="text-right number">${fmt(s.total_tax)}</td>
          <td class="text-right number"><strong>${fmt(s.total_amount)}</strong></td>
        </tr>
      `).join('') : '<tr><td colspan="5" class="text-center text-muted" style="padding:40px">데이터 없음</td></tr>';
    } else {
      thead.innerHTML = '<tr><th>매출일</th><th>채널</th><th>품목</th><th class="text-right">공급가</th><th class="text-right">세액</th><th class="text-right">합계</th><th>상태</th></tr>';
      tbody.innerHTML = d.items.length ? d.items.map(s => `
        <tr onclick="viewSale(${s.id})" style="cursor:pointer">
          <td>${s.sale_date}</td>
          <td>${s.channel || '-'}</td>
          <td>${s.recipient || '-'}</td>
          <td class="text-right number">${fmt(s.total_supply)}</td>
          <td class="text-right number">${fmt(s.total_tax)}</td>
          <td class="text-right number"><strong>${fmt(s.total_amount)}</strong></td>
          <td><span class="badge badge-${s.status === 'confirmed' ? 'success' : s.status === 'cancelled' ? 'danger' : 'warning'}">${
            s.status === 'confirmed' ? '확정' : s.status === 'cancelled' ? '취소' : '반품'
          }</span></td>
        </tr>
      `).join('') : '<tr><td colspan="7" class="text-center text-muted" style="padding:40px">매출 데이터가 없습니다. "매출 동기화" 버튼을 눌러주세요.</td></tr>';
    }
    document.getElementById('sales-info').textContent = `총 ${d.total}건`;
    const sumEl = document.getElementById('sales-sum');
    if (sumEl) sumEl.textContent = `합계 ₩${fmt(d.sum_amount)}`;
    renderPagination('sales-paging', d.total, 50, page, p => loadSales(p));

    const toggleBtn = document.getElementById('sales-group-toggle');
    if (toggleBtn) toggleBtn.textContent = salesGrouped ? '상세 보기' : '합산 보기';
  } catch (e) { toast(e.message, 'error'); }
}

// 전체 내역(합산) 탭에서 채널명 클릭 → 그 채널 상품별 매출을 아래로 펼침/접기
async function toggleSalesChannelProducts(rowEl) {
  const channel = rowEl.dataset.channel;
  const arrow = rowEl.querySelector('.sales-ch-arrow');
  // 이미 펼쳐져 있으면 접기
  if (rowEl.nextElementSibling && rowEl.nextElementSibling.classList.contains('sales-ch-detail')) {
    while (rowEl.nextElementSibling && rowEl.nextElementSibling.classList.contains('sales-ch-detail')) rowEl.nextElementSibling.remove();
    if (arrow) arrow.textContent = '▸';
    return;
  }
  const from = document.getElementById('sales-from')?.value || '';
  const to = document.getElementById('sales-to')?.value || '';
  if (arrow) arrow.textContent = '▾';
  try {
    const resp = await api(`/api/sales/summary?date_from=${from}&date_to=${to}&group_by=product&channel=${encodeURIComponent(channel)}`);
    const items = resp.items || [];
    const html = items.length ? items.map(p => `
      <tr class="sales-ch-detail" style="background:var(--bg)">
        <td style="padding-left:32px;font-size:12px" class="text-muted">${p.label || '-'}</td>
        <td class="text-right number text-muted" style="font-size:12px">${p.qty != null ? fmt(p.qty) : '-'}</td>
        <td class="text-right number text-muted" style="font-size:12px">${fmt(p.supply)}</td>
        <td class="text-right number text-muted" style="font-size:12px">${fmt(p.tax)}</td>
        <td class="text-right number" style="font-size:12px">₩${fmt(p.total)}</td>
      </tr>`).join('')
      : `<tr class="sales-ch-detail"><td colspan="5" class="text-muted" style="padding-left:32px;font-size:12px">상품 데이터 없음 (로켓배송 등 총액만 집계된 채널)</td></tr>`;
    rowEl.insertAdjacentHTML('afterend', html);
  } catch (e) {
    toast(e.message, 'error');
    if (arrow) arrow.textContent = '▸';
  }
}

async function viewSale(id) {
  try {
    const d = await api(`/api/sales/${id}`);
    const m = document.getElementById('modal');
    m.querySelector('.modal-header span').textContent = `매출 상세 #${id}`;
    m.querySelector('.modal-body').innerHTML = `
      <div class="form-row mb-2">
        <div><span class="text-muted">매출일</span><br><strong>${d.sale.sale_date}</strong></div>
        <div><span class="text-muted">채널</span><br><strong>${d.sale.channel || '-'}</strong></div>
      </div>
      <div class="form-row mb-2">
        <div><span class="text-muted">품목</span><br><strong>${d.sale.recipient || '-'}</strong></div>
        <div><span class="text-muted">합계</span><br><strong class="number">₩${fmt(d.sale.total_amount)}</strong></div>
      </div>
      <table class="mt-2">
        <thead><tr><th>품목</th><th class="text-right">수량</th><th class="text-right">단가</th><th class="text-right">합계</th></tr></thead>
        <tbody>${d.lines.map(l => `
          <tr><td>${l.product_name || '-'}</td><td class="text-right number">${fmt(l.qty)}</td>
          <td class="text-right number">${fmt(l.unit_price)}</td><td class="text-right number">${fmt(l.line_total)}</td></tr>
        `).join('')}</tbody>
      </table>
    `;
    m.querySelector('.modal-footer').innerHTML = '<button class="btn" onclick="closeModal()">닫기</button>';
    openModal();
  } catch (e) { toast(e.message, 'error'); }
}

async function syncSales() {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = '동기화 중... (최대 30일)';
  try {
    const r = await api('/api/sales/sync', { method: 'POST', body: { days: 30 } });
    toast(`매출 ${r.synced}건 동기화 완료 (최근 30일)`);
    loadSales(salesPage);
  } catch (e) { toast(e.message, 'error'); }
  btn.disabled = false;
  btn.textContent = '매출 동기화';
}

// ── Sales Summary Tab ──
function switchSalesTab(tab) {
  document.querySelectorAll('[data-sales-tab]').forEach(el => el.classList.toggle('active', el.dataset.salesTab === tab));
  document.getElementById('sales-tab-list').classList.toggle('hidden', tab !== 'list');
  document.getElementById('sales-tab-summary').classList.toggle('hidden', tab !== 'summary');
  if (tab === 'summary') loadSalesSummary();
}

async function loadSalesSummary() {
  const fromEl = document.getElementById('summary-from');
  const toEl = document.getElementById('summary-to');
  if (!fromEl.value) { const now = new Date(); const d = new Date(now.getFullYear(), now.getMonth(), 1); fromEl.value = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
  if (!toEl.value) { const now = new Date(); toEl.value = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`; }
  const groupBy = document.getElementById('summary-group')?.value || 'daily';
  const channel = document.getElementById('summary-channel')?.value || '';
  const searchQ = document.getElementById('summary-search')?.value?.trim() || '';

  const summaryChSel = document.getElementById('summary-channel');
  if (summaryChSel && summaryChSel.options.length <= 1 && salesChannels.length) {
    salesChannels.forEach(ch => { const o = document.createElement('option'); o.value = ch; o.textContent = ch; summaryChSel.appendChild(o); });
  }

  try {
    const resp = await api(`/api/sales/summary?date_from=${fromEl.value}&date_to=${toEl.value}&group_by=${groupBy}&channel=${encodeURIComponent(channel)}`);
    let data = resp.items || resp;
    const grandTotal = resp.grand_total || data.reduce((s, r) => s + (r.total || 0), 0);
    if (searchQ) data = data.filter(r => (r.label || '').toLowerCase().includes(searchQ.toLowerCase()));
    document.getElementById('summary-total').textContent = `합계 ₩${fmt(grandTotal)}`;

    const tbody = document.getElementById('summary-tbody');
    const rowTotal = data.reduce((s, r) => s + (r.total || 0), 0);
    const drill = groupBy === 'channel';  // 채널별일 때만 클릭→상품별 펼침
    tbody.innerHTML = data.length ? data.map(r => {
      const chAttr = drill ? ` class="ch-row" style="cursor:pointer" data-channel="${(r.label||'').replace(/"/g,'&quot;')}" onclick="toggleChannelProducts(this)"` : '';
      const arrow = drill ? '<span class="ch-arrow" style="display:inline-block;width:1.1em;color:var(--text-muted)">▸</span>' : '';
      return `<tr${chAttr}>
        <td><strong>${arrow}${r.label || '-'}</strong></td>
        <td class="text-right number">${r.qty != null ? fmt(r.qty) : (r.cnt != null ? fmt(r.cnt) + '건' : '-')}</td>
        <td class="text-right number">${fmt(r.supply)}</td>
        <td class="text-right number">${fmt(r.tax)}</td>
        <td class="text-right number"><strong>₩${fmt(r.total)}</strong></td>
      </tr>`;
    }).join('') + `<tr style="background:var(--bg);font-weight:700">
      <td>합계</td><td></td>
      <td class="text-right number">${fmt(data.reduce((s,r) => s + (r.supply||0), 0))}</td>
      <td class="text-right number">${fmt(data.reduce((s,r) => s + (r.tax||0), 0))}</td>
      <td class="text-right number">₩${fmt(rowTotal)}</td>
    </tr>` : '<tr><td colspan="5" class="text-center text-muted" style="padding:40px">데이터 없음</td></tr>';

    renderSalesSummaryChart(data, groupBy);
  } catch (e) { toast(e.message, 'error'); }
}

// 채널 행 클릭 → 해당 채널의 상품별 매출을 아래로 펼침/접기
async function toggleChannelProducts(rowEl) {
  const channel = rowEl.dataset.channel;
  const arrow = rowEl.querySelector('.ch-arrow');
  // 이미 펼쳐져 있으면 접기
  if (rowEl.nextElementSibling && rowEl.nextElementSibling.classList.contains('ch-detail')) {
    while (rowEl.nextElementSibling && rowEl.nextElementSibling.classList.contains('ch-detail')) rowEl.nextElementSibling.remove();
    if (arrow) arrow.textContent = '▸';
    return;
  }
  const from = document.getElementById('summary-from').value;
  const to = document.getElementById('summary-to').value;
  if (arrow) arrow.textContent = '▾';
  try {
    const resp = await api(`/api/sales/summary?date_from=${from}&date_to=${to}&group_by=product&channel=${encodeURIComponent(channel)}`);
    const items = resp.items || [];
    const html = items.length ? items.map(p => `
      <tr class="ch-detail" style="background:var(--bg)">
        <td style="padding-left:32px;font-size:12px" class="text-muted">${p.label || '-'}</td>
        <td class="text-right number text-muted" style="font-size:12px">${p.qty != null ? fmt(p.qty) : '-'}</td>
        <td class="text-right number text-muted" style="font-size:12px">${fmt(p.supply)}</td>
        <td class="text-right number text-muted" style="font-size:12px">${fmt(p.tax)}</td>
        <td class="text-right number" style="font-size:12px">₩${fmt(p.total)}</td>
      </tr>`).join('')
      : `<tr class="ch-detail"><td colspan="5" class="text-muted" style="padding-left:32px;font-size:12px">상품 데이터 없음</td></tr>`;
    rowEl.insertAdjacentHTML('afterend', html);
  } catch (e) {
    toast(e.message, 'error');
    if (arrow) arrow.textContent = '▸';
  }
}

function renderSalesSummaryChart(data, groupBy) {
  const ctx = document.getElementById('chart-sales-summary');
  if (chartSalesSummary) chartSalesSummary.destroy();
  if (!data.length) return;
  const isBar = groupBy === 'channel' || groupBy === 'product';
  chartSalesSummary = new Chart(ctx, {
    type: isBar ? 'bar' : 'line',
    data: {
      labels: data.map(d => {
        const l = d.label || '-';
        return l.length > 15 ? l.slice(0, 15) + '…' : l;
      }),
      datasets: [{
        label: '매출',
        data: data.map(d => d.total),
        backgroundColor: isBar ? CHART_COLORS.slice(0, data.length) : 'rgba(178,88,57,0.08)',
        borderColor: '#b25839',
        borderWidth: isBar ? 0 : 2,
        fill: !isBar,
        tension: 0.3,
        borderRadius: isBar ? 4 : 0,
        pointRadius: isBar ? 0 : 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => '₩' + fmt(ctx.raw) } },
      },
      scales: {
        y: { ticks: { callback: v => v >= 1e6 ? (v/1e6).toFixed(0) + 'M' : fmt(v) }, grid: { color: '#f0eadf' } },
        x: { grid: { display: false }, ticks: { maxRotation: 45 } },
      },
    },
  });
}

// ── Purchase Orders ──
let ordersPage = 1;

function initOrderFilters() {
  const now = new Date();
  const from = document.getElementById('order-from');
  const to = document.getElementById('order-to');
  if (from && !from.value) from.value = new Date(now.getFullYear(), now.getMonth() - 3, 1).toISOString().slice(0,10);
  if (to && !to.value) to.value = now.toISOString().slice(0,10);
}

// 발주 정렬 상태 (기본: 발주일 최신순). 같은 컬럼 재클릭 = 방향 토글.
let _orderSort = { col: 'date', dir: 'desc' };
function sortOrders(col) {
  if (_orderSort.col === col) _orderSort.dir = _orderSort.dir === 'asc' ? 'desc' : 'asc';
  else { _orderSort.col = col; _orderSort.dir = (col === 'pono' || col === 'supplier' || col === 'status') ? 'asc' : 'desc'; }
  loadOrders(1);
}

async function loadOrders(page = 1) {
  ordersPage = page;
  initOrderFilters();
  const status = document.getElementById('order-status')?.value || '';
  const q = document.getElementById('order-search')?.value || '';
  const from = document.getElementById('order-from')?.value || '';
  const to = document.getElementById('order-to')?.value || '';
  try {
    const sort = `${_orderSort.col}_${_orderSort.dir}`;
    // 헤더 정렬 화살표 갱신
    document.querySelectorAll('.sort-ar').forEach(el => {
      el.textContent = (el.dataset.k === _orderSort.col) ? (_orderSort.dir === 'asc' ? '▲' : '▼') : '';
    });
    const d = await api(`/api/purchase-orders?status=${status}&q=${encodeURIComponent(q)}&date_from=${from}&date_to=${to}&sort=${sort}&page=${page}&size=30`);
    const tbody = document.getElementById('orders-tbody');
    const statusMap = { draft: '작성중', confirmed: '확정', partial: '부분입고', completed: '완료', cancelled: '취소' };
    const badgeMap = { draft: 'default', confirmed: 'info', partial: 'warning', completed: 'success', cancelled: 'danger' };
    tbody.innerHTML = d.items.length ? d.items.map(o => {
      const items = o.items_summary || '';
      const shortItems = items.length > 50 ? items.slice(0, 50) + '…' : items;
      return `
      <tr onclick="viewOrder(${o.id})" style="cursor:pointer">
        <td><strong>${o.po_number}</strong></td>
        <td>${o.po_date}</td>
        <td>${o.supplier_name || '-'}</td>
        <td class="text-muted" style="font-size:11.5px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${items}">${shortItems || '-'}</td>
        <td>${o.delivery_date || '-'}</td>
        <td class="text-right number">${fmt(o.total_qty || 0)}</td>
        <td class="text-right number">${fmt(Math.round(o.total_amount * 1.1))}</td>
        <td><span class="badge badge-${badgeMap[o.status]}">${statusMap[o.status]}</span></td>
      </tr>`;
    }).join('') : '<tr><td colspan="8" class="text-center text-muted" style="padding:40px">발주 데이터가 없습니다</td></tr>';
    document.getElementById('orders-info').textContent = `총 ${d.total}건`;
    const sumEl = document.getElementById('orders-sum');
    if (sumEl) sumEl.textContent = `합계 ₩${fmt(Math.round(d.sum_amount * 1.1))} (VAT포함)`;
    renderPagination('orders-paging', d.total, 30, page, p => loadOrders(p));
  } catch (e) { toast(e.message, 'error'); }
}

async function viewOrder(id) {
  try {
    const d = await api(`/api/purchase-orders/${id}`);
    const statusMap = { draft: '작성중', confirmed: '확정', partial: '부분입고', completed: '완료', cancelled: '취소' };
    const poSupply = d.lines.reduce((s, l) => s + (l.amount || 0), 0);
    const poTax = Math.round(poSupply * 0.1);
    const poTotal = poSupply + poTax;
    const m = document.getElementById('modal');
    m.querySelector('.modal-header span').textContent = `발주서 ${d.po.po_number}`;
    m.querySelector('.modal-body').innerHTML = `
      <div class="form-row mb-2">
        <div><span class="text-muted">발주일</span><br><strong>${d.po.po_date}</strong></div>
        <div><span class="text-muted">납품예정일</span><br><strong>${d.po.delivery_date || '-'}</strong></div>
      </div>
      <div class="form-row mb-2">
        <div><span class="text-muted">거래처</span><br><strong>${d.po.supplier_name || '-'}</strong></div>
        <div><span class="text-muted">상태</span><br><strong>${statusMap[d.po.status]}</strong></div>
      </div>
      <table class="mt-2">
        <thead><tr><th>품목</th><th class="text-right">발주량</th><th class="text-right">입고량</th><th class="text-right">단가</th><th class="text-right">공급가액</th><th class="text-right">부가세</th></tr></thead>
        <tbody>${d.lines.map(l => `
          <tr><td>${l.product_name || l.product_code}</td>
          <td class="text-right number">${fmt(l.qty_ordered)}</td>
          <td class="text-right number">${fmt(l.qty_received)}</td>
          <td class="text-right number">${fmt(l.unit_price)}</td>
          <td class="text-right number">${fmt(l.amount)}</td>
          <td class="text-right number">${fmt(Math.round((l.amount || 0) * 0.1))}</td></tr>
        `).join('')}</tbody>
      </table>
      <div class="text-right mt-2" style="font-size:13px;line-height:1.9">공급가액 ₩${fmt(poSupply)}<br>부가세(10%) ₩${fmt(poTax)}<br><span style="font-weight:700;font-size:15px">합계(VAT 포함) <span style="color:var(--accent)">₩${fmt(poTotal)}</span></span></div>
      ${d.po.memo ? `<div class="mt-2"><span class="text-muted">메모</span><br>${d.po.memo}</div>` : ''}
    `;
    m.querySelector('.modal-footer').innerHTML = `
      <button class="btn" onclick="closeModal()">닫기</button>
      <button class="btn" onclick="editOrder(${id})">✏️ 수정</button>
      <button class="btn" onclick="copyPO(${id})">복사</button>
      <button class="btn" onclick="downloadPOPdf(${id})">📄 PDF</button>
      <button class="btn" onclick="emailPO(${id})">이메일 발송</button>
      ${d.po.status === 'draft' ? `<button class="btn btn-primary" onclick="confirmPO(${id})">발주 확정</button>` : ''}
    `;
    openModal();
  } catch (e) { toast(e.message, 'error'); }
}

async function confirmPO(id) {
  try {
    await api(`/api/purchase-orders/${id}/status`, { method: 'PUT', body: { status: 'confirmed' } });
    toast('발주가 확정되었습니다');
    await viewOrder(id);   // 모달 유지 — 확정 상태로 갱신해 다시 표시 (X로만 닫힘)
    loadOrders(ordersPage);
  } catch (e) { toast(e.message, 'error'); }
}

async function copyPO(id) {
  try {
    const r = await api(`/api/purchase-orders/${id}/copy`, { method: 'POST' });
    toast(`발주서 복사 완료: ${r.po_number}`);
    await viewOrder(r.id);   // 모달 유지 — 복사된 새 발주서로 전환 (X로만 닫힘)
    loadOrders();
  } catch (e) { toast(e.message, 'error'); }
}

function downloadPOPdf(id) {
  // 새 탭에서 PDF 뷰어로 열기 (HTTP 사이트의 blob/attachment 다운로드를 크롬이 차단하는 문제 회피).
  // 뷰어에서 저장/인쇄 가능. 강제 저장이 필요하면 ?dl=1.
  window.open(`/api/purchase-orders/${id}/pdf`, '_blank');
}

async function emailPO(id) {
  try {
    const d = await api(`/api/purchase-orders/${id}`);
    const sid = d.po.supplier_id;
    let contacts = [];
    if (sid) { try { contacts = await api(`/api/partners/${sid}/contacts`); } catch (e) {} }
    window._poEmailCtx = { poId: id, supplierId: sid };
    const m = document.getElementById('modal');
    const toContacts = contacts.filter(c => c.contact_type === 'to');
    const ccContacts = contacts.filter(c => c.contact_type === 'cc');

    const esc = s => String(s || '').replace(/'/g, "\\'");
    const row = c => `
      <label style="display:flex;align-items:center;gap:8px;padding:4px 0">
        <input type="checkbox" class="email-${c.contact_type}" value="${c.email}" checked />
        <span style="min-width:82px">${c.name}</span>
        <span class="text-muted" style="font-size:12px;flex:1">${c.email}</span>
        <span onclick="editPOContact(${c.id},'${esc(c.name)}','${esc(c.email)}','${c.contact_type}')" style="cursor:pointer;font-size:13px" title="수정">✏️</span>
        <span onclick="delPOContact(${c.id},'${esc(c.name)}')" style="cursor:pointer;color:#ccc;font-weight:700;font-size:15px" title="삭제">✕</span>
      </label>`;

    m.querySelector('.modal-header span').textContent = `발주서 이메일 발송 — ${d.po.po_number}`;
    m.querySelector('.modal-body').innerHTML = `
      <div class="form-group">
        <label>수신 (To)</label>
        ${toContacts.map(row).join('') || '<span class="text-muted" style="font-size:13px">없음</span>'}
      </div>
      <div class="form-group">
        <label>참조 (Cc)</label>
        ${ccContacts.map(row).join('') || '<span class="text-muted" style="font-size:13px">없음</span>'}
      </div>
      ${sid ? `
      <div class="form-group" style="border-top:1px solid var(--line,#eee);padding-top:12px">
        <label style="font-size:12px;color:var(--ink-3,#999)">+ 연락처 추가 <span style="font-weight:400">(저장돼서 다음 발주서에도 떠요)</span></label>
        <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:6px">
          <input type="text" id="new-contact-name" placeholder="이름" style="width:88px" />
          <input type="email" id="new-contact-email" placeholder="이메일" style="flex:1;min-width:150px" />
          <select id="new-contact-type" style="padding:6px;border:1px solid var(--line,#ddd);border-radius:6px">
            <option value="to">수신</option><option value="cc">참조</option>
          </select>
          <button class="btn btn-sm" onclick="addPOContact()">추가</button>
        </div>
      </div>` : ''}
      <div class="form-group">
        <label style="font-size:12px;color:var(--ink-3,#999)">임시 수신 <span style="font-weight:400">(이번 발송만, 저장 안 함)</span></label>
        <input type="email" id="email-to-custom" placeholder="직접 입력..." />
      </div>
      <div class="form-group">
        <label>발신</label>
        <div class="text-muted" style="font-size:13px">info@becorelab.kr</div>
      </div>
    `;
    m.querySelector('.modal-footer').innerHTML = `
      <button class="btn" onclick="closeModal();viewOrder(${id})">취소</button>
      <button class="btn btn-primary" onclick="sendPOEmail(${id})">발송</button>`;
    openModal();
  } catch (e) { toast(e.message, 'error'); }
}

async function addPOContact() {
  const ctx = window._poEmailCtx; if (!ctx?.supplierId) return;
  const name = document.getElementById('new-contact-name').value.trim();
  const email = document.getElementById('new-contact-email').value.trim();
  const type = document.getElementById('new-contact-type').value;
  if (!name || !email) return toast('이름과 이메일을 입력하세요', 'error');
  try {
    await api(`/api/partners/${ctx.supplierId}/contacts`, { method: 'POST', body: { name, email, contact_type: type } });
    toast('연락처 추가됨'); emailPO(ctx.poId);
  } catch (e) { toast(e.message, 'error'); }
}

async function editPOContact(cid, name, email, type) {
  const ctx = window._poEmailCtx; if (!ctx?.supplierId) return;
  const nName = prompt('이름', name); if (nName === null) return;
  const nEmail = prompt('이메일', email); if (nEmail === null) return;
  let nType = prompt('구분 — to(수신) / cc(참조)', type); if (nType === null) return;
  nType = nType.trim().toLowerCase() === 'cc' ? 'cc' : 'to';
  try {
    await api(`/api/partners/${ctx.supplierId}/contacts/${cid}`, { method: 'PUT', body: { name: nName.trim(), email: nEmail.trim(), contact_type: nType } });
    toast('연락처 수정됨'); emailPO(ctx.poId);
  } catch (e) { toast(e.message, 'error'); }
}

async function delPOContact(cid, name) {
  const ctx = window._poEmailCtx; if (!ctx?.supplierId) return;
  if (!confirm(`'${name}' 연락처를 삭제할까요?`)) return;
  try {
    await api(`/api/partners/${ctx.supplierId}/contacts/${cid}`, { method: 'DELETE' });
    toast('연락처 삭제됨'); emailPO(ctx.poId);
  } catch (e) { toast(e.message, 'error'); }
}

async function sendPOEmail(id) {
  const checked = document.querySelectorAll('.email-to:checked');
  const custom = document.getElementById('email-to-custom')?.value?.trim();
  const toList = [...checked].map(c => c.value);
  if (custom) toList.push(custom);
  if (!toList.length) return toast('수신 이메일을 선택하세요', 'error');
  const ccList = [...document.querySelectorAll('.email-cc:checked')].map(c => c.value);

  try {
    await api(`/api/purchase-orders/${id}/email`, { method: 'POST', body: { to: toList, cc: ccList } });
    toast(`발주서 발송 완료 (수신 ${toList.length}명${ccList.length ? ' · 참조 ' + ccList.length : ''})`);
    closeModal();
  } catch (e) { toast(e.message, 'error'); }
}

let _orderDebounceTimer;
function debounceLoadOrders() {
  clearTimeout(_orderDebounceTimer);
  _orderDebounceTimer = setTimeout(() => loadOrders(), 300);
}

async function editOrder(id) { return newOrder(id); }

async function newOrder(poId = null) {
  const suppliers = await api('/api/partners?type=supplier&size=200');
  const products = await api('/api/products?size=200');
  window._allSuppliers = suppliers.items;
  window._poProducts = products.items;
  let po = null, lines = [];
  if (poId) {
    const d = await api(`/api/purchase-orders/${poId}`);
    po = d.po; lines = d.lines || [];
  }
  const m = document.getElementById('modal');
  m.querySelector('.modal-header span').textContent = poId ? '발주서 수정' : '발주서 작성';
  m.querySelector('.modal-body').innerHTML = `
    <div class="form-row">
      <div class="form-group"><label>발주일</label><input type="date" id="m-podate" value="${po ? po.po_date : new Date().toISOString().slice(0,10)}" /></div>
      <div class="form-group"><label>납품예정일</label><input type="date" id="m-podelivery" value="${po && po.delivery_date ? po.delivery_date : ''}" /></div>
    </div>
    <div class="form-group"><label>공급처</label>
      <div class="autocomplete-wrap">
        <input type="text" id="m-posupplier-search" placeholder="공급처명 검색..." autocomplete="off" value="${po && po.supplier_name ? po.supplier_name.replace(/"/g,'&quot;') : ''}" />
        <input type="hidden" id="m-posupplier" value="${po ? po.supplier_id : ''}" />
        <div class="autocomplete-list" id="supplier-autocomplete"></div>
      </div>
    </div>
    <div class="form-group"><label>메모</label><textarea id="m-pomemo" rows="2">${po && po.memo ? po.memo : ''}</textarea></div>
    <hr style="border-color:var(--line); margin:16px 0" />
    <div class="flex justify-between items-center mb-2">
      <strong>발주 품목</strong>
      <button class="btn btn-sm" onclick="addPOLine()">+ 품목 추가</button>
    </div>
    <div id="po-lines"></div>
    <datalist id="po-products-datalist">${(window._poProducts || []).map(p => `<option value="${(p.name + ' (' + p.product_code + ')').replace(/"/g, '&quot;')}"></option>`).join('')}</datalist>
    <div class="text-right mt-2" style="font-size:13px;line-height:1.9">공급가액 <span id="po-supply">₩0</span><br>부가세(10%) <span id="po-tax">₩0</span><br><span style="font-weight:700;font-size:15px">합계(VAT 포함) <span id="po-total" style="color:var(--accent)">₩0</span></span></div>
  `;
  m.querySelector('.modal').classList.add('modal-wide');
  initSupplierAutocomplete();
  m.querySelector('.modal-footer').innerHTML = `
    <button class="btn" onclick="closeModal()">취소</button>
    <button class="btn btn-primary" onclick="savePO(${poId || 'null'})">${poId ? '수정 저장' : '발주 등록'}</button>`;
  openModal();
  if (lines.length) lines.forEach(l => addPOLine(l));
  else addPOLine();
  recalcPOTotal();
}

function initSupplierAutocomplete() {
  const input = document.getElementById('m-posupplier-search');
  const hidden = document.getElementById('m-posupplier');
  const list = document.getElementById('supplier-autocomplete');
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    hidden.value = '';
    if (!q) { list.innerHTML = ''; list.style.display = 'none'; return; }
    const matches = (window._allSuppliers || []).filter(s => s.name.toLowerCase().includes(q)).slice(0, 8);
    if (!matches.length) { list.innerHTML = '<div class="autocomplete-item text-muted">결과 없음</div>'; list.style.display = 'block'; return; }
    list.innerHTML = matches.map(s => `<div class="autocomplete-item" data-id="${s.id}">${s.name}</div>`).join('');
    list.style.display = 'block';
    list.querySelectorAll('.autocomplete-item[data-id]').forEach(el => {
      el.addEventListener('click', () => {
        input.value = el.textContent;
        hidden.value = el.dataset.id;
        list.style.display = 'none';
      });
    });
  });
  input.addEventListener('blur', () => setTimeout(() => { list.style.display = 'none'; }, 200));
}

function addPOLine(line = null) {
  const container = document.getElementById('po-lines');
  const div = document.createElement('div');
  div.className = 'form-row mb-2';
  div.style.alignItems = 'end';
  let displayName = '';
  if (line) {
    const prod = (window._poProducts || []).find(p => p.id === line.product_id);
    displayName = prod ? `${prod.name} (${prod.product_code})` : (line.product_name || '');
  }
  div.innerHTML = `
    <div class="form-group" style="flex:2.4"><label>품목 <span class="text-muted" style="font-weight:400">· 타이핑 검색 (새 품목명 직접 입력 가능)</span></label>
      <input type="text" class="po-product-search" list="po-products-datalist" placeholder="품목명·코드 입력..." autocomplete="off" value="${displayName.replace(/"/g, '&quot;')}" />
      <input type="hidden" class="po-product-id" value="${line ? line.product_id : ''}" /></div>
    <div class="form-group" style="flex:0.8"><label>수량</label><input type="number" class="po-qty" value="${line ? line.qty_ordered : 1}" min="1" /></div>
    <div class="form-group" style="flex:1"><label>단가</label><input type="number" class="po-price" value="${line ? line.unit_price : 0}" /></div>
    <div class="form-group" style="flex:1.2"><label>금액</label><input type="text" class="po-amount" value="0" readonly style="background:var(--line-2);font-weight:600" /></div>
    <button class="btn btn-sm btn-danger" onclick="this.parentElement.remove();recalcPOTotal()" style="margin-bottom:16px">X</button>
  `;
  const search = div.querySelector('.po-product-search');
  const hidden = div.querySelector('.po-product-id');
  search.addEventListener('input', () => {
    const prod = (window._poProducts || []).find(p => `${p.name} (${p.product_code})` === search.value);
    if (prod) { hidden.value = prod.id; div.querySelector('.po-price').value = prod.purchase_price || 0; }
    else { hidden.value = ''; }
    recalcLine(div); recalcPOTotal();
  });
  div.querySelector('.po-qty').addEventListener('input', () => { recalcLine(div); recalcPOTotal(); });
  div.querySelector('.po-price').addEventListener('input', () => { recalcLine(div); recalcPOTotal(); });
  container.appendChild(div);
  recalcLine(div);
}

function recalcLine(div) {
  const qty = Number(div.querySelector('.po-qty').value) || 0;
  const price = Number(div.querySelector('.po-price').value) || 0;
  div.querySelector('.po-amount').value = fmt(qty * price);
}

function recalcPOTotal() {
  let supply = 0;
  document.querySelectorAll('#po-lines > div').forEach(div => {
    const qty = Number(div.querySelector('.po-qty').value) || 0;
    const price = Number(div.querySelector('.po-price').value) || 0;
    supply += qty * price;
  });
  const tax = Math.round(supply * 0.1);
  const sEl = document.getElementById('po-supply');
  const tEl = document.getElementById('po-tax');
  const el = document.getElementById('po-total');
  if (sEl) sEl.textContent = '₩' + fmt(supply);
  if (tEl) tEl.textContent = '₩' + fmt(tax);
  if (el) el.textContent = '₩' + fmt(supply + tax);
}

async function savePO(poId = null) {
  const lines = [];
  document.querySelectorAll('#po-lines > div').forEach(row => {
    const productId = row.querySelector('.po-product-id').value;
    const productName = row.querySelector('.po-product-search').value;
    const qty = Number(row.querySelector('.po-qty').value);
    const price = Number(row.querySelector('.po-price').value);
    // 등록 품목(product_id) 또는 자유 입력 품목명(product_name) 둘 중 하나만 있으면 발주 라인에 포함
    // → "바이올렛 머스크 9차"처럼 매번 품목 등록 없이 발주서에 쓰는 대로 저장됨
    if ((productId || productName.trim()) && qty > 0) lines.push({ product_id: productId ? Number(productId) : null, product_name: productName.trim(), qty_ordered: qty, unit_price: price });
  });
  if (!lines.length) return toast('품목을 추가해주세요', 'error');
  const supplierId = document.getElementById('m-posupplier').value;
  if (!supplierId) return toast('공급처를 선택해주세요', 'error');

  const body = {
    po_date: document.getElementById('m-podate').value,
    delivery_date: document.getElementById('m-podelivery').value,
    supplier_id: Number(supplierId),
    memo: document.getElementById('m-pomemo').value,
    lines,
  };
  try {
    if (poId) {
      await api(`/api/purchase-orders/${poId}`, { method: 'PUT', body });
      toast('발주서 수정 완료');
      await viewOrder(poId);   // 모달 유지 — 저장 후 상세로 갱신 (X로만 닫힘)
    } else {
      const r = await api('/api/purchase-orders', { method: 'POST', body });
      toast(`발주서 ${r.po_number} 등록 완료`);
      await viewOrder(r.id);   // 모달 유지 — 새 발주서 상세로 (X로만 닫힘)
    }
    loadOrders();
  } catch (e) { toast(e.message, 'error'); }
}

// ── Modal ──
function openModal() { document.getElementById('modal').classList.add('show'); }
function closeModal() {
  const ov = document.getElementById('modal');
  ov.classList.remove('show');
  const inner = ov.querySelector('.modal');
  if (inner) inner.classList.remove('modal-wide');
}

// ── Pagination ──
function renderPagination(containerId, total, size, current, callback) {
  const pages = Math.ceil(total / size);
  const el = document.getElementById(containerId);
  if (!el || pages <= 1) { if (el) el.innerHTML = ''; return; }
  let html = '';
  if (current > 1) html += `<button class="btn btn-sm" onclick="void(0)" data-p="${current-1}">&lt;</button> `;
  for (let i = 1; i <= pages; i++) {
    if (i === current) html += `<button class="btn btn-sm btn-primary">${i}</button> `;
    else if (Math.abs(i - current) < 3 || i === 1 || i === pages)
      html += `<button class="btn btn-sm" onclick="void(0)" data-p="${i}">${i}</button> `;
    else if (Math.abs(i - current) === 3) html += '... ';
  }
  if (current < pages) html += `<button class="btn btn-sm" onclick="void(0)" data-p="${current+1}">&gt;</button>`;
  el.innerHTML = html;
  el.querySelectorAll('[data-p]').forEach(btn => {
    btn.addEventListener('click', () => callback(Number(btn.dataset.p)));
  });
}

// ── Calendar (일정 관리) ──
let calYear, calMonth;          // 현재 보고 있는 연/월 (calMonth: 0~11)
let calEvents = [];
const EVENT_TYPES = [
  { key: 'leave', label: '연차' },
  { key: 'meeting', label: '미팅' },
  { key: 'restock', label: '재입고' },
  { key: 'etc', label: '기타' },
];

function calIso(y, m, d) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

async function loadCalendar() {
  if (calYear === undefined) {
    const now = new Date();
    calYear = now.getFullYear();
    calMonth = now.getMonth();
  }
  document.getElementById('cal-title').textContent = `${calYear}년 ${calMonth + 1}월`;
  // 이번 달 + 앞뒤 걸치는 날짜까지 넉넉히 조회
  const start = calIso(calYear, calMonth, 1);
  const lastDay = new Date(calYear, calMonth + 1, 0).getDate();
  const end = calIso(calYear, calMonth, lastDay);
  try {
    calEvents = await api(`/api/events?start=${start}&end=${end}`);
  } catch (e) { calEvents = []; toast(e.message, 'error'); }
  renderCalendar();
}

function renderCalendar() {
  const grid = document.getElementById('cal-grid');
  const first = new Date(calYear, calMonth, 1);
  const startDow = first.getDay();              // 0(일)~6(토)
  const lastDay = new Date(calYear, calMonth + 1, 0).getDate();
  const prevLast = new Date(calYear, calMonth, 0).getDate();
  const todayIso = (() => { const n = new Date(); return calIso(n.getFullYear(), n.getMonth(), n.getDate()); })();

  // 해당 날짜의 이벤트 묶기
  const byDate = {};
  calEvents.forEach(ev => {
    // 기간 이벤트는 start~end 모든 날에 표시
    const s = ev.start_date, e = ev.end_date || ev.start_date;
    let d = new Date(s + 'T00:00:00');
    const last = new Date(e + 'T00:00:00');
    while (d <= last) {
      const key = calIso(d.getFullYear(), d.getMonth(), d.getDate());
      (byDate[key] = byDate[key] || []).push(ev);
      d.setDate(d.getDate() + 1);
    }
  });

  // 공휴일 날짜 Set (날짜 숫자 빨강 처리용)
  const holidayDates = new Set(
    calEvents.filter(ev => ev.event_type === 'holiday').map(ev => ev.start_date)
  );

  let cells = [];
  // 앞쪽 지난달
  for (let i = startDow - 1; i >= 0; i--) cells.push({ d: prevLast - i, other: true, ym: [calYear, calMonth - 1] });
  // 이번달
  for (let d = 1; d <= lastDay; d++) cells.push({ d, other: false, ym: [calYear, calMonth] });
  // 뒤쪽 다음달 (7의 배수 채우기)
  let nd = 1;
  while (cells.length % 7 !== 0) cells.push({ d: nd++, other: true, ym: [calYear, calMonth + 1] });

  grid.innerHTML = cells.map(c => {
    const ny = c.ym[0], nm = c.ym[1];
    const realDate = new Date(ny, nm, c.d);
    const iso = calIso(realDate.getFullYear(), realDate.getMonth(), realDate.getDate());
    const dow = realDate.getDay();
    const evs = byDate[iso] || [];
    const shown = evs.slice(0, 3);
    const more = evs.length - shown.length;
    // 공휴일이면 날짜 숫자 빨강 (일요일과 같은 색, today는 accent 배경이라 구분됨)
    const isHoliday = holidayDates.has(iso);
    const dayClass = (dow === 0 || isHoliday) ? 'sun' : dow === 6 ? 'sat' : '';
    return `<div class="cal-cell ${c.other ? 'other-month' : ''} ${iso === todayIso ? 'today' : ''}" onclick="editEvent(0,'${iso}')">
      <div class="cal-daynum ${dayClass}">${c.d}</div>
      ${shown.map(ev => `<div class="cal-event type-${ev.event_type}" onclick="event.stopPropagation();${ev.event_type === 'holiday' ? `toast('공휴일입니다 🔴','warning')` : ev.readonly ? `toast('발주 입고 일정이에요 (발주 메뉴에서 관리)','warning')` : `editEvent(${ev.id})`}" title="${(ev.title || '').replace(/"/g, '')}">${ev.title}</div>`).join('')}
      ${more > 0 ? `<div class="cal-more">+${more}개</div>` : ''}
    </div>`;
  }).join('');
}

function calMove(delta) {
  calMonth += delta;
  if (calMonth < 0) { calMonth = 11; calYear--; }
  if (calMonth > 11) { calMonth = 0; calYear++; }
  loadCalendar();
}
function calToday() {
  const n = new Date(); calYear = n.getFullYear(); calMonth = n.getMonth();
  loadCalendar();
}

function editEvent(id, presetDate) {
  const ev = id ? calEvents.find(x => x.id === id) : null;
  const m = document.getElementById('modal');
  m.querySelector('.modal-header span').textContent = ev ? '일정 수정' : '일정 추가';
  m.querySelector('.modal-body').innerHTML = `
    <div class="form-group"><label>제목 <span class="required">*</span></label>
      <input id="ev-title" value="${ev ? (ev.title || '').replace(/"/g, '&quot;') : ''}" placeholder="일정 제목을 입력하세요" /></div>
    <div class="form-group"><label>종류</label>
      <select id="ev-type">${EVENT_TYPES.filter(t => t.key !== 'restock').map(t => `<option value="${t.key}">${t.label}</option>`).join('')}</select></div>
    <div style="display:flex;gap:12px">
      <div class="form-group" style="flex:1"><label>시작일 <span class="required">*</span></label>
        <input type="date" id="ev-start" value="${ev ? ev.start_date : (presetDate || '')}" /></div>
      <div class="form-group" style="flex:1"><label>종료일 <span class="text-muted">(선택)</span></label>
        <input type="date" id="ev-end" value="${ev && ev.end_date ? ev.end_date : ''}" /></div>
    </div>
    <div class="form-group"><label>메모</label>
      <textarea id="ev-memo" rows="2" placeholder="(선택)">${ev && ev.memo ? ev.memo : ''}</textarea></div>
  `;
  if (ev) m.querySelector('#ev-type').value = ev.event_type === 'restock' ? 'etc' : ev.event_type;
  m.querySelector('.modal-footer').innerHTML = `
    ${ev ? `<button class="btn" style="color:var(--red);margin-right:auto" onclick="deleteEvent(${id})">삭제</button>` : ''}
    <button class="btn" onclick="closeModal()">취소</button>
    <button class="btn btn-primary" onclick="saveEvent(${id})">저장</button>`;
  openModal();
}

async function saveEvent(id) {
  const title = document.getElementById('ev-title').value.trim();
  const start_date = document.getElementById('ev-start').value;
  if (!title) return toast('제목을 입력하세요', 'error');
  if (!start_date) return toast('시작일을 선택하세요', 'error');
  const body = {
    title,
    event_type: document.getElementById('ev-type').value,
    start_date,
    end_date: document.getElementById('ev-end').value || null,
    memo: document.getElementById('ev-memo').value.trim() || null,
  };
  if (!id && currentUser) body.created_by = currentUser.id;
  try {
    if (id) await api(`/api/events/${id}`, { method: 'PUT', body });
    else await api('/api/events', { method: 'POST', body });
    toast(id ? '일정이 수정되었어요' : '일정이 추가되었어요');
    closeModal();
    loadCalendar();
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteEvent(id) {
  if (!confirm('이 일정을 삭제할까요?')) return;
  try {
    await api(`/api/events/${id}`, { method: 'DELETE' });
    toast('일정이 삭제되었어요');
    closeModal();
    loadCalendar();
  } catch (e) { toast(e.message, 'error'); }
}

// ── 채널별 가격관리 (파일럿) ──
let pricingData = { channels: [], items: [] };

function calcPricing(sale, cost, consumer, pack, ch) {
  if (sale == null || sale === '') return null;
  sale = Number(sale);
  const vat = ch.vat_rate != null ? ch.vat_rate : 0.1;
  const comm = ch.commission_rate != null ? ch.commission_rate : 0;
  const supply = sale / (1 + vat) * (1 - comm);
  const discount = consumer ? (1 - sale / consumer) : null;
  const totalProfit = supply - (cost || 0);
  const margin = supply ? totalProfit / supply : null;
  const unitProfit = totalProfit / (pack || 1);
  return { supply, discount, margin, unitProfit };
}

function marginClass(m) {
  if (m == null) return '';
  if (m >= 0.40) return 'mg-good';
  if (m >= 0.20) return 'mg-mid';
  return 'mg-low';
}

function subHtml(r) {
  if (!r) return '<span class="text-muted">-</span>';
  const d = r.discount != null ? Math.round(r.discount * 100) + '%' : '-';
  const m = r.margin != null ? Math.round(r.margin * 100) + '%' : '-';
  return `<span class="${marginClass(r.margin)}" title="공급가 ${fmt(Math.round(r.supply))} · 개당이익 ${fmt(Math.round(r.unitProfit))}">${d} · ${m}</span>`;
}

async function loadPricing() {
  try {
    pricingData = await api('/api/pricing');
  } catch (e) { toast(e.message, 'error'); return; }
  const sel = document.getElementById('pricing-group');
  if (sel && !sel.dataset.filled) {
    const groups = [...new Set(pricingData.items.map(it => it.group_name).filter(Boolean))];
    sel.innerHTML = '<option value="">전체 품목군</option>' + groups.map(g => `<option value="${g}">${g}</option>`).join('');
    if (groups.length) sel.value = groups[0];   // 기본: 첫 품목군 (전체는 너무 많음)
    sel.dataset.filled = '1';
  }
  renderPricing();
}

function renderPricing() {
  const { channels, items } = pricingData;
  const q = (document.getElementById('pricing-search')?.value || '').trim().toLowerCase();
  const grp = document.getElementById('pricing-group')?.value || '';
  let head = '<tr><th>품목</th><th class="text-right">원가</th><th class="text-right">소비자가</th>';
  channels.forEach(ch => {
    head += `<th class="pc-ch" colspan="2">${ch.name} <span class="text-muted" style="font-weight:400">${Math.round(ch.commission_rate * 100)}%</span></th>`;
  });
  head += '</tr><tr><th></th><th></th><th></th>';
  channels.forEach(() => { head += '<th class="text-right">판매가</th><th class="text-right">할인·이익률</th>'; });
  head += '</tr>';
  document.getElementById('pricing-thead').innerHTML = head;

  const rows = items.filter(it =>
    (!grp || it.group_name === grp) &&
    (!q || it.name.toLowerCase().includes(q) || (it.code || '').toLowerCase().includes(q)));
  document.getElementById('pricing-tbody').innerHTML = rows.map(it => {
    let tds = `<td><b>${it.name}</b>${it.code ? `<br><span class="text-muted" style="font-size:11px">${it.code}</span>` : ''}</td>`
      + `<td class="text-right">${it.cost != null ? fmt(it.cost) : '-'}</td>`
      + `<td class="text-right">${it.consumer != null ? fmt(it.consumer) : '-'}</td>`;
    channels.forEach(ch => {
      const sale = it.prices[String(ch.id)];
      const r = calcPricing(sale, it.cost, it.consumer, it.pack, ch);
      tds += `<td class="text-right"><input class="pc-input" type="text" inputmode="numeric" value="${sale != null ? fmt(sale) : ''}" onchange="savePrice(${it.id},${ch.id},this)" /></td>`
        + `<td class="text-right pc-sub" id="sub-${it.id}-${ch.id}">${subHtml(r)}</td>`;
    });
    return `<tr>${tds}</tr>`;
  }).join('');
}

async function savePrice(itemId, chId, input) {
  const raw = input.value.replace(/[^0-9]/g, '');
  const val = raw === '' ? null : Number(raw);
  const it = pricingData.items.find(x => x.id === itemId);
  const ch = pricingData.channels.find(x => x.id === chId);
  it.prices[String(chId)] = val;
  const r = calcPricing(val, it.cost, it.consumer, it.pack, ch);
  const sub = document.getElementById(`sub-${itemId}-${chId}`);
  if (sub) sub.innerHTML = subHtml(r);
  if (val != null) input.value = fmt(val);
  try {
    await api('/api/pricing/cell', { method: 'PUT', body: { item_id: itemId, channel_id: chId, sale_price: val } });
  } catch (e) { toast(e.message, 'error'); }
}

function csvCell(v) {
  v = v == null ? '' : String(v);
  return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}

function exportPricingExcel() {
  const { channels, items } = pricingData;
  const head = ['품목군', '품목', '구성', '코드', '원가', '소비자가'];
  channels.forEach(ch => head.push(`${ch.name} 판매가`, `${ch.name} 할인율`, `${ch.name} 공급가`, `${ch.name} 이익률`));
  const lines = [head.map(csvCell).join(',')];
  items.forEach(it => {
    const row = [it.group_name || '', it.name, (it.pack || 1) + '개', it.code || '', it.cost ?? '', it.consumer ?? ''];
    channels.forEach(ch => {
      const sale = it.prices[String(ch.id)];
      const r = calcPricing(sale, it.cost, it.consumer, it.pack, ch);
      if (r) row.push(sale, r.discount != null ? Math.round(r.discount * 100) + '%' : '', Math.round(r.supply), Math.round(r.margin * 100) + '%');
      else row.push('', '', '', '');
    });
    lines.push(row.map(csvCell).join(','));
  });
  const csv = '﻿' + lines.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const today = new Date().toLocaleDateString('sv-SE');  // YYYY-MM-DD
  a.href = url;
  a.download = `비코어랩_채널별판매가_${today}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  toast('엑셀(CSV) 내보내기 완료');
}

// ── 선물 트렌드 (카카오 선물하기 베스트 랭킹) ──
let _kakaoData = null, _kakaoTabIdx = 0, _kakaoBandIdx = 0;
// 가격대 필터 — 수집은 전체, 화면에서 필터(카카오 API가 가격필터 미지원). 우리 시장=중저가.
const KAKAO_BANDS = [
  { label: '전체', min: 0, max: Infinity },
  { label: '~2만', min: 0, max: 20000 },
  { label: '2~4만', min: 20000, max: 40000 },
  { label: '4만+', min: 40000, max: Infinity },
];

async function loadKakao(date) {
  try {
    // 날짜 셀렉트 (최초 1회)
    const sel = document.getElementById('kakao-date');
    if (!sel.options.length) {
      const { dates } = await api('/api/kakao/dates');
      sel.innerHTML = (dates || []).map(d => `<option value="${d}">${d}</option>`).join('');
    }
    const data = await api(`/api/kakao/rank${date ? `?date=${date}` : ''}`);
    _kakaoData = data;
    if (date) sel.value = date; else if (data.date) sel.value = data.date;
    document.getElementById('kakao-updated').textContent =
      (data.tabs[0]?.updatedAt ? `${data.tabs[0].updatedAt} 기준` : '') +
      (data.isFirst ? ' · 첫 수집(내일부터 변동 표시)' : ` · 전일(${data.prevDate}) 대비`);

    // 탭바
    document.getElementById('kakao-tabbar').innerHTML = data.tabs.map((t, i) =>
      `<button class="btn btn-sm ${i === _kakaoTabIdx ? 'btn-primary' : ''}" onclick="selectKakaoTab(${i})">${t.label}${t.hasOrder ? ' 📦' : ''}</button>`
    ).join('');
    // 가격대 필터
    document.getElementById('kakao-priceband').innerHTML =
      '<span class="text-muted" style="font-size:12px;margin-right:2px">가격대</span>' +
      KAKAO_BANDS.map((band, i) =>
        `<button class="btn btn-sm ${i === _kakaoBandIdx ? 'btn-primary' : ''}" onclick="selectKakaoBand(${i})">${band.label}</button>`
      ).join('');

    renderKakaoHighlight(data);
    renderKakaoCards(data.tabs[_kakaoTabIdx]);
  } catch (e) {
    document.getElementById('kakao-cards').innerHTML =
      `<div class="empty-state"><p>${e.message || '데이터 없음'} — 내일 9:50 자동 수집됩니다</p></div>`;
  }
}

function selectKakaoTab(i) {
  _kakaoTabIdx = i;
  document.querySelectorAll('#kakao-tabbar button').forEach((b, j) => b.classList.toggle('btn-primary', j === i));
  renderKakaoCards(_kakaoData.tabs[i]);
}

function selectKakaoBand(i) {
  _kakaoBandIdx = i;
  document.querySelectorAll('#kakao-priceband button').forEach((b, j) => b.classList.toggle('btn-primary', j === i));
  renderKakaoCards(_kakaoData.tabs[_kakaoTabIdx]);
}

async function switchKakaoView(view) {
  document.getElementById('kv-ranking').classList.toggle('btn-primary', view === 'ranking');
  document.getElementById('kv-insight').classList.toggle('btn-primary', view === 'insight');
  document.getElementById('kv-hourly').classList.toggle('btn-primary', view === 'hourly');
  document.getElementById('kakao-view-ranking').classList.toggle('hidden', view !== 'ranking');
  document.getElementById('kakao-view-insight').classList.toggle('hidden', view !== 'insight');
  document.getElementById('kakao-view-hourly').classList.toggle('hidden', view !== 'hourly');
  if (view === 'insight') loadKakaoInsight(document.getElementById('kakao-date').value);
  if (view === 'hourly') loadKakaoHourly();
}

async function loadKakaoHourly() {
  const box = document.getElementById('kakao-view-hourly');
  box.innerHTML = '<div class="empty-state"><p>시간대 분석 중…</p></div>';
  let d;
  try { d = await api('/api/kakao/hourly'); }
  catch (e) { box.innerHTML = '<div class="empty-state"><p>시간대 데이터를 불러오지 못했어요</p></div>'; return; }

  if (d.message) {
    box.innerHTML = `<div class="empty-state" style="padding:40px 20px">
      <div style="font-size:32px;margin-bottom:10px">⏰</div><p>${d.message}</p></div>`;
    return;
  }

  // ① 시간대 슬롯 평균 (막대) — 진짜 피크
  const maxW = Math.max(1, ...d.slots.map(s => s.wishAvg));
  const bars = d.slots.map((s, i) => {
    const w = Math.round(s.wishAvg / maxW * 100);
    const peak = i === 0 ? ' 🔥' : '';
    return `<div style="display:flex;align-items:center;gap:10px;margin:6px 0">
      <div style="width:74px;font-weight:700;font-size:13px">${s.slot}${peak}</div>
      <div style="flex:1;background:#f4f1ea;border-radius:7px;height:24px;overflow:hidden">
        <div style="width:${w}%;height:100%;background:linear-gradient(90deg,#ffd84d,#ff8a3d);border-radius:7px"></div>
      </div>
      <div style="width:170px;font-size:12px;text-align:right">찜 +${fmt(s.wishAvg)}${s.orderAvg ? ` · 주문 +${fmt(s.orderAvg)}` : ''} <span class="text-muted">(n=${s.n})</span></div>
    </div>`;
  }).join('');

  const peakBanner = d.peak ? `
    <div style="background:linear-gradient(135deg,#fff6e0,#ffe9cc);border-radius:12px;padding:16px 18px;margin-bottom:18px">
      <div style="font-size:13px;color:var(--ink-2,#666);margin-bottom:3px">🎯 트래픽 피크 구간 ${d.multiDay ? '(여러 날 평균)' : '(오늘만 — 며칠 더 쌓이면 정확해져요)'}</div>
      <div style="font-size:22px;font-weight:800">${d.peak.slot} <span style="font-size:15px;font-weight:600;color:#e8760d">찜 +${fmt(d.peak.wishAvg)}/구간</span></div>
    </div>` : '';

  // ② 최근 구간 상세 (최신순)
  const rows = [...d.intervals].reverse().map(iv => `
    <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--line,#eee);font-size:13px">
      <div style="width:130px;font-weight:600">${iv.from}→${iv.to}</div>
      <div style="width:110px;color:#1a8f3c;font-weight:700">찜 +${fmt(iv.wish)}</div>
      <div style="width:90px;color:#2563c9">${iv.order ? '주문 +' + fmt(iv.order) : ''}</div>
      <div style="width:80px;color:var(--ink-3,#999)">↑${iv.rankUp}개</div>
      <div style="flex:1;color:var(--ink-2,#666);font-size:12px">${iv.top ? `최고: ${iv.top.brand || ''} 찜+${fmt(iv.top.delta)}` : ''}</div>
    </div>`).join('');

  box.innerHTML = `
    ${peakBanner}
    <h3 style="margin:4px 0 4px">📊 시간대별 활발도 <span class="text-muted" style="font-size:12px;font-weight:400">— 찜 증분(관심 트래픽) 기준. 막대 길수록 그 시간에 사람 몰림</span></h3>
    <div style="margin:10px 0 22px">${bars || '<span class="text-muted">아직 구간이 부족해요</span>'}</div>
    <h3 style="margin:4px 0 4px">🕐 최근 구간 상세 <span class="text-muted" style="font-size:12px;font-weight:400">— 스냅샷 ${d.snapCount}개 · 리뷰는 시간단위로 안 변해 제외</span></h3>
    <div style="margin-top:8px">${rows || '<span class="text-muted">구간 데이터 없음</span>'}</div>`;
}

async function loadKakaoInsight(date) {
  const box = document.getElementById('kakao-view-insight');
  box.innerHTML = '<div class="empty-state"><p>분석 중…</p></div>';
  try {
    const d = await api(`/api/kakao/insights${date ? `?date=${date}` : ''}`);
    const won = v => v == null ? '-' : fmt(v) + '원';
    // ① 판매 급상승 (리뷰증분) — 데이터 2일+ 있을 때
    const risers = d.hasPrev && d.risers.length ? `
      <h3 style="margin:4px 0 8px">🔥 판매 급상승 <span class="text-muted" style="font-size:12px;font-weight:400">— 어제 대비 리뷰(실구매) 증가 TOP</span></h3>
      <div class="kakao-ins-list">${d.risers.map((p, i) => `
        <a href="${p.productUrl}" target="_blank" class="kakao-ins-row">
          <span class="ins-rank">${i + 1}</span>
          <span class="ins-thumb" style="background-image:url('${p.imageUrl || ''}')"></span>
          <span class="ins-main"><b>${p.brand}</b> <span class="text-muted">${p.category.split('>').pop()}</span><br>${p.name}</span>
          <span class="ins-metric"><b style="color:#1a8f3c">📝 +${fmt(p.reviewDelta)}</b><br><span class="text-muted">${won(p.price)}</span></span>
        </a>`).join('')}</div>` : `
      <div class="kakao-hl-box" style="margin-bottom:16px">📈 <b>판매 급상승</b>은 내일부터 표시돼요 — 오늘이 첫 수집이라 어제와 비교할 데이터가 아직 없어요. 매일 쌓일수록 정확해집니다.</div>`;
    // ② 카테고리 활발도
    const cats = `
      <h3 style="margin:18px 0 8px">📂 카테고리 활발도 <span class="text-muted" style="font-size:12px;font-weight:400">— 리뷰(누적판매) 많은 시장 순. 큰 시장일수록 수요 검증됨</span></h3>
      <div class="table-scroll"><table class="kakao-ins-table">
        <thead><tr><th>카테고리</th><th class="r">리뷰 합계</th><th class="r">찜 중앙값</th><th class="r">가격 중앙값</th><th class="r">가격대</th></tr></thead>
        <tbody>${d.categories.map(c => `<tr>
          <td>${c.label}</td><td class="r"><b>${fmt(c.reviewSum)}</b></td>
          <td class="r">${fmt(c.wishMedian)}</td><td class="r">${won(c.priceMedian)}</td>
          <td class="r text-muted">${won(c.priceMin)}~${won(c.priceMax)}</td></tr>`).join('')}</tbody>
      </table></div>`;
    // ③ 검증 상품 TOP (리뷰 누적 최다)
    const top = `
      <h3 style="margin:18px 0 8px">✅ 검증된 베스트셀러 <span class="text-muted" style="font-size:12px;font-weight:400">— 리뷰(실판매) 누적 최다. 이미 팔리는 안전한 시장</span></h3>
      <div class="kakao-ins-list">${d.topReviewed.map((p, i) => `
        <a href="${p.productUrl}" target="_blank" class="kakao-ins-row">
          <span class="ins-rank">${i + 1}</span>
          <span class="ins-thumb" style="background-image:url('${p.imageUrl || ''}')"></span>
          <span class="ins-main"><b>${p.brand}</b> <span class="text-muted">${p.category.split('>').pop()}</span><br>${p.name}</span>
          <span class="ins-metric"><b>📝 ${fmt(p.reviewTotal)}</b><br><span class="text-muted">${won(p.price)}</span></span>
        </a>`).join('')}</div>`;
    box.innerHTML = `<div class="text-muted" style="font-size:12px;margin-bottom:12px">${d.date} 기준 · 데이터가 쌓일수록 '판매 급상승'이 강력해져요</div>${risers}${cats}${top}`;
  } catch (e) {
    box.innerHTML = `<div class="empty-state"><p>${e.message || '데이터 없음'}</p></div>`;
  }
}

function renderKakaoHighlight(data) {
  if (data.isFirst) { document.getElementById('kakao-highlight').innerHTML = ''; return; }
  const risers = [], news = [];
  data.tabs.forEach(t => t.rows.forEach(r => {
    if (r.move === 'new') news.push({ ...r, tab: t.label });
    else if (typeof r.move === 'number' && r.move >= 3) risers.push({ ...r, tab: t.label });
  }));
  risers.sort((a, b) => b.move - a.move);
  const chip = (r, badge) => `<a href="${r.productUrl}" target="_blank" class="kakao-chip" title="${r.name}">${badge} <b>${r.brand}</b> <span class="text-muted">${r.tab.split('>').pop()}</span></a>`;
  const h = document.getElementById('kakao-highlight');
  if (!risers.length && !news.length) { h.innerHTML = ''; return; }
  h.innerHTML = `<div class="kakao-hl-box">
    ${risers.length ? `<div><span class="kakao-hl-t">🔥 급상승</span> ${risers.slice(0, 6).map(r => chip(r, `▲${r.move}`)).join('')}</div>` : ''}
    ${news.length ? `<div style="margin-top:8px"><span class="kakao-hl-t">🆕 신규진입</span> ${news.slice(0, 6).map(r => chip(r, '')).join('')}</div>` : ''}
  </div>`;
}

function renderKakaoCards(tab) {
  if (!tab) return;
  const moveBadge = (r) => {
    if (r.move === 'new') return '<span class="kakao-mv new">🆕 신규</span>';
    if (typeof r.move !== 'number' || r.move === 0) return '<span class="kakao-mv flat">―</span>';
    return r.move > 0 ? `<span class="kakao-mv up">▲${r.move}</span>` : `<span class="kakao-mv down">▼${-r.move}</span>`;
  };
  // 증분 pill — 양수는 초록(팔림/관심↑), 음수는 회색. 값 있을 때만 표시.
  const delta = (v, label, unit = '') => {
    if (v == null || v === 0) return '';
    const cls = v > 0 ? 'up' : 'down';
    return `<span class="kakao-d ${cls}" title="전일 대비 ${label}">${label} ${v > 0 ? '+' : ''}${fmt(v)}${unit}</span>`;
  };
  // 가격대 필터 (순위는 원래대로 유지, 해당 구간 상품만 표시)
  const band = KAKAO_BANDS[_kakaoBandIdx];
  const filtered = tab.rows.filter(r => {
    const p = r.price;
    return typeof p === 'number' && p >= band.min && p < band.max;
  });
  const cards = filtered.map(r => {
    const dc = r.discountRate ? `<span class="kakao-dc">${r.discountRate}%</span>` : '';
    // 핵심 판매신호: 리뷰Δ(실구매) > 주문수 > 찜Δ. 카드 하단 지표행에 모아서 표시.
    const metrics = [
      delta(r.reviewDelta, '📝', ''),                                   // 리뷰 증분 = 실구매
      r.orderCount != null ? `<span class="kakao-d order" title="주문수(트렌딩 노출분)">📦${fmt(r.orderCount)}${r.orderDelta ? (r.orderDelta > 0 ? '+' : '') + r.orderDelta : ''}</span>` : '',
      delta(r.wishDelta, '♡', ''),                                      // 찜 증분 = 관심
    ].filter(Boolean).join(' ');
    return `<a href="${r.productUrl}" target="_blank" class="kakao-card">
      <div class="kakao-rank">${r.rank} ${moveBadge(r)}</div>
      <div class="kakao-img" style="background-image:url('${r.imageUrl || ''}')"></div>
      <div class="kakao-body">
        <div class="kakao-brand">${r.brand || ''}</div>
        <div class="kakao-name">${r.name || ''}</div>
        <div class="kakao-price">${dc} <b>${fmt(r.price)}원</b></div>
        <div class="kakao-base">♡ ${fmt(r.wishCount)}${r.reviewTotal != null ? ` · 📝 ${fmt(r.reviewTotal)}` : ''}</div>
        ${metrics ? `<div class="kakao-metrics">${metrics}</div>` : '<div class="kakao-metrics kakao-first">전일 데이터 없음</div>'}
      </div>
    </a>`;
  }).join('');
  document.getElementById('kakao-cards').innerHTML = cards ||
    `<div class="empty-state"><p>${band.label} 가격대에 해당 상품이 없어요</p></div>`;
}

// ── 경쟁사 레이더 (광고 운영품목 우리 vs 경쟁 가격추적) ──
let _radarCharts = [];

async function loadRadar() {
  const box = document.getElementById('radar-groups');
  box.innerHTML = '<div class="empty-state"><p>불러오는 중…</p></div>';
  _radarCharts.forEach(c => { try { c.destroy(); } catch (e) {} });
  _radarCharts = [];
  try {
    const d = await api('/api/radar/groups');
    if (!d.groups || !d.groups.length) {
      box.innerHTML = '<div class="empty-state"><p>등록된 추적 품목이 없어요</p></div>'; return;
    }
    // 그룹(키워드) datalist 채우기
    document.getElementById('radar-kw-list').innerHTML =
      d.groups.map(g => `<option value="${g.keyword}">`).join('');
    box.innerHTML = d.groups.map((g, gi) => {
      const rows = g.items.map(it => {
        const rowStyle = it.isMine ? ' style="background:rgba(217,119,87,.08);font-weight:600"'
          : (it.isReference ? ' style="color:#aaa"' : '');
        const mark = it.isMine ? '⭐' : (it.isReference ? '📊' : '');
        const refTag = it.isReference ? ' <span style="font-size:10px;color:#bbb;border:1px solid #ddd;border-radius:4px;padding:0 4px">참고</span>' : '';
        const pd = it.priceDelta ? `<span class="kakao-d ${it.priceDelta < 0 ? 'up' : 'down'}">${it.priceDelta < 0 ? '▼' : '▲'}${fmt(Math.abs(it.priceDelta))}</span>` : '';
        const rd = it.reviewDelta ? `<span class="kakao-d ${it.reviewDelta > 0 ? 'up' : 'down'}" title="전일 대비 리뷰">${it.reviewDelta > 0 ? '+' : ''}${fmt(it.reviewDelta)}</span>` : '';
        return `<tr${rowStyle}>
          <td>${mark} <a href="${it.productUrl}" target="_blank" style="color:inherit">${it.label}</a>${refTag}</td>
          <td class="r"><b>${fmt(it.price)}원</b> ${pd}</td>
          <td class="r">${fmt(it.reviewCount)} ${rd}</td>
          <td class="r">${it.ranking != null ? it.ranking + '위' : '-'}</td>
          <td class="r"><span class="radar-del" title="제거" onclick="deleteRadarProduct(${it.id},'${(it.label || '').replace(/'/g, '')}')">✕</span></td>
        </tr>`;
      }).join('');
      // 참고(대기업)는 추이 그래프에서 제외 — 추적 대상만
      const trendItems = g.items.filter(it => !it.isReference);
      const hasTrend = trendItems.some(it => it.history.length >= 2);
      const compN = g.count - (g.hasMine ? 1 : 0) - (g.refCount || 0);
      return `<div class="radar-card">
        <div class="radar-head">${g.hasMine ? '⭐ ' : ''}${g.keyword}
          <span class="text-muted" style="font-size:12px;font-weight:400">${g.hasMine ? '우리 1 · ' : ''}추적 ${compN}${g.refCount ? ` · 📊참고 ${g.refCount}` : ''}</span></div>
        <table class="kakao-ins-table" style="margin-bottom:10px">
          <thead><tr><th>상품</th><th class="r">현재가</th><th class="r">리뷰</th><th class="r">순위</th><th class="r"></th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        ${hasTrend ? `<div style="height:200px"><canvas id="radar-chart-${gi}"></canvas></div>`
          : '<div class="text-muted" style="font-size:12px">📈 가격추이 그래프는 이틀 이상 쌓이면 표시돼요 (오늘 첫 수집)</div>'}
      </div>`;
    }).join('');

    // 가격추이 차트 (그룹별)
    const palette = ['#d97757', '#5896', '#1a8f3c', '#c23', '#2563c9', '#b26', '#888'];
    d.groups.forEach((g, gi) => {
      const el = document.getElementById(`radar-chart-${gi}`);
      if (!el) return;
      const chartItems = g.items.filter(it => !it.isReference);  // 참고(대기업) 제외
      const allDates = [...new Set(chartItems.flatMap(it => it.history.map(h => h.date)))].sort();
      const datasets = chartItems.map((it, i) => {
        const map = Object.fromEntries(it.history.map(h => [h.date, h.price]));
        return {
          label: (it.isMine ? '⭐' : '') + it.label.replace(/\s*\(.*\)/, ''),
          data: allDates.map(dt => map[dt] ?? null),
          borderColor: it.isMine ? '#d97757' : palette[(i % 6) + 1],
          borderWidth: it.isMine ? 3 : 1.5,
          spanGaps: true, tension: .3, pointRadius: 0,
        };
      });
      _radarCharts.push(new Chart(el, {
        type: 'line',
        data: { labels: allDates.map(x => x.slice(5)), datasets },
        options: { responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 10 } } } },
          scales: { y: { ticks: { callback: v => (v / 1000) + 'k' }, grid: { color: '#f0eadf' } }, x: { grid: { display: false } } } },
      }));
    });
  } catch (e) {
    box.innerHTML = `<div class="empty-state"><p>${e.message || '데이터 없음'}</p></div>`;
  }
}

async function addRadarProduct() {
  const url = document.getElementById('radar-url').value.trim();
  const kw = document.getElementById('radar-kw').value.trim();
  const msg = document.getElementById('radar-add-msg');
  if (!url || !kw) { msg.textContent = 'URL과 그룹을 입력하세요'; msg.style.color = '#c23'; return; }
  msg.textContent = '등록 중…'; msg.style.color = '';
  try {
    const r = await api('/api/radar/add', { method: 'POST', body: JSON.stringify({
      url, keyword: kw,
      isMine: document.getElementById('radar-mine').checked,
      isReference: document.getElementById('radar-ref').checked,
    }) });
    msg.textContent = r.message || (r.ok ? '완료' : '실패');
    msg.style.color = r.ok ? '#1a8f3c' : '#c23';
    if (r.ok) {
      document.getElementById('radar-url').value = '';
      document.getElementById('radar-mine').checked = false;
      document.getElementById('radar-ref').checked = false;
      setTimeout(loadRadar, 800);  // 목록 새로고침 (가격은 다음 수집 때)
    }
  } catch (e) { msg.textContent = e.message; msg.style.color = '#c23'; }
}

async function deleteRadarProduct(id, label) {
  if (!confirm(`'${label}'을(를) 레이더에서 제거할까요?`)) return;
  try {
    await api(`/api/radar/product/${id}`, { method: 'DELETE' });
    loadRadar();
  } catch (e) { toast(e.message, 'error'); }
}

// ── 네이버 SA 광고 ──
let _nsaDays = 7;
let _nsaKwData = null;
let _nsaTrendChart = null;
let _nsaBubbleChart = null;
let _nsaKwSort = { key: 'clk', dir: -1 };

function setNsaDays(days) {
  _nsaDays = days;
  [3, 7, 30].forEach(d => {
    const btn = document.getElementById(`nsa-d-${d}`);
    if (btn) btn.classList.toggle('btn-primary', d === days);
  });
  const kwVisible = !document.getElementById('nsa-view-kw')?.classList.contains('hidden');
  if (kwVisible) loadNaverKw(days); else loadNaverAd(days);
}

function switchNsaView(view) {
  ['summary', 'kw'].forEach(v => {
    const btn = document.getElementById(`nsv-${v}`);
    const panel = document.getElementById(`nsa-view-${v}`);
    if (btn) btn.classList.toggle('btn-primary', v === view);
    if (panel) panel.classList.toggle('hidden', v !== view);
  });
  if (view === 'summary') loadNaverAd(_nsaDays);
  else loadNaverKw(_nsaDays);
}

async function loadNaverAd(days) {
  if (days !== undefined) _nsaDays = days;
  [3, 7, 30].forEach(d => {
    const btn = document.getElementById(`nsa-d-${d}`);
    if (btn) btn.classList.toggle('btn-primary', d === _nsaDays);
  });
  const sigBox = document.getElementById('nsa-signals');
  if (sigBox) sigBox.innerHTML = '<div style="grid-column:span 4;color:#bbb;font-size:13px;padding:24px 0">로딩 중…</div>';
  try {
    const d = await api(`/api/naver/summary?days=${_nsaDays}`);
    renderNsaSignals(d.signals || []);
    renderNsaKpi(d.kpi || {}, d.prev || {});
    loadNsaTrend(_nsaDays);
  } catch(e) {
    if (sigBox) sigBox.innerHTML = `<div style="grid-column:span 4;color:#bbb;font-size:13px;padding:24px 0">${e.message}</div>`;
  }
}

function renderNsaSignals(signals) {
  const box = document.getElementById('nsa-signals');
  if (!box) return;
  const kindMap = {
    opportunity: { cls: 'green', tag: '🟢 기회' },
    loss:        { cls: 'red',   tag: '🔴 손실' },
    dormant:     { cls: 'gray',  tag: '⚫ 잠복' },
    ops:         { cls: 'amber', tag: '💰 운영' },
  };
  if (!signals.length) {
    box.innerHTML = '<div class="nsa-sig gray" style="grid-column:span 4;text-align:center;padding:18px">시그널 없음 — 안정 운영 중</div>';
    return;
  }
  box.innerHTML = signals.map(s => {
    const k = kindMap[s.kind] || { cls: 'gray', tag: s.kind };
    const metaParts = [s.confidence ? '확신 ' + s.confidence : '', s.window || ''].filter(Boolean);
    return `<div class="nsa-sig ${k.cls}">
      <span class="nsa-tag">${k.tag}</span>
      <div class="nsa-sig-kw">${s.title || '-'}</div>
      <div class="nsa-fig">${s.figures || ''}</div>
      <div class="nsa-act">→ ${s.action || ''}</div>
      ${metaParts.length ? `<div class="nsa-meta">${metaParts.join(' · ')}</div>` : ''}
    </div>`;
  }).join('');
}

function renderNsaKpi(kpi, prev) {
  const box = document.getElementById('nsa-kpi');
  if (!box) return;
  const roasTarget = 400;
  const ctr = (kpi.imp && kpi.clk) ? (kpi.clk / kpi.imp * 100).toFixed(1) : (kpi.ctr != null ? Number(kpi.ctr).toFixed(1) : '0.0');
  const convAmt = kpi.convAmt || 0;
  const convAmtDisp = convAmt >= 1e6 ? (convAmt / 1e4).toFixed(1) + '만' : fmt(convAmt);
  const roasVal = kpi.roas || 0;
  const roasColor = roasVal >= roasTarget ? '#1a8f3c' : '#d63a3a';
  const roasDelta = (prev && prev.roas != null) ? (roasVal > prev.roas ? '<small style="color:#1a8f3c"> ▲</small>' : '<small style="color:#d63a3a"> ▼</small>') : '';

  function pctDelta(cur, prevV) {
    if (cur == null || prevV == null || prevV === 0) return '';
    const d = cur - prevV;
    if (Math.abs(d) < 0.001) return '';
    const pct = Math.abs(Math.round(d / prevV * 100));
    return d > 0
      ? `<small style="color:#1a8f3c"> ▲${pct}%</small>`
      : `<small style="color:#d63a3a"> ▼${pct}%</small>`;
  }

  const cells = [
    { lbl:'광고비',       val: fmt(kpi.cost || 0),                                   sub:'원',         delta: pctDelta(kpi.cost, prev?.cost) },
    { lbl:'전환매출(실)', val: convAmtDisp,                                           sub:'구매완료',   delta: pctDelta(kpi.convAmt, prev?.convAmt) },
    { lbl:'ROAS',         val: `<span style="color:${roasColor}">${fmt(Math.round(roasVal))}%</span>`, sub:`목표 ${roasTarget}%`, delta: roasDelta },
    { lbl:'전환수',       val: fmt(kpi.ccnt || 0),                                   sub:'건' },
    { lbl:'CVR',          val: (kpi.cvr != null ? Number(kpi.cvr).toFixed(1) : '0.0') + '%', sub:'전환율' },
    { lbl:'CPC',          val: fmt(Math.round(kpi.cpc || 0)),                        sub:'클릭당' },
    { lbl:'노출/클릭',   val: fmt(kpi.imp || 0), sub:`클릭 ${fmt(kpi.clk || 0)} · CTR ${ctr}%` },
  ];
  box.innerHTML = cells.map(c =>
    `<div class="nsa-kpi-cell">
      <div class="nsa-kpi-lbl">${c.lbl}</div>
      <div class="nsa-kpi-val">${c.val}${c.delta || ''}</div>
      <div class="nsa-kpi-sub">${c.sub}</div>
    </div>`
  ).join('');
}

async function loadNsaTrend(days) {
  const wrap = document.querySelector('#nsa-trend-chart')?.parentElement;
  const canvas = document.getElementById('nsa-trend-chart');
  if (!canvas) return;
  if (_nsaTrendChart) { _nsaTrendChart.destroy(); _nsaTrendChart = null; }
  try {
    const d = await api(`/api/naver/trend?days=${days}`);
    const items = d.items || [];
    if (!items.length) {
      if (wrap) wrap.innerHTML = '<div style="color:#bbb;font-size:13px;text-align:center;padding:40px">추이 데이터 없음</div>';
      return;
    }
    const labels = items.map(i => i.date.slice(5));
    const roasData = items.map(i => i.roas ?? null);
    const costData = items.map(i => i.cost ?? null);
    _nsaTrendChart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            type: 'line',
            label: 'ROAS (%)',
            data: roasData,
            borderColor: '#1a8f3c',
            backgroundColor: 'rgba(26,143,60,0)',
            yAxisID: 'y1',
            tension: 0.3,
            pointRadius: 3,
            borderWidth: 2.5,
            pointBackgroundColor: '#1a8f3c',
          },
          {
            type: 'bar',
            label: '광고비',
            data: costData,
            backgroundColor: 'rgba(178,88,57,0.5)',
            yAxisID: 'y2',
            borderRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 10, font: { size: 11 } } },
          tooltip: {
            backgroundColor: '#2a241f',
            titleFont: { size: 12 },
            bodyFont: { size: 13, weight: '600' },
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: ctx => ctx.dataset.label === 'ROAS (%)'
                ? `ROAS: ${fmt(Math.round(ctx.raw || 0))}%`
                : `광고비: ₩${fmt(ctx.raw || 0)}`,
            },
          },
        },
        scales: {
          y1: {
            type: 'linear',
            position: 'left',
            title: { display: true, text: 'ROAS (%)', font: { size: 11 } },
            grid: { color: '#f0eadf' },
            ticks: { callback: v => v + '%', font: { size: 11 } },
          },
          y2: {
            type: 'linear',
            position: 'right',
            title: { display: true, text: '광고비 (₩)', font: { size: 11 } },
            grid: { display: false },
            ticks: { callback: v => v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v, font: { size: 11 } },
          },
          x: { grid: { display: false } },
        },
      },
    });
  } catch(e) {
    if (wrap) wrap.innerHTML = `<div style="color:#bbb;font-size:13px;text-align:center;padding:40px">${e.message}</div>`;
  }
}

async function loadNaverKw(days) {
  if (days === undefined) days = _nsaDays;
  const tbody = document.getElementById('nsa-kw-tbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:#bbb;padding:24px">로딩 중…</td></tr>';
  // 키워드 뷰 상단 기간 레이블 업데이트
  const kwPeriodLabel = document.getElementById('nsa-kw-period-label');
  if (kwPeriodLabel) kwPeriodLabel.textContent = `최근 ${days}일`;
  try {
    const d = await api(`/api/naver/keywords?days=${days}`);
    _nsaKwData = d.items || [];
    renderNsaBubble(_nsaKwData, d.targetRoas);
    renderNsaCross(d.cross || [], d.targetRoas);
    renderNsaKwTable();
  } catch(e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:#bbb;padding:24px">${e.message}</td></tr>`;
    const crossBox = document.getElementById('nsa-cross');
    if (crossBox) crossBox.innerHTML = `<div style="color:#bbb;font-size:13px">${e.message}</div>`;
  }
}

function renderNsaBubble(items, targetRoas) {
  const canvas = document.getElementById('nsa-bubble');
  if (!canvas) return;
  // 줌 플러그인 등록 (UMD 로드 후 1회)
  const zp = window.ChartZoom || (window['chartjs-plugin-zoom']);
  if (zp && Chart.registry && !Chart.registry.plugins.get('zoom')) { try { Chart.register(zp); } catch (e) {} }
  if (_nsaBubbleChart) { _nsaBubbleChart.destroy(); _nsaBubbleChart = null; }
  const ROAS_CAP = 2500;
  const pts = items.map((kw, idx) => ({
    x: kw.clk || 0,
    y: Math.min(kw.roas || 0, ROAS_CAP),
    r: Math.max(7, Math.min(40, Math.sqrt(kw.imp || 1) * 2.2)),
    // extra data for tooltip / click
    kw: kw.kw, typ: kw.typ, grp: kw.grp, roas: kw.roas || 0,
    clk: kw.clk || 0, imp: kw.imp || 0, cost: kw.cost || 0,
    ccnt: kw.ccnt || 0, cv: kw.convAmt || 0, cpc: kw.cpc || 0,
    qi: kw.qi, c: kw.vcolor || '#8a8a8a', vl: kw.verdict || '-', idx,
  }));
  _nsaBubbleChart = new Chart(canvas, {
    type: 'bubble',
    data: {
      datasets: [{
        data: pts,
        backgroundColor: pts.map(p => p.c + 'cc'),
        borderColor: pts.map(p => p.c),
        borderWidth: 1.5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      onClick(e, els) {
        if (!els.length) return;
        renderNsaKwDetail(pts[els[0].index].idx);
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#2a241f',
          callbacks: {
            label(c) {
              const p = c.raw;
              return [`${p.kw} (${p.typ})`, `${p.grp}`, `ROAS ${fmt(p.roas)}% · 클릭 ${p.clk} · 노출 ${p.imp}`];
            },
          },
        },
        zoom: {
          zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'xy' },
          pan: { enabled: true, mode: 'xy' },
        },
      },
      scales: {
        x: { title: { display: true, text: '클릭 수 →' }, min: -0.4, grid: { color: '#f0eee9' } },
        y: { title: { display: true, text: 'ROAS (%) ↑' }, min: 0, max: 2600, grid: { color: '#f0eee9' } },
      },
    },
  });
}

function renderNsaKwDetail(idx) {
  if (!_nsaKwData || _nsaKwData[idx] == null) return;
  const p = _nsaKwData[idx];
  const box = document.getElementById('nsa-detail');
  if (!box) return;
  const c = p.vcolor || '#8a8a8a';
  const ctr = p.imp ? (p.clk / p.imp * 100).toFixed(1) : '0.0';
  const cell = (l, v) => `<div class="nsa-dt-cell"><div class="nsa-dt-l">${l}</div><div class="nsa-dt-v">${v}</div></div>`;
  const bidTxt = p.bid ? ` · 입찰 ${fmt(p.bid)}원` : '';
  box.innerHTML = `
    <div class="nsa-dt-head">
      <div class="nsa-dt-kw">${p.kw}</div>
      <div class="nsa-dt-badge" style="background:${c}22;color:${c}">${p.verdict || '-'}</div>
    </div>
    <div class="nsa-dt-path">📁 캠페인 <b>${p.campaign || '-'}</b> › 그룹 <b>${p.adgroup || p.grp || '-'}</b></div>
    <div class="nsa-dt-tag" style="margin-bottom:12px">${p.typ}${p.qi != null ? ` · 품질지수 ${p.qi}` : ''}${bidTxt}</div>
    <div class="nsa-dt-grid">
      ${cell('노출', fmt(p.imp || 0))}
      ${cell('클릭', fmt(p.clk || 0) + ` (CTR ${ctr}%)`)}
      ${cell('CPC', fmt(p.cpc || 0))}
      ${cell('광고비', fmt(p.cost || 0))}
      ${cell('전환수', fmt(p.ccnt || 0))}
      ${cell('전환매출', fmt(p.convAmt || 0))}
      ${cell('ROAS', `<span style="color:${c}">${fmt(p.roas || 0)}%</span>`)}
      ${cell('목표대비', p.roas >= 400 ? '✅ 달성' : `${fmt(p.roas || 0)}/400%`)}
    </div>`;
}

function resetNsaZoom() {
  if (_nsaBubbleChart && _nsaBubbleChart.resetZoom) _nsaBubbleChart.resetZoom();
}

function renderNsaCross(cross, targetRoas) {
  const box = document.getElementById('nsa-cross');
  if (!box) return;
  if (!cross.length) {
    box.innerHTML = '<div style="color:#bbb;font-size:13px">교차 비교 데이터 없음</div>';
    return;
  }
  const rColor = r => r >= (targetRoas || 400) ? '#1a8f3c' : r > 0 ? '#d63a3a' : '#8a8a8a';
  box.innerHTML = cross.map(c => {
    const itemsHtml = (c.entries || []).map(e =>
      `<div class="nsa-cc-item" style="border-color:${rColor(e.roas || 0)}55">
        <div class="nsa-cc-typ">${e.typ} · ${e.grp || '-'}</div>
        <div class="nsa-cc-roas" style="color:${rColor(e.roas || 0)}">${fmt(e.roas || 0)}%</div>
        <div class="nsa-cc-sub">클릭 ${fmt(e.clk || 0)} · 광고비 ${fmt(e.cost || 0)} · 전환 ${fmt(e.ccnt || 0)}</div>
      </div>`
    ).join('');
    return `<div class="nsa-cc-card"><div class="nsa-cc-kw">🔗 ${c.kw}</div><div class="nsa-cc-row">${itemsHtml}</div></div>`;
  }).join('');
}

function sortNsaKw(key) {
  if (_nsaKwSort.key === key) _nsaKwSort.dir *= -1;
  else { _nsaKwSort.key = key; _nsaKwSort.dir = key === 'kw' ? 1 : -1; }
  renderNsaKwTable();
}

function renderNsaKwTable() {
  const tbody = document.getElementById('nsa-kw-tbody');
  if (!tbody || !_nsaKwData) return;
  const q = (document.getElementById('nsa-kw-search')?.value || '').toLowerCase();
  const typ = document.getElementById('nsa-kw-typ')?.value || '';
  let rows = _nsaKwData.slice();
  if (q) rows = rows.filter(r => (r.kw || '').toLowerCase().includes(q));
  if (typ) rows = rows.filter(r => (r.typ || '') === typ);
  const { key, dir } = _nsaKwSort;
  rows.sort((a, b) => {
    const av = a[key] ?? (key === 'kw' ? '' : 0);
    const bv = b[key] ?? (key === 'kw' ? '' : 0);
    if (typeof av === 'string') return av.localeCompare(bv, 'ko') * dir;
    return (av - bv) * dir;
  });
  // 정렬 화살표 갱신
  document.querySelectorAll('#nsa-kw-table .sort-ar').forEach(el => {
    el.textContent = el.dataset.k === key ? (dir > 0 ? '▲' : '▼') : '';
  });
  tbody.innerHTML = rows.length ? rows.map(r => {
    const origIdx = _nsaKwData.indexOf(r);
    const vc = r.vcolor || '#8a8a8a';
    const roasTxt = (r.roas > 0)
      ? `<span style="color:${vc};font-weight:700">${fmt(r.roas)}%</span>`
      : '<span class="text-muted">-</span>';
    const qiCls = (r.qi >= 5) ? 'nsa-qi-hi' : (r.qi >= 3) ? 'nsa-qi-mid' : 'nsa-qi-lo';
    return `<tr style="cursor:pointer" onclick="renderNsaKwDetail(${origIdx})">
      <td>${r.kw}</td>
      <td><span class="nsa-typ">${r.typ || '-'}</span></td>
      <td class="text-right number">${fmt(r.imp || 0)}</td>
      <td class="text-right number">${fmt(r.clk || 0)}</td>
      <td class="text-right number">${r.cpc > 0 ? fmt(r.cpc) : '<span class="text-muted">-</span>'}</td>
      <td class="text-right number">${r.cost > 0 ? fmt(r.cost) : '<span class="text-muted">-</span>'}</td>
      <td class="text-right number">${fmt(r.ccnt || 0)}</td>
      <td class="text-right">${roasTxt}</td>
      <td class="text-right"><span class="nsa-qi ${qiCls}">${r.qi != null ? r.qi : '-'}</span></td>
      <td><span class="nsa-badge" style="background:${vc}22;color:${vc}">${r.verdict || '-'}</span></td>
    </tr>`;
  }).join('') : '<tr><td colspan="10" style="text-align:center;color:#bbb;padding:24px">키워드 없음</td></tr>';
}

// ── Users (직원 관리) ──
let usersCache = [];
const ROLE_LABEL = { admin: '관리자', manager: '매니저', staff: '직원', viewer: '뷰어' };

async function loadUsers() {
  try {
    usersCache = await api('/api/users');
  } catch (e) { toast(e.message, 'error'); return; }
  const tb = document.getElementById('users-tbody');
  tb.innerHTML = usersCache.map(u => `
    <tr class="${u.is_active ? '' : 'row-inactive'}">
      <td>${u.id}</td>
      <td><b>${u.username}</b></td>
      <td>${u.name}</td>
      <td>${u.email || '<span class="text-muted">-</span>'}</td>
      <td><span class="badge-role role-${u.role}">${ROLE_LABEL[u.role] || u.role}</span></td>
      <td>${u.is_active
        ? '<span class="badge badge-on">활성</span>'
        : '<span class="badge badge-off">비활성</span>'}</td>
      <td class="row-actions">
        <button class="btn btn-sm" onclick="editUser(${u.id})">수정</button>
        <button class="btn btn-sm" onclick="resetUserPw(${u.id})">비번초기화</button>
        ${u.is_active
          ? `<button class="btn btn-sm" style="color:var(--red)" onclick="toggleUser(${u.id},0)">비활성화</button>`
          : `<button class="btn btn-sm" style="color:var(--green)" onclick="toggleUser(${u.id},1)">활성화</button>`}
      </td>
    </tr>`).join('');
}

function editUser(id) {
  const u = id ? usersCache.find(x => x.id === id) : null;
  const m = document.getElementById('modal');
  m.querySelector('.modal-header span').textContent = u ? '직원 정보 수정' : '직원 추가';
  m.querySelector('.modal-body').innerHTML = `
    <div class="form-group"><label>이름 <span class="required">*</span></label>
      <input id="u-name" value="${u ? u.name : ''}" placeholder="직원 이름" /></div>
    <div class="form-group"><label>아이디 <span class="required">*</span></label>
      <input id="u-username" value="${u ? u.username : ''}" ${u ? 'disabled' : ''} placeholder="로그인 아이디" /></div>
    <div class="form-group"><label>이메일</label>
      <input id="u-email" value="${u && u.email ? u.email : ''}" placeholder="name@becorelab.kr" /></div>
    <div class="form-group"><label>권한</label>
      <select id="u-role">
        <option value="staff">직원 (staff)</option>
        <option value="manager">매니저 (manager)</option>
        <option value="admin">관리자 (admin)</option>
        <option value="viewer">뷰어 (viewer)</option>
      </select></div>
    ${u ? '' : `<div class="form-group"><label>임시 비밀번호 <span class="required">*</span></label>
      <input id="u-pass" value="ilbia2026!" /><div class="text-muted" style="font-size:12px;margin-top:4px">첫 로그인 후 변경 안내하세요.</div></div>`}
  `;
  if (u) m.querySelector('#u-role').value = u.role;
  m.querySelector('.modal-footer').innerHTML = `
    <button class="btn" onclick="closeModal()">취소</button>
    <button class="btn btn-primary" onclick="saveUser(${id})">저장</button>`;
  openModal();
}

async function saveUser(id) {
  const name = document.getElementById('u-name').value.trim();
  const role = document.getElementById('u-role').value;
  const email = document.getElementById('u-email').value.trim();
  if (!name) return toast('이름을 입력하세요', 'error');
  try {
    if (id) {
      await api(`/api/users/${id}`, { method: 'PUT', body: { name, role, email } });
      toast('수정되었습니다');
    } else {
      const username = document.getElementById('u-username').value.trim();
      const password = document.getElementById('u-pass').value;
      if (!username) return toast('아이디를 입력하세요', 'error');
      if (password.length < 4) return toast('임시 비밀번호는 4자 이상이어야 합니다', 'error');
      await api('/api/users', { method: 'POST', body: { username, name, role, email, password } });
      toast('직원이 추가되었습니다');
    }
    closeModal();
    loadUsers();
  } catch (e) { toast(e.message, 'error'); }
}

async function toggleUser(id, active) {
  const u = usersCache.find(x => x.id === id);
  const verb = active ? '활성화' : '비활성화 (로그인 차단)';
  if (!confirm(`${u.name}님 계정을 ${verb} 할까요?`)) return;
  try {
    await api(`/api/users/${id}`, { method: 'PUT', body: { is_active: active } });
    toast(active ? '활성화되었습니다' : '비활성화되었습니다 (로그인 차단)');
    loadUsers();
  } catch (e) { toast(e.message, 'error'); }
}

async function resetUserPw(id) {
  const u = usersCache.find(x => x.id === id);
  const pw = prompt(`${u.name}님의 새 임시 비밀번호를 입력하세요:`, 'ilbia2026!');
  if (pw === null) return;
  if (pw.length < 4) return toast('4자 이상 입력하세요', 'error');
  try {
    await api(`/api/users/${id}/reset-password`, { method: 'POST', body: { password: pw } });
    toast('비밀번호가 초기화되었습니다');
  } catch (e) { toast(e.message, 'error'); }
}

// ── Login ──
function enterApp() {
  document.getElementById('login-screen').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  document.getElementById('user-name').textContent = currentUser.name;
  navigate(localStorage.getItem('erp_page') || 'dashboard');
}

async function doLogin() {
  const username = document.getElementById('login-user').value;
  const password = document.getElementById('login-pass').value;
  const errEl = document.getElementById('login-error');

  if (!username || !password) {
    errEl.textContent = '아이디와 비밀번호를 입력하세요.';
    errEl.classList.add('show');
    return;
  }
  errEl.classList.remove('show');

  try {
    currentUser = await api('/api/auth/login', { method: 'POST', body: { username, password } });
    localStorage.setItem('erp_user', JSON.stringify(currentUser));
    enterApp();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.add('show');
  }
}

async function loadLoginStats() {
  try {
    const d = await api('/api/dashboard');
    const ps = document.getElementById('login-stat-partners');
    const pr = document.getElementById('login-stat-products');
    if (ps) ps.textContent = fmt(d.partners);
    if (pr) pr.textContent = fmt(d.products);
  } catch (e) {}
}

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('login-form').addEventListener('submit', (e) => { e.preventDefault(); doLogin(); });

  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => navigate(el.dataset.page));
  });

  // 검색 디바운스
  ['partner-search', 'product-search', 'stock-search', 'sales-search', 'order-search'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      let timer;
      el.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          if (id === 'partner-search') loadPartners();
          else if (id === 'product-search') loadProducts();
          else if (id === 'sales-search') loadSales();
          else if (id === 'order-search') loadOrders();
          else loadStock();
        }, 300);
      });
    }
  });

  (() => {
    const modalEl = document.getElementById('modal');
    let mdTarget = null;
    modalEl.addEventListener('mousedown', e => { mdTarget = e.target; });
    modalEl.addEventListener('click', e => {
      // 오버레이에서 "누르고 뗀" 경우에만 닫기 (입력칸 안에서 드래그 선택 시 닫힘 방지)
      if (e.target.classList.contains('modal-overlay') && mdTarget && mdTarget.classList.contains('modal-overlay')) closeModal();
    });
  })();

  document.getElementById('logout-btn').addEventListener('click', () => {
    currentUser = null;
    localStorage.removeItem('erp_user');
    document.getElementById('app').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('login-user').value = '';
    document.getElementById('login-pass').value = '';
    document.getElementById('login-error').classList.remove('show');
  });

  // 새로고침해도 로그인 유지 (localStorage 복원)
  try {
    const saved = localStorage.getItem('erp_user');
    if (saved) { currentUser = JSON.parse(saved); enterApp(); }
  } catch (e) { localStorage.removeItem('erp_user'); }

  loadLoginStats();
});


// ── 매출 분석 (2026-07-15) — /api/analysis/* · 정산 확정 데이터 ──
let _saMonthlyChart=null,_saGroupChart=null,_saDrillChart=null,_saData=null,_saDrillState={};
const _saWon=v=>v==null?'-':Math.round(v).toLocaleString();
const _saMan=v=>(v/10000).toLocaleString(undefined,{maximumFractionDigits:0})+'만';

async function loadSalesAnalysis(){
  const d=await api('/api/analysis/monthly');
  _saData=d;
  renderSaOverview();
  // 드릴다운 월 셀렉터
  const sel=document.getElementById('sa-drill-ym');
  sel.innerHTML=d.months.map(m=>`<option value="${m.ym}">${m.ym}</option>`).join('');
  sel.value=d.months[d.months.length-1].ym;
}

function switchSaView(v){
  ['overview','drill','plan'].forEach(x=>{
    document.getElementById('sa-view-'+x).classList.toggle('hidden',x!==v);
    document.getElementById('sav-'+x).classList.toggle('btn-primary',x===v);
  });
  if(v==='drill') saDrillChannels();
  if(v==='plan') loadSaPlan();
}

function renderSaOverview(){
  const ms=_saData.months;
  // 콤보차트: 매출 막대 + 순마진율 라인
  const c1=document.getElementById('sa-monthly-chart');
  if(_saMonthlyChart){_saMonthlyChart.destroy();}
  _saMonthlyChart=new Chart(c1,{type:'bar',
    data:{labels:ms.map(m=>m.ym.slice(5)+'월'),datasets:[
      {label:'총매출',data:ms.map(m=>m.revenue),backgroundColor:'#5b8def',borderRadius:6,yAxisID:'y'},
      {label:'순이익(VAT별도)',data:ms.map(m=>m.profit_net),backgroundColor:'#8fd19e',borderRadius:6,yAxisID:'y'},
      {label:'순마진율(%)',data:ms.map(m=>m.margin_net),type:'line',borderColor:'#e08a00',backgroundColor:'#e08a00',yAxisID:'y2',tension:.3}
    ]},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      scales:{y:{ticks:{callback:v=>_saMan(v)}},y2:{position:'right',grid:{display:false},min:0,max:70,ticks:{callback:v=>v+'%'}}},
      plugins:{tooltip:{callbacks:{label:ctx=>ctx.dataset.label+': '+(ctx.dataset.yAxisID==='y2'?ctx.raw+'%':_saWon(ctx.raw)+'원')}}}}});
  // 그룹 스택
  const groups=_saData.groups;const yms=ms.map(m=>m.ym);
  const palette={'자사몰':'#e58f8f','네이버':'#4caf7d','쿠팡':'#f0b35a','오픈마켓':'#8fa8e0','종합몰':'#b79ad1','수동발주':'#9aa5ad','기타':'#ccc'};
  const c2=document.getElementById('sa-group-chart');
  if(_saGroupChart){_saGroupChart.destroy();}
  _saGroupChart=new Chart(c2,{type:'bar',
    data:{labels:yms.map(y=>y.slice(5)+'월'),datasets:Object.keys(groups).map(g=>({label:g,data:yms.map(y=>groups[g][y]||0),backgroundColor:palette[g]||'#ccc',stack:'s'}))},
    options:{responsive:true,maintainAspectRatio:false,scales:{x:{stacked:true},y:{stacked:true,ticks:{callback:v=>_saMan(v)}}},
      plugins:{tooltip:{callbacks:{label:ctx=>ctx.dataset.label+': '+_saWon(ctx.raw)+'원'}}}}});
  // 월별 표
  let html='';let prev=null;
  ms.forEach(m=>{
    const mom=prev?((m.revenue-prev)/prev*100):null;
    html+=`<tr><td>${m.ym}</td><td class="text-right">${_saWon(m.revenue)}</td><td class="text-right">${_saWon(m.profit_gross)}</td><td class="text-right"><b>${_saWon(m.profit_net)}</b></td><td class="text-right">${m.margin_net}%</td><td class="text-right" style="color:${mom==null?'#999':mom>=0?'#1a8f3c':'#d63a3a'}">${mom==null?'-':(mom>=0?'+':'')+mom.toFixed(1)+'%'}</td></tr>`;
    prev=m.revenue;
  });
  document.getElementById('sa-monthly-tbody').innerHTML=html;
}

async function saDrillChannels(){
  const ym=document.getElementById('sa-drill-ym').value;
  _saDrillState={level:'channels',ym};
  const d=await api('/api/analysis/drill?ym='+ym);
  document.getElementById('sa-drill-crumb').textContent=ym+' · 채널별';
  document.getElementById('sa-drill-back').classList.add('hidden');
  document.getElementById('sa-drill-chartwrap').classList.add('hidden');
  document.getElementById('sa-drill-thead').innerHTML='<tr><th>채널</th><th>그룹</th><th class="text-right">수량</th><th class="text-right">총매출</th><th class="text-right">이익</th><th class="text-right">마진율</th><th class="text-right">전월 대비</th></tr>';
  document.getElementById('sa-drill-tbody').innerHTML=d.items.map(i=>
    `<tr style="cursor:pointer" onclick="saDrillProducts('${i.channel.replace(/'/g,"\\'")}')"><td><b>${i.channel}</b></td><td>${i.group}</td><td class="text-right">${_saWon(i.qty)}</td><td class="text-right">${_saWon(i.revenue)}</td><td class="text-right">${_saWon(i.profit)}</td><td class="text-right">${i.margin}%</td><td class="text-right" style="color:${i.rev_diff>=0?'#1a8f3c':'#d63a3a'}">${(i.rev_diff>=0?'+':'')+_saWon(i.rev_diff)}</td></tr>`).join('');
}

async function saDrillProducts(channel){
  const ym=_saDrillState.ym||document.getElementById('sa-drill-ym').value;
  _saDrillState={level:'products',ym,channel};
  const d=await api('/api/analysis/drill?ym='+ym+'&channel='+encodeURIComponent(channel));
  document.getElementById('sa-drill-crumb').textContent=ym+' · '+channel+' · 품목별';
  document.getElementById('sa-drill-back').classList.remove('hidden');
  document.getElementById('sa-drill-chartwrap').classList.add('hidden');
  document.getElementById('sa-drill-thead').innerHTML='<tr><th>품목</th><th class="text-right">수량</th><th class="text-right">매출</th><th class="text-right">원가</th><th class="text-right">이익</th><th class="text-right">마진율</th><th class="text-right">전월 대비</th></tr>';
  document.getElementById('sa-drill-tbody').innerHTML=d.items.map(i=>
    `<tr style="cursor:pointer" onclick="saDrillProduct('${i.product.replace(/'/g,"\\'")}')"><td>${i.product}</td><td class="text-right">${_saWon(i.qty)}</td><td class="text-right">${_saWon(i.revenue)}</td><td class="text-right">${_saWon(i.cost)}</td><td class="text-right">${_saWon(i.profit)}</td><td class="text-right">${i.margin}%</td><td class="text-right" style="color:${i.rev_diff>=0?'#1a8f3c':'#d63a3a'}">${(i.rev_diff>=0?'+':'')+_saWon(i.rev_diff)}</td></tr>`).join('');
}

async function saDrillProduct(product){
  _saDrillState={level:'product',ym:_saDrillState.ym,channel:_saDrillState.channel,product};
  const d=await api('/api/analysis/drill?product='+encodeURIComponent(product));
  document.getElementById('sa-drill-crumb').textContent='📦 '+product+' · 월×채널 추적';
  document.getElementById('sa-drill-back').classList.remove('hidden');
  document.getElementById('sa-drill-thead').innerHTML='<tr><th>월</th><th>채널</th><th class="text-right">수량</th><th class="text-right">매출</th><th class="text-right">이익</th></tr>';
  document.getElementById('sa-drill-tbody').innerHTML=d.items.map(i=>
    `<tr><td>${i.ym}</td><td>${i.channel}</td><td class="text-right">${_saWon(i.qty)}</td><td class="text-right">${_saWon(i.revenue)}</td><td class="text-right">${_saWon(i.profit)}</td></tr>`).join('');
  // 월합 차트
  const byYm={};d.items.forEach(i=>{byYm[i.ym]=(byYm[i.ym]||0)+i.revenue;});
  const yms=Object.keys(byYm).sort();
  document.getElementById('sa-drill-chartwrap').classList.remove('hidden');
  const cv=document.getElementById('sa-drill-chart');
  if(_saDrillChart){_saDrillChart.destroy();}
  _saDrillChart=new Chart(cv,{type:'bar',data:{labels:yms.map(y=>y.slice(5)+'월'),datasets:[{label:product+' 매출(전채널)',data:yms.map(y=>byYm[y]),backgroundColor:'#5b8def',borderRadius:6}]},
    options:{responsive:true,maintainAspectRatio:false,scales:{y:{ticks:{callback:v=>_saMan(v)}}},plugins:{tooltip:{callbacks:{label:ctx=>_saWon(ctx.raw)+'원'}}}}});
}

function saDrillBack(){
  if(_saDrillState.level==='product'&&_saDrillState.channel) saDrillProducts(_saDrillState.channel);
  else saDrillChannels();
}

async function loadSaPlan(){
  const f=await api('/api/analysis/forecast');
  const p=await api('/api/analysis/products');
  const card=(t,v,sub)=>`<div style="background:#fff;border:1px solid var(--line,#eceae6);border-radius:14px;padding:16px 18px"><div style="font-size:12px;color:#888">${t}</div><div style="font-size:22px;font-weight:700;margin:4px 0">${v}</div><div style="font-size:11px;color:#aaa">${sub||''}</div></div>`;
  const prog=(f.day/f.days_in_month*100).toFixed(0);
  document.getElementById('sa-plan-cards').innerHTML=
    card(`${f.ym} 누적 (잠정)`, _saMan(f.mtd)+'원', `${f.day}/${f.days_in_month}일 경과 (${prog}%)`)+
    card('월말 런레이트 전망', _saMan(f.runrate)+'원', '단순 일평균 × 월일수')+
    card(`최근 확정월 (${f.last_confirmed.ym})`, _saMan(f.last_confirmed.revenue)+'원', '순이익 '+_saMan(f.last_confirmed.profit_net)+'원')+
    card('전망 vs 전월 확정', ((f.runrate/f.last_confirmed.revenue-1)*100).toFixed(1)+'%', f.note);
  document.getElementById('sa-plan-tbody').innerHTML=p.items.slice(0,15).map(i=>
    `<tr style="cursor:pointer" onclick="switchSaView('drill');saDrillProduct('${i.product.replace(/'/g,"\\'")}')"><td>${i.product}</td><td class="text-right">${_saWon(i.qty)}</td><td class="text-right">${_saWon(i.revenue)}</td><td class="text-right">${_saWon(i.profit)}</td><td class="text-right">${i.revenue?(i.profit/i.revenue*100).toFixed(1):0}%</td></tr>`).join('');
}
