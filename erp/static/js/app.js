/* 비코어랩 ERP — 프론트엔드 */

const API = '';
let currentUser = null;
let currentPage = 'dashboard';

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
    users: '사용자 관리',
  }[page] || '';

  const loaders = {
    dashboard: loadDashboard,
    partners: loadPartners,
    products: loadProducts,
    stock: loadStock,
    sales: loadSales,
    orders: loadOrders,
  };
  if (loaders[page]) loaders[page]();
}

// ── Dashboard ──
async function loadDashboard() {
  try {
    const d = await api('/api/dashboard');
    document.getElementById('dash-partners').textContent = fmt(d.partners);
    document.getElementById('dash-products').textContent = fmt(d.products);
    document.getElementById('dash-lowstock').textContent = fmt(d.low_stock);
    document.getElementById('dash-today-sales').textContent = '₩' + fmt(d.today_sales);
    document.getElementById('dash-month-sales').textContent = '₩' + fmt(d.month_sales);
    document.getElementById('dash-pending-po').textContent = fmt(d.pending_po);
  } catch (e) {
    toast(e.message, 'error');
  }
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

// ── Stock ──
async function loadStock() {
  const q = document.getElementById('stock-search')?.value || '';
  const alertOnly = document.getElementById('stock-alert')?.checked || false;
  try {
    const items = await api(`/api/stock?q=${encodeURIComponent(q)}&alert_only=${alertOnly}`);
    const tbody = document.getElementById('stock-tbody');
    tbody.innerHTML = items.map(s => {
      const qty = s.qty_on_hand ?? 0;
      const safe = s.safety_stock || 0;
      let cls = '', badge = '';
      if (qty <= 0) { cls = 'text-danger'; badge = '<span class="badge badge-danger">품절</span>'; }
      else if (qty <= safe) { cls = 'text-warning'; badge = '<span class="badge badge-warning">부족</span>'; }
      else { badge = '<span class="badge badge-success">정상</span>'; }
      return `
      <tr>
        <td>${s.product_code}</td>
        <td><strong>${s.name}</strong></td>
        <td>${s.spec || '-'}</td>
        <td class="text-right number ${cls}">${fmt(qty)}</td>
        <td class="text-right number">${fmt(s.qty_reserved ?? 0)}</td>
        <td class="text-right number">${fmt(s.qty_available ?? qty)}</td>
        <td class="text-right number">${fmt(safe)}</td>
        <td>${badge}</td>
        <td>${s.last_synced_at || '-'}</td>
      </tr>`;
    }).join('');
    document.getElementById('stock-info').textContent = `총 ${items.length}건`;
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
    const d = await api(`/api/sales?date_from=${from}&date_to=${to}&channel=${encodeURIComponent(channel)}&q=${encodeURIComponent(q)}&page=${page}&size=50`);
    const tbody = document.getElementById('sales-tbody');
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
    document.getElementById('sales-info').textContent = `총 ${d.total}건`;
    const sumEl = document.getElementById('sales-sum');
    if (sumEl) sumEl.textContent = `합계 ₩${fmt(d.sum_amount)}`;
    renderPagination('sales-paging', d.total, 50, page, p => loadSales(p));
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
    const d = await api(`/api/purchase-orders?status=${status}&q=${encodeURIComponent(q)}&date_from=${from}&date_to=${to}&page=${page}&size=30`);
    const tbody = document.getElementById('orders-tbody');
    const statusMap = { draft: '작성중', confirmed: '확정', partial: '부분입고', completed: '완료', cancelled: '취소' };
    const badgeMap = { draft: 'default', confirmed: 'info', partial: 'warning', completed: 'success', cancelled: 'danger' };
    tbody.innerHTML = d.items.length ? d.items.map(o => `
      <tr onclick="viewOrder(${o.id})" style="cursor:pointer">
        <td><strong>${o.po_number}</strong></td>
        <td>${o.po_date}</td>
        <td>${o.supplier_name || '-'}</td>
        <td>${o.delivery_date || '-'}</td>
        <td class="text-right number">${fmt(o.total_amount)}</td>
        <td><span class="badge badge-${badgeMap[o.status]}">${statusMap[o.status]}</span></td>
      </tr>
    `).join('') : '<tr><td colspan="6" class="text-center text-muted" style="padding:40px">발주 데이터가 없습니다</td></tr>';
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

async function newOrder() {
  const suppliers = await api('/api/partners?type=supplier&size=200');
  const products = await api('/api/products?size=200');
  const m = document.getElementById('modal');
  m.querySelector('.modal-header span').textContent = '발주서 작성';
  m.querySelector('.modal-body').innerHTML = `
    <div class="form-row">
      <div class="form-group"><label>발주일</label><input type="date" id="m-podate" value="${new Date().toISOString().slice(0,10)}" /></div>
      <div class="form-group"><label>납품예정일</label><input type="date" id="m-podelivery" /></div>
    </div>
    <div class="form-group"><label>공급처</label>
      <select id="m-posupplier"><option value="">선택</option>${suppliers.items.map(s => `<option value="${s.id}">${s.name}</option>`).join('')}</select></div>
    <div class="form-group"><label>메모</label><textarea id="m-pomemo" rows="2"></textarea></div>
    <hr style="border-color:var(--border); margin:16px 0" />
    <div class="flex justify-between items-center mb-2">
      <strong>발주 품목</strong>
      <button class="btn btn-sm" onclick="addPOLine()">+ 품목 추가</button>
    </div>
    <div id="po-lines"></div>
  `;
  window._poProducts = products.items;
  m.querySelector('.modal-footer').innerHTML = `
    <button class="btn" onclick="closeModal()">취소</button>
    <button class="btn btn-primary" onclick="savePO()">발주 등록</button>`;
  openModal();
  addPOLine();
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
