#!/usr/bin/env python3
"""
iLBiA 소싱 매니저 — 알리바바 문의 발송 + 히스토리 관리

실행: python3 sourcing_app.py
접속: http://localhost:5000
"""

import sqlite3
import threading
import os
from flask import Flask, request, jsonify, render_template_string

# alibaba_search에서 핵심 함수 가져오기
from alibaba_search import (
    _get_headless_page_with_cookies,
    _find_storefront_url,
    _send_alibaba_inquiry,
)
from playwright.sync_api import sync_playwright

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sourcing.db')

# ── 메시지 템플릿 ──────────────────────────────────────────────────────────────
MESSAGE_TEMPLATE = """\
Dear {company} Team,

I hope this message finds you well.

My name is Kyle Chung, CEO of Becorelab Co., Ltd. (Korea) — brand: iLBiA. \
We sell household convenience products on Coupang, Naver Smart Store, and 11Street in Korea.

We are specifically interested in your product:
{product_link}

Our requirements:
- Target price : {target_price}
- Quantity     : {quantity} pcs (initial order)
- Specifications: {spec}

Could you please confirm:
1. Whether you can meet our target price at the requested quantity
2. MOQ (Minimum Order Quantity)
3. OEM/ODM options (custom logo, label, packaging)
4. Sample availability & shipping cost to Korea
5. Lead time & payment terms (T/T, L/C)
6. Product weight & carton dimensions
{extra_block}
Kindly reply to our email: kychung@becorelab.kr
We will respond promptly.

Best regards,
Kyle Chung
CEO, Becorelab Co., Ltd. | Brand: iLBiA
Email  : kychung@becorelab.kr
Website: www.ilbia.co.kr
Korea"""

# ── DB ────────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inquiries (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at     TEXT    DEFAULT (datetime('now','localtime')),
                alibaba_url    TEXT    NOT NULL,
                company        TEXT,
                target_price   TEXT,
                quantity       TEXT,
                spec           TEXT,
                extra_notes    TEXT,
                status         TEXT    DEFAULT 'pending',
                message_sent   TEXT,
                storefront_url TEXT,
                error_msg      TEXT
            )
        """)
        conn.commit()

# ── 백그라운드 발송 ────────────────────────────────────────────────────────────
def _update_db(inquiry_id, status, **kwargs):
    with get_db() as conn:
        sets = ['status = ?']
        vals = [status]
        for k, v in kwargs.items():
            sets.append(f'{k} = ?')
            vals.append(v)
        vals.append(inquiry_id)
        conn.execute(f"UPDATE inquiries SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()

def _send_in_background(inquiry_id: int, data: dict):
    extra = data.get('extra_notes', '').strip()
    extra_block = f"\n{extra}\n" if extra else ''

    company  = data.get('company', '') or ''
    target_p = data.get('target_price', '') or '-'
    quantity = data.get('quantity', '') or '-'
    spec     = data.get('spec', '') or '-'

    message = MESSAGE_TEMPLATE.format(
        company=company or 'Team',
        product_link=data['alibaba_url'],
        target_price=target_p,
        quantity=quantity,
        spec=spec,
        extra_block=extra_block,
    )

    try:
        with sync_playwright() as p:
            browser, ctx, page = _get_headless_page_with_cookies(p)
            try:
                storefront = _find_storefront_url(page, company, data['alibaba_url'])
                if not storefront:
                    _update_db(inquiry_id, 'failed', error_msg='스토어 URL을 찾을 수 없음')
                    return

                # company가 없으면 storefront URL에서 추출
                display_company = company
                if not display_company and storefront:
                    slug = storefront.split('.en.alibaba.com')[0].split('/')[-1]
                    display_company = slug.capitalize()
                    with get_db() as conn:
                        conn.execute('UPDATE inquiries SET company = ? WHERE id = ?',
                                     (display_company, inquiry_id))
                        conn.commit()

                ok, reason = _send_alibaba_inquiry(
                    page, display_company or 'Team', storefront, message
                )
                if ok:
                    _update_db(inquiry_id, 'sent',
                               storefront_url=storefront, message_sent=message)
                else:
                    _update_db(inquiry_id, 'failed',
                               storefront_url=storefront, error_msg=reason)
            finally:
                browser.close()
    except Exception as e:
        _update_db(inquiry_id, 'failed', error_msg=str(e))

# ── API ───────────────────────────────────────────────────────────────────────
@app.route('/api/send', methods=['POST'])
def api_send():
    data = request.json or {}
    if not data.get('alibaba_url'):
        return jsonify({'error': 'URL 필수'}), 400

    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO inquiries
              (alibaba_url, company, target_price, quantity, spec, extra_notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get('alibaba_url'),
            data.get('company', ''),
            data.get('target_price', ''),
            data.get('quantity', ''),
            data.get('spec', ''),
            data.get('extra_notes', ''),
        ))
        inquiry_id = cur.lastrowid
        conn.commit()

    t = threading.Thread(target=_send_in_background,
                         args=(inquiry_id, data), daemon=True)
    t.start()
    return jsonify({'id': inquiry_id, 'status': 'pending'})


@app.route('/api/history')
def api_history():
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM inquiries ORDER BY created_at DESC'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/inquiry/<int:inquiry_id>')
def api_inquiry_detail(inquiry_id):
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM inquiries WHERE id = ?', (inquiry_id,)
        ).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@app.route('/api/status/<int:inquiry_id>')
def api_status(inquiry_id):
    with get_db() as conn:
        row = conn.execute(
            'SELECT status, error_msg FROM inquiries WHERE id = ?', (inquiry_id,)
        ).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@app.route('/api/update_status', methods=['POST'])
def api_update_status():
    data = request.json or {}
    allowed = ['replied', 'ordered', 'cancelled', 'sent']
    if data.get('status') not in allowed:
        return jsonify({'error': '유효하지 않은 상태'}), 400
    with get_db() as conn:
        conn.execute('UPDATE inquiries SET status = ? WHERE id = ?',
                     (data['status'], data['id']))
        conn.commit()
    return jsonify({'ok': True})


# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>iLBiA 소싱 매니저</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --mint: #3ecfb2; --mint-d: #2ab89d;
  --bg: #f3f7f6; --card: #fff; --border: #e2e8f0;
  --text: #1a2332; --muted: #64748b;
  --red: #ef4444; --yellow: #f59e0b;
  --blue: #3b82f6; --green: #10b981; --purple: #8b5cf6;
}
body { font-family: -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
       background: var(--bg); color: var(--text); font-size: 14px; }

header { background: #fff; border-bottom: 2px solid var(--mint);
         padding: 0 28px; display: flex; align-items: center;
         gap: 28px; height: 58px; position: sticky; top: 0; z-index: 50;
         box-shadow: 0 1px 6px rgba(62,207,178,.12); }
.logo { font-size: 1.2rem; font-weight: 900; color: var(--mint);
        letter-spacing: -0.5px; }
.logo span { color: var(--text); }

.tabs { display: flex; gap: 4px; }
.tab { padding: 7px 18px; border-radius: 20px; cursor: pointer; font-weight: 600;
       color: var(--muted); border: none; background: none; font-size: 14px;
       font-family: inherit; transition: all .2s; }
.tab.active { background: var(--mint); color: #fff; }
.tab:hover:not(.active) { background: #e8faf6; color: var(--mint); }

main { max-width: 860px; margin: 32px auto; padding: 0 24px; }

.card { background: var(--card); border: 1px solid var(--border);
        border-radius: 14px; padding: 28px; margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,.04); }

.section-title { font-size: 15px; font-weight: 700; margin-bottom: 20px;
                 color: var(--text); display: flex; align-items: center; gap: 8px; }
.section-title::before { content:''; display:block; width:4px; height:18px;
                          background:var(--mint); border-radius:2px; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group.full { grid-column: 1 / -1; }
label { font-size: 12px; font-weight: 700; color: var(--muted);
        letter-spacing: .3px; text-transform: uppercase; }
input, textarea, select {
  border: 1.5px solid var(--border); border-radius: 8px;
  padding: 10px 13px; font-size: 14px; font-family: inherit;
  outline: none; transition: border-color .2s; background: #fff; }
input:focus, textarea:focus { border-color: var(--mint);
  box-shadow: 0 0 0 3px rgba(62,207,178,.12); }
textarea { resize: vertical; min-height: 80px; }
input::placeholder, textarea::placeholder { color: #b0bec5; }

.btn { padding: 11px 24px; border-radius: 8px; border: none; cursor: pointer;
       font-size: 14px; font-weight: 700; font-family: inherit; transition: all .2s; }
.btn-primary { background: var(--mint); color: #fff; }
.btn-primary:hover { background: var(--mint-d); transform: translateY(-1px); }
.btn-primary:disabled { opacity:.5; cursor:not-allowed; transform:none; }
.btn-sm { padding: 5px 12px; font-size: 12px; border-radius: 6px; }
.btn-outline { background: #fff; border: 1.5px solid var(--border); color: var(--muted); }
.btn-outline:hover { border-color: var(--mint); color: var(--mint); }

.status-bar { padding: 12px 16px; border-radius: 8px; margin-top: 16px;
              font-weight: 600; display: none; }
.status-bar.sending { display:block; background:#dbeafe; color:#2563eb; }
.status-bar.success { display:block; background:#d1fae5; color:#059669; }
.status-bar.error   { display:block; background:#fee2e2; color:#dc2626; }

.badge { display:inline-block; padding:3px 10px; border-radius:20px;
         font-size:11px; font-weight:700; }
.badge-pending    { background:#fef3c7; color:#d97706; }
.badge-sent       { background:#dbeafe; color:#2563eb; }
.badge-replied    { background:#d1fae5; color:#059669; }
.badge-ordered    { background:#ede9fe; color:#7c3aed; }
.badge-failed     { background:#fee2e2; color:#dc2626; }
.badge-cancelled  { background:#f1f5f9; color:#94a3b8; }

table { width:100%; border-collapse:collapse; }
th { text-align:left; padding:10px 12px; font-size:11px; font-weight:700;
     color:var(--muted); border-bottom:2px solid var(--border);
     letter-spacing:.3px; text-transform:uppercase; }
td { padding:12px; border-bottom:1px solid var(--border); vertical-align:middle; }
tr:hover td { background:#f8fafb; }
td a { color:var(--mint); text-decoration:none; }
td a:hover { text-decoration:underline; }

.modal-overlay { display:none; position:fixed; inset:0;
                 background:rgba(0,0,0,.4); z-index:100;
                 align-items:center; justify-content:center; }
.modal-overlay.open { display:flex; }
.modal { background:#fff; border-radius:16px; padding:28px;
         width:640px; max-width:92vw; max-height:82vh; overflow-y:auto; }
.modal-header { display:flex; justify-content:space-between;
                align-items:center; margin-bottom:20px; }
.modal-close { background:none; border:none; cursor:pointer;
               font-size:22px; color:var(--muted); line-height:1; }

.detail-row { display:flex; gap:14px; padding:9px 0;
              border-bottom:1px solid var(--border); }
.detail-label { width:110px; font-weight:700; color:var(--muted);
                font-size:12px; flex-shrink:0; padding-top:1px; }
.detail-value { flex:1; word-break:break-all; line-height:1.5; }
pre.msg-preview { background:#f8fafb; border:1px solid var(--border);
                  border-radius:8px; padding:14px; font-size:12px;
                  white-space:pre-wrap; overflow-y:auto; max-height:220px;
                  font-family:monospace; margin-top:8px; }

.page { display:none; }
.page.active { display:block; }

.empty { text-align:center; padding:52px; color:var(--muted); font-size:15px; }
.toolbar { display:flex; justify-content:space-between; align-items:center;
           margin-bottom:20px; }
.hint { font-size:12px; color:var(--muted); margin-top:6px; }

.stat-row { display:flex; gap:12px; margin-bottom:20px; flex-wrap:wrap; }
.stat { flex:1; min-width:100px; background:var(--card);
        border:1px solid var(--border); border-radius:10px;
        padding:14px 16px; text-align:center; }
.stat-num { font-size:22px; font-weight:900; color:var(--mint); }
.stat-label { font-size:11px; color:var(--muted); margin-top:2px; font-weight:600; }
</style>
</head>
<body>

<header>
  <span class="logo">iLBiA <span>소싱 매니저</span></span>
  <div class="tabs">
    <button class="tab active" id="tab-new" onclick="switchTab('new', this)">새 문의</button>
    <button class="tab" id="tab-history" onclick="switchTab('history', this)">히스토리</button>
  </div>
</header>

<main>

  <!-- ── 새 문의 탭 ── -->
  <div id="page-new" class="page active">
    <div class="card">
      <div class="section-title">알리바바 업체 문의 발송</div>
      <div class="form-grid">
        <div class="form-group full">
          <label>알리바바 제품 URL *</label>
          <input type="url" id="alibaba_url"
                 placeholder="https://www.alibaba.com/product-detail/...">
          <span class="hint">문의할 알리바바 제품 페이지 URL을 붙여넣으세요.</span>
        </div>
        <div class="form-group full">
          <label>업체명 (선택 — 비워두면 자동 감지)</label>
          <input type="text" id="company"
                 placeholder="예: Shanghai Condibe Hardware Co., Ltd.">
        </div>
        <div class="form-group">
          <label>타겟 단가</label>
          <input type="text" id="target_price"
                 placeholder="예: USD 0.5~1.0 / pcs (FOB)">
        </div>
        <div class="form-group">
          <label>수량 (초도발주 기준)</label>
          <input type="text" id="quantity"
                 placeholder="예: 1,000">
        </div>
        <div class="form-group full">
          <label>규격 / 사이즈 / 색상</label>
          <input type="text" id="spec"
                 placeholder="예: 50×50mm, White, Custom Logo Print">
        </div>
        <div class="form-group full">
          <label>추가 요청사항</label>
          <textarea id="extra_notes"
                    placeholder="예: Please send a sample before bulk order. We need custom packaging with Korean labels."></textarea>
        </div>
      </div>
      <div style="margin-top:22px; display:flex; align-items:center; gap:16px;">
        <button class="btn btn-primary" id="send-btn" onclick="sendInquiry()">
          문의 발송
        </button>
        <span style="color:var(--muted); font-size:13px;">
          헤드리스 브라우저로 자동 발송 · 히스토리에 자동 저장됩니다
        </span>
      </div>
      <div class="status-bar" id="status-bar"></div>
    </div>
  </div>

  <!-- ── 히스토리 탭 ── -->
  <div id="page-history" class="page">
    <div id="stat-row" class="stat-row"></div>
    <div class="card">
      <div class="toolbar">
        <div class="section-title" style="margin-bottom:0;">문의 히스토리</div>
        <button class="btn btn-outline btn-sm" onclick="loadHistory()">새로고침</button>
      </div>
      <div id="history-content">
        <div class="empty">로딩 중...</div>
      </div>
    </div>
  </div>

</main>

<!-- 상세 모달 -->
<div class="modal-overlay" id="modal" onclick="closeModal(event)">
  <div class="modal">
    <div class="modal-header">
      <h3 style="font-size:16px; font-weight:700;">문의 상세</h3>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div id="modal-body"></div>
  </div>
</div>

<script>
const STATUS_LABEL = {
  pending:'대기중', sent:'발송완료', replied:'회신받음',
  ordered:'발주완료', failed:'실패', cancelled:'취소'
};

function switchTab(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  el.classList.add('active');
  if (name === 'history') loadHistory();
}

/* ── 발송 ── */
async function sendInquiry() {
  const url = document.getElementById('alibaba_url').value.trim();
  if (!url) { alert('알리바바 URL을 입력해주세요.'); return; }

  const btn = document.getElementById('send-btn');
  const bar = document.getElementById('status-bar');
  btn.disabled = true;
  bar.className = 'status-bar sending';
  bar.textContent = '⏳ 발송 중… 헤드리스 브라우저 실행 중입니다.';

  const payload = {
    alibaba_url  : url,
    company      : document.getElementById('company').value.trim(),
    target_price : document.getElementById('target_price').value.trim(),
    quantity     : document.getElementById('quantity').value.trim(),
    spec         : document.getElementById('spec').value.trim(),
    extra_notes  : document.getElementById('extra_notes').value.trim(),
  };

  try {
    const res  = await fetch('/api/send', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    pollStatus(data.id, btn, bar);
  } catch(e) {
    bar.className = 'status-bar error';
    bar.textContent = '❌ 오류: ' + e.message;
    btn.disabled = false;
  }
}

async function pollStatus(id, btn, bar) {
  for (let i = 0; i < 80; i++) {
    await new Promise(r => setTimeout(r, 3000));
    const res  = await fetch('/api/status/' + id);
    const data = await res.json();
    if (data.status === 'sent') {
      bar.className = 'status-bar success';
      bar.textContent = '✅ 발송 완료! 히스토리에서 확인하세요.';
      btn.disabled = false; return;
    } else if (data.status === 'failed') {
      bar.className = 'status-bar error';
      bar.textContent = '❌ 실패: ' + (data.error_msg || '알 수 없는 오류');
      btn.disabled = false; return;
    }
  }
  bar.className = 'status-bar error';
  bar.textContent = '⚠️ 시간 초과 — 히스토리에서 상태 확인해주세요.';
  btn.disabled = false;
}

/* ── 히스토리 ── */
async function loadHistory() {
  const res  = await fetch('/api/history');
  const rows = await res.json();

  // 통계
  const counts = {pending:0,sent:0,replied:0,ordered:0,failed:0,cancelled:0};
  rows.forEach(r => { if (counts[r.status] !== undefined) counts[r.status]++; });
  document.getElementById('stat-row').innerHTML = `
    <div class="stat"><div class="stat-num">${rows.length}</div><div class="stat-label">전체</div></div>
    <div class="stat"><div class="stat-num" style="color:#2563eb;">${counts.sent}</div><div class="stat-label">발송완료</div></div>
    <div class="stat"><div class="stat-num" style="color:#059669;">${counts.replied}</div><div class="stat-label">회신받음</div></div>
    <div class="stat"><div class="stat-num" style="color:#7c3aed;">${counts.ordered}</div><div class="stat-label">발주완료</div></div>
    <div class="stat"><div class="stat-num" style="color:#dc2626;">${counts.failed}</div><div class="stat-label">실패</div></div>
  `;

  if (!rows.length) {
    document.getElementById('history-content').innerHTML =
      '<div class="empty">아직 문의 내역이 없습니다.</div>';
    return;
  }

  document.getElementById('history-content').innerHTML = `
    <table>
      <thead><tr>
        <th>#</th>
        <th>날짜</th>
        <th>업체명</th>
        <th>제품</th>
        <th>단가</th>
        <th>수량</th>
        <th>상태</th>
        <th>변경</th>
      </tr></thead>
      <tbody>
        ${rows.map(r => `
          <tr onclick="showDetail(${r.id})" style="cursor:pointer;">
            <td style="color:var(--muted); font-size:12px;">${r.id}</td>
            <td style="white-space:nowrap; font-size:12px; color:var(--muted);">
              ${r.created_at.slice(0,16).replace('T',' ')}</td>
            <td style="max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              ${r.company || '<span style="color:#b0bec5;">감지중</span>'}</td>
            <td><a href="${r.alibaba_url}" target="_blank"
                   onclick="event.stopPropagation()">링크 ↗</a></td>
            <td style="white-space:nowrap;">${r.target_price || '-'}</td>
            <td>${r.quantity || '-'}</td>
            <td><span class="badge badge-${r.status}">${STATUS_LABEL[r.status]||r.status}</span></td>
            <td onclick="event.stopPropagation()">
              <select onchange="updateStatus(${r.id}, this.value)"
                      style="font-size:12px; padding:4px 6px; border:1.5px solid var(--border);
                             border-radius:6px; font-family:inherit; cursor:pointer;">
                <option value="">변경</option>
                <option value="replied">회신받음</option>
                <option value="ordered">발주완료</option>
                <option value="cancelled">취소</option>
              </select>
            </td>
          </tr>`).join('')}
      </tbody>
    </table>
  `;
}

/* ── 상세 ── */
async function showDetail(id) {
  const res = await fetch('/api/inquiry/' + id);
  const r   = await res.json();
  document.getElementById('modal-body').innerHTML = `
    <div class="detail-row">
      <span class="detail-label">상태</span>
      <span><span class="badge badge-${r.status}">${STATUS_LABEL[r.status]||r.status}</span></span>
    </div>
    <div class="detail-row">
      <span class="detail-label">업체명</span>
      <span class="detail-value">${r.company||'-'}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">제품 URL</span>
      <span class="detail-value">
        <a href="${r.alibaba_url}" target="_blank">${r.alibaba_url}</a>
      </span>
    </div>
    <div class="detail-row">
      <span class="detail-label">스토어</span>
      <span class="detail-value">
        ${r.storefront_url
          ? `<a href="${r.storefront_url}" target="_blank">${r.storefront_url}</a>`
          : '-'}
      </span>
    </div>
    <div class="detail-row">
      <span class="detail-label">타겟 단가</span>
      <span class="detail-value">${r.target_price||'-'}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">수량</span>
      <span class="detail-value">${r.quantity||'-'}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">규격</span>
      <span class="detail-value">${r.spec||'-'}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">추가요청</span>
      <span class="detail-value">${r.extra_notes||'-'}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">발송일시</span>
      <span class="detail-value" style="font-size:12px;">${r.created_at}</span>
    </div>
    ${r.error_msg ? `
    <div class="detail-row">
      <span class="detail-label">오류</span>
      <span class="detail-value" style="color:var(--red);">${r.error_msg}</span>
    </div>` : ''}
    ${r.message_sent ? `
    <div style="margin-top:14px;">
      <div style="font-size:12px; font-weight:700; color:var(--muted); margin-bottom:4px;">
        발송된 메시지
      </div>
      <pre class="msg-preview">${r.message_sent.replace(/</g,'&lt;')}</pre>
    </div>` : ''}
  `;
  document.getElementById('modal').classList.add('open');
}

async function updateStatus(id, status) {
  if (!status) return;
  await fetch('/api/update_status', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({id, status})
  });
  loadHistory();
}

function closeModal(e) {
  if (!e || e.target === document.getElementById('modal'))
    document.getElementById('modal').classList.remove('open');
}
</script>
</body>
</html>"""


@app.route('/')
def index():
    return render_template_string(HTML)


if __name__ == '__main__':
    init_db()
    print()
    print('  iLBiA 소싱 매니저 실행 중')
    print('  브라우저에서 열기 → http://localhost:5000')
    print()
    app.run(debug=False, port=5000, threaded=True)
