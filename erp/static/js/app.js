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
    calendar: '일정 관리',
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
    calendar: loadCalendar,
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
async function loadStock() {
  const q = document.getElementById('stock-search')?.value || '';
  const alertOnly = document.getElementById('stock-alert')?.checked || false;
  const hideZero = document.getElementById('stock-hide-zero')?.checked || false;
  const showMaterial = document.getElementById('stock-show-material')?.checked || false;
  try {
    const [items_raw, summary] = await Promise.all([
      api(`/api/stock?q=${encodeURIComponent(q)}&alert_only=${alertOnly}&show_material=${showMaterial}`),
      api('/api/stock/summary'),
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
            ${renderCardItems(pendingInbound, s => `<span class="stock-dash-badge stock-dash-badge-inbound">+${fmt(s.pending_inbound)}</span>`, '<span style="color:var(--ink-3)">예정 없음</span>')}
          </div>
        </div>`;
    }

    const tbody = document.getElementById('stock-tbody');
    tbody.innerHTML = classified.map(s => {
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

      const qtyColor = s.status === 'out' ? 'var(--red)' : s.status === 'danger' || s.status === 'low' ? 'var(--amber)' : 'var(--ink)';

      const discBadge = s.is_discontinued ? ' <span class="badge" style="background:var(--ink-4);color:var(--ink-2);font-size:10px">단종</span>' : '';

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
        <td onclick="viewStockDetail(${s.id})" class="text-right">${depletionText}</td>
        <td onclick="viewStockDetail(${s.id})">${badge}</td>
        <td><button class="btn btn-sm" onclick="event.stopPropagation();viewStockLedger(${s.id},'${(s.name||'').replace(/'/g,"\\'")}')">수불부</button></td>
      </tr>`;
    }).join('');
    document.getElementById('stock-info').textContent = `총 ${items.length}건`;
  } catch (e) { toast(e.message, 'error'); }
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
        <thead><tr><th>기간</th><th class="text-right">출고수량</th><th class="text-right">금액</th></tr></thead>
        <tbody>${items.map(t => `<tr>
          <td>${t.period}</td>
          <td class="text-right number">${fmt(t.qty)}</td>
          <td class="text-right number">₩${fmt(t.amount)}</td>
        </tr>`).join('')}</tbody>
      </table>` : '<div class="empty-state"><p>최근 90일 출고 이력이 없습니다</p></div>'}
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
      thead.innerHTML = '<tr><th>매출일</th><th>채널</th><th class="text-right">건수</th><th class="text-right">공급가</th><th class="text-right">세액</th><th class="text-right">합계</th></tr>';
      tbody.innerHTML = d.items.length ? d.items.map(s => `
        <tr>
          <td>${s.sale_date}</td>
          <td><strong>${s.channel || '-'}</strong></td>
          <td class="text-right number">${s.item_count}건</td>
          <td class="text-right number">${fmt(s.total_supply)}</td>
          <td class="text-right number">${fmt(s.total_tax)}</td>
          <td class="text-right number"><strong>${fmt(s.total_amount)}</strong></td>
        </tr>
      `).join('') : '<tr><td colspan="6" class="text-center text-muted" style="padding:40px">데이터 없음</td></tr>';
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
    tbody.innerHTML = data.length ? data.map(r => {
      return `<tr>
        <td><strong>${r.label || '-'}</strong></td>
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

async function loadOrders(page = 1) {
  ordersPage = page;
  initOrderFilters();
  const status = document.getElementById('order-status')?.value || '';
  const q = document.getElementById('order-search')?.value || '';
  const from = document.getElementById('order-from')?.value || '';
  const to = document.getElementById('order-to')?.value || '';
  try {
    const sort = document.getElementById('order-sort')?.value || 'date_desc';
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
        <td class="text-right number">${fmt(o.total_amount)}</td>
        <td><span class="badge badge-${badgeMap[o.status]}">${statusMap[o.status]}</span></td>
      </tr>`;
    }).join('') : '<tr><td colspan="7" class="text-center text-muted" style="padding:40px">발주 데이터가 없습니다</td></tr>';
    document.getElementById('orders-info').textContent = `총 ${d.total}건`;
    const sumEl = document.getElementById('orders-sum');
    if (sumEl) sumEl.textContent = `합계 ₩${fmt(d.sum_amount)}`;
    renderPagination('orders-paging', d.total, 30, page, p => loadOrders(p));
  } catch (e) { toast(e.message, 'error'); }
}

async function viewOrder(id) {
  try {
    const d = await api(`/api/purchase-orders/${id}`);
    const statusMap = { draft: '작성중', confirmed: '확정', partial: '부분입고', completed: '완료', cancelled: '취소' };
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
        <thead><tr><th>품목</th><th class="text-right">발주량</th><th class="text-right">입고량</th><th class="text-right">단가</th><th class="text-right">금액</th></tr></thead>
        <tbody>${d.lines.map(l => `
          <tr><td>${l.product_name || l.product_code}</td>
          <td class="text-right number">${fmt(l.qty_ordered)}</td>
          <td class="text-right number">${fmt(l.qty_received)}</td>
          <td class="text-right number">${fmt(l.unit_price)}</td>
          <td class="text-right number">${fmt(l.amount)}</td></tr>
        `).join('')}</tbody>
      </table>
      ${d.po.memo ? `<div class="mt-2"><span class="text-muted">메모</span><br>${d.po.memo}</div>` : ''}
    `;
    m.querySelector('.modal-footer').innerHTML = `
      <button class="btn" onclick="closeModal()">닫기</button>
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
    closeModal();
    loadOrders(ordersPage);
  } catch (e) { toast(e.message, 'error'); }
}

async function copyPO(id) {
  try {
    const r = await api(`/api/purchase-orders/${id}/copy`, { method: 'POST' });
    toast(`발주서 복사 완료: ${r.po_number}`);
    closeModal();
    loadOrders();
  } catch (e) { toast(e.message, 'error'); }
}

function downloadPOPdf(id) {
  window.open(`/api/purchase-orders/${id}/pdf`, '_blank');
}

async function emailPO(id) {
  try {
    const d = await api(`/api/purchase-orders/${id}`);
    let contacts = [];
    if (d.po.supplier_id) {
      try { contacts = await api(`/api/partners/${d.po.supplier_id}/contacts`); } catch(e) {}
    }
    const m = document.getElementById('modal');
    const toContacts = contacts.filter(c => c.contact_type === 'to');
    const ccContacts = contacts.filter(c => c.contact_type === 'cc');

    m.querySelector('.modal-header span').textContent = `발주서 이메일 발송 — ${d.po.po_number}`;
    m.querySelector('.modal-body').innerHTML = `
      <div class="form-group">
        <label>수신 (To)</label>
        ${toContacts.length ? toContacts.map(c => `
          <label style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer">
            <input type="checkbox" class="email-to" value="${c.email}" checked />
            <span>${c.name}</span> <span class="text-muted" style="font-size:12px">${c.email}</span>
          </label>`).join('') : ''}
        <input type="email" id="email-to-custom" placeholder="직접 입력..." style="margin-top:4px" />
      </div>
      <div class="form-group">
        <label>참조 (Cc)</label>
        ${ccContacts.length ? ccContacts.map(c => `
          <label style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer">
            <input type="checkbox" class="email-cc" value="${c.email}" checked />
            <span>${c.name}</span> <span class="text-muted" style="font-size:12px">${c.email}</span>
          </label>`).join('') : '<span class="text-muted" style="font-size:13px">없음</span>'}
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

async function sendPOEmail(id) {
  const checked = document.querySelectorAll('.email-to:checked');
  const custom = document.getElementById('email-to-custom')?.value?.trim();
  const toList = [...checked].map(c => c.value);
  if (custom) toList.push(custom);
  if (!toList.length) return toast('수신 이메일을 선택하세요', 'error');

  try {
    await api(`/api/purchase-orders/${id}/email`, { method: 'POST', body: { to: toList[0] } });
    toast(`발주서 발송 완료`);
    closeModal();
  } catch (e) { toast(e.message, 'error'); }
}

let _orderDebounceTimer;
function debounceLoadOrders() {
  clearTimeout(_orderDebounceTimer);
  _orderDebounceTimer = setTimeout(() => loadOrders(), 300);
}

async function newOrder() {
  const suppliers = await api('/api/partners?type=supplier&size=200');
  const products = await api('/api/products?size=200');
  window._allSuppliers = suppliers.items;
  window._poProducts = products.items;
  const m = document.getElementById('modal');
  m.querySelector('.modal-header span').textContent = '발주서 작성';
  m.querySelector('.modal-body').innerHTML = `
    <div class="form-row">
      <div class="form-group"><label>발주일</label><input type="date" id="m-podate" value="${new Date().toISOString().slice(0,10)}" /></div>
      <div class="form-group"><label>납품예정일</label><input type="date" id="m-podelivery" /></div>
    </div>
    <div class="form-group"><label>공급처</label>
      <div class="autocomplete-wrap">
        <input type="text" id="m-posupplier-search" placeholder="공급처명 검색..." autocomplete="off" />
        <input type="hidden" id="m-posupplier" />
        <div class="autocomplete-list" id="supplier-autocomplete"></div>
      </div>
    </div>
    <div class="form-group"><label>메모</label><textarea id="m-pomemo" rows="2"></textarea></div>
    <hr style="border-color:var(--line); margin:16px 0" />
    <div class="flex justify-between items-center mb-2">
      <strong>발주 품목</strong>
      <button class="btn btn-sm" onclick="addPOLine()">+ 품목 추가</button>
    </div>
    <div id="po-lines"></div>
  `;
  initSupplierAutocomplete();
  m.querySelector('.modal-footer').innerHTML = `
    <button class="btn" onclick="closeModal()">취소</button>
    <button class="btn btn-primary" onclick="savePO()">발주 등록</button>`;
  openModal();
  addPOLine();
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

function addPOLine() {
  const container = document.getElementById('po-lines');
  const idx = container.children.length;
  const div = document.createElement('div');
  div.className = 'form-row mb-2';
  div.style.alignItems = 'end';
  div.innerHTML = `
    <div class="form-group" style="flex:2"><label>품목</label>
      <select class="po-product"><option value="">선택</option>${(window._poProducts || []).map(p => `<option value="${p.id}" data-price="${p.purchase_price}">${p.name} (${p.product_code})</option>`).join('')}</select></div>
    <div class="form-group" style="flex:1"><label>수량</label><input type="number" class="po-qty" value="1" min="1" /></div>
    <div class="form-group" style="flex:1"><label>단가</label><input type="number" class="po-price" value="0" /></div>
    <button class="btn btn-sm btn-danger" onclick="this.parentElement.remove()" style="margin-bottom:16px">X</button>
  `;
  div.querySelector('.po-product').addEventListener('change', function() {
    const opt = this.options[this.selectedIndex];
    div.querySelector('.po-price').value = opt.dataset.price || 0;
  });
  container.appendChild(div);
}

async function savePO() {
  const lines = [];
  document.querySelectorAll('#po-lines > div').forEach(row => {
    const productId = row.querySelector('.po-product').value;
    const productName = row.querySelector('.po-product').options[row.querySelector('.po-product').selectedIndex]?.text || '';
    const qty = Number(row.querySelector('.po-qty').value);
    const price = Number(row.querySelector('.po-price').value);
    if (productId && qty > 0) lines.push({ product_id: Number(productId), product_name: productName, qty_ordered: qty, unit_price: price });
  });
  if (!lines.length) return toast('품목을 추가해주세요', 'error');
  const supplierId = document.getElementById('m-posupplier').value;
  if (!supplierId) return toast('공급처를 선택해주세요', 'error');

  try {
    const r = await api('/api/purchase-orders', { method: 'POST', body: {
      po_date: document.getElementById('m-podate').value,
      delivery_date: document.getElementById('m-podelivery').value,
      supplier_id: Number(supplierId),
      memo: document.getElementById('m-pomemo').value,
      lines,
    }});
    toast(`발주서 ${r.po_number} 등록 완료`);
    closeModal();
    loadOrders();
  } catch (e) { toast(e.message, 'error'); }
}

// ── Modal ──
function openModal() { document.getElementById('modal').classList.add('show'); }
function closeModal() { document.getElementById('modal').classList.remove('show'); }

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
    const dayClass = dow === 0 ? 'sun' : dow === 6 ? 'sat' : '';
    return `<div class="cal-cell ${c.other ? 'other-month' : ''} ${iso === todayIso ? 'today' : ''}" onclick="editEvent(0,'${iso}')">
      <div class="cal-daynum ${dayClass}">${c.d}</div>
      ${shown.map(ev => `<div class="cal-event type-${ev.event_type}" onclick="event.stopPropagation();${ev.readonly ? `toast('발주 입고 일정이에요 (발주 메뉴에서 관리)','warning')` : `editEvent(${ev.id})`}" title="${(ev.title || '').replace(/"/g, '')}">${ev.title}</div>`).join('')}
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
      <input id="ev-title" value="${ev ? (ev.title || '').replace(/"/g, '&quot;') : ''}" placeholder="예: 박성락님 연차 / 거래처 미팅" /></div>
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
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');
    document.getElementById('user-name').textContent = currentUser.name;
    navigate('dashboard');
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

  document.getElementById('modal').addEventListener('click', e => {
    if (e.target.classList.contains('modal-overlay')) closeModal();
  });

  document.getElementById('logout-btn').addEventListener('click', () => {
    currentUser = null;
    document.getElementById('app').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('login-user').value = '';
    document.getElementById('login-pass').value = '';
    document.getElementById('login-error').classList.remove('show');
  });

  loadLoginStats();
});
