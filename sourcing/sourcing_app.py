#!/usr/bin/env python3
"""
비코어랩 소싱 매니저 — 알리바바 문의 발송 + 히스토리 관리

실행: python3 sourcing_app.py
접속: http://localhost:8080
"""

import sqlite3
import threading
import os
import csv
import io
import subprocess
import requests
from flask import Flask, request, jsonify, render_template_string, Response, send_from_directory

# alibaba_search에서 핵심 함수 가져오기
from alibaba_search import (
    _get_headless_page_with_cookies,
    _find_storefront_url,
    _send_alibaba_inquiry,
)
from playwright.sync_api import sync_playwright

app = Flask(__name__)
DB_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sourcing.db')
THUMB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'thumbnails')

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

# ── macOS 알림 ─────────────────────────────────────────────────────────────────
def _notify(title: str, message: str):
    try:
        subprocess.run(
            ['osascript', '-e',
             f'display notification "{message}" with title "{title}" sound name "Glass"'],
            capture_output=True, timeout=5
        )
    except Exception:
        pass

# ── 이미지 로컬 다운로드 ────────────────────────────────────────────────────────
def _download_image(img_url: str, inquiry_id: int) -> str:
    """알리바바 이미지를 로컬에 저장하고 서빙 경로 반환"""
    try:
        os.makedirs(THUMB_DIR, exist_ok=True)
        ext = img_url.split('?')[0].rsplit('.', 1)[-1][:4].lower()
        if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
            ext = 'jpg'
        filename = f'inq_{inquiry_id}.{ext}'
        filepath = os.path.join(THUMB_DIR, filename)
        r = requests.get(img_url, timeout=10, headers={
            'Referer': 'https://www.alibaba.com/',
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        })
        if r.status_code == 200 and len(r.content) > 500:
            with open(filepath, 'wb') as f:
                f.write(r.content)
            return f'/thumbs/{filename}'
    except Exception:
        pass
    return ''

@app.route('/thumbs/<filename>')
def serve_thumb(filename):
    return send_from_directory(THUMB_DIR, filename)

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
                error_msg      TEXT,
                product_image  TEXT,
                product_name   TEXT,
                folder         TEXT    DEFAULT '기본'
            )
        """)
        for col, dfn in [
            ('product_image', 'TEXT'),
            ('product_name',  'TEXT'),
            ('folder',        "TEXT DEFAULT '기본'"),
        ]:
            try:
                conn.execute(f'ALTER TABLE inquiries ADD COLUMN {col} {dfn}')
            except Exception:
                pass
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
    extra    = data.get('extra_notes', '').strip()
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
                # ── 1. 제품 페이지 → 이름 + 이미지 추출 ──────────────────────
                try:
                    page.goto(data['alibaba_url'], wait_until='domcontentloaded', timeout=20000)

                    product_name = page.evaluate("""
                        (document.querySelector('meta[property="og:title"]')?.content ||
                         document.querySelector('h1')?.textContent || '')
                        .trim().replace(/\\s+/g, ' ').slice(0, 80)
                    """)
                    img_url = page.evaluate(
                        "document.querySelector('meta[property=\"og:image\"]')?.content || ''"
                    )

                    updates = {}
                    if product_name:
                        updates['product_name'] = product_name
                    if img_url:
                        local_path = _download_image(img_url, inquiry_id)
                        if local_path:
                            updates['product_image'] = local_path

                    if updates:
                        with get_db() as conn:
                            sets = ', '.join(f'{k} = ?' for k in updates)
                            vals = list(updates.values()) + [inquiry_id]
                            conn.execute(f'UPDATE inquiries SET {sets} WHERE id = ?', vals)
                            conn.commit()
                except Exception:
                    pass

                # ── 2. 스토어 URL 탐색 ──────────────────────────────────────
                storefront = _find_storefront_url(page, company, data['alibaba_url'])
                if not storefront:
                    _update_db(inquiry_id, 'failed', error_msg='스토어 URL을 찾을 수 없음')
                    _notify('비코어랩 소싱 매니저', '❌ 발송 실패 — 스토어 URL 없음')
                    return

                display_company = company
                if not display_company and storefront:
                    slug = storefront.split('.en.alibaba.com')[0].split('/')[-1]
                    display_company = slug.capitalize()
                    with get_db() as conn:
                        conn.execute('UPDATE inquiries SET company = ? WHERE id = ?',
                                     (display_company, inquiry_id))
                        conn.commit()

                # ── 3. 문의 발송 ────────────────────────────────────────────
                ok, reason = _send_alibaba_inquiry(
                    page, display_company or 'Team', storefront, message
                )
                if ok:
                    _update_db(inquiry_id, 'sent',
                               storefront_url=storefront, message_sent=message)
                    _notify('비코어랩 소싱 매니저',
                            f'✅ 발송 완료 — {display_company or "업체"}')
                else:
                    _update_db(inquiry_id, 'failed',
                               storefront_url=storefront, error_msg=reason)
                    _notify('비코어랩 소싱 매니저',
                            f'❌ 발송 실패 — {display_company or "업체"}: {reason[:40]}')
            finally:
                browser.close()
    except Exception as e:
        _update_db(inquiry_id, 'failed', error_msg=str(e))
        _notify('비코어랩 소싱 매니저', f'❌ 오류 발생 — {str(e)[:50]}')

# ── API ───────────────────────────────────────────────────────────────────────
@app.route('/api/send', methods=['POST'])
def api_send():
    data = request.json or {}
    if not data.get('alibaba_url'):
        return jsonify({'error': 'URL 필수'}), 400

    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO inquiries
              (alibaba_url, company, target_price, quantity, spec, extra_notes, folder)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('alibaba_url'),
            data.get('company', ''),
            data.get('target_price', ''),
            data.get('quantity', ''),
            data.get('spec', ''),
            data.get('extra_notes', ''),
            data.get('folder', '기본') or '기본',
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


@app.route('/api/update_folder', methods=['POST'])
def api_update_folder():
    data = request.json or {}
    folder = (data.get('folder') or '기본').strip() or '기본'
    with get_db() as conn:
        conn.execute('UPDATE inquiries SET folder = ? WHERE id = ?',
                     (folder, data['id']))
        conn.commit()
    return jsonify({'ok': True})


@app.route('/api/export/csv')
def api_export_csv():
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM inquiries ORDER BY created_at DESC'
        ).fetchall()

    STATUS_KR = {'pending':'대기중','sent':'발송완료','replied':'회신받음',
                 'ordered':'발주완료','failed':'실패','cancelled':'취소'}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['#','폴더','날짜','제품명','업체명','제품URL','스토어URL','타겟단가','수량','규격','상태','추가요청','오류'])
    for r in rows:
        r = dict(r)
        writer.writerow([
            r['id'], r.get('folder','기본'), r['created_at'],
            r.get('product_name','') or '',
            r['company'] or '',
            r['alibaba_url'], r['storefront_url'] or '',
            r['target_price'] or '', r['quantity'] or '',
            r['spec'] or '', STATUS_KR.get(r['status'], r['status']),
            r['extra_notes'] or '', r['error_msg'] or '',
        ])

    output.seek(0)
    bom = '\ufeff'
    return Response(
        bom + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="sourcing_history.csv"'}
    )


# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>비코어랩 소싱 매니저</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --accent: #ff6b2b; --accent-d: #e55a1b; --accent-glow: rgba(255,107,43,.15);
  --bg: #0f0f13; --bg2: #16161d; --card: #1c1c26; --border: #2a2a38;
  --text: #eaeaf0; --muted: #7a7a90;
  --red: #ff4d4d; --blue: #4d9fff; --green: #2dd4a0; --purple: #a78bfa;
}
body { font-family: -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
       background: var(--bg); color: var(--text); font-size: 16px; }

header { background: var(--bg2); border-bottom: 2px solid var(--accent);
         padding: 0 32px; display: flex; align-items: center;
         gap: 32px; height: 66px; position: sticky; top: 0; z-index: 50;
         box-shadow: 0 2px 12px rgba(0,0,0,.5); }
.logo { font-size: 1.4rem; font-weight: 900; color: var(--accent); letter-spacing: -0.5px; }
.logo span { color: var(--text); }
.tabs { display: flex; gap: 6px; }
.tab { padding: 9px 22px; border-radius: 20px; cursor: pointer; font-weight: 600;
       color: var(--muted); border: none; background: none; font-size: 15px;
       font-family: inherit; transition: all .2s; }
.tab.active { background: var(--accent); color: #fff; }
.tab:hover:not(.active) { background: rgba(255,107,43,.1); color: var(--accent); }

main { max-width: 1160px; margin: 36px auto; padding: 0 28px; }
.cost-cell { white-space:nowrap; }
.cost-usd { font-size:13px; font-weight:700; color:var(--text); }
.cost-krw { font-size:11px; color:var(--muted); }
.cost-na  { font-size:12px; color:#555; }
.card { background: var(--card); border: 1px solid var(--border);
        border-radius: 16px; padding: 32px; margin-bottom: 24px;
        box-shadow: 0 2px 12px rgba(0,0,0,.3); }
.section-title { font-size: 17px; font-weight: 700; margin-bottom: 24px;
                 color: var(--text); display: flex; align-items: center; gap: 10px; }
.section-title::before { content:''; display:block; width:4px; height:20px;
                          background:var(--accent); border-radius:2px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.form-group { display: flex; flex-direction: column; gap: 8px; }
.form-group.full { grid-column: 1 / -1; }
label { font-size: 13px; font-weight: 700; color: #b0b0c0;
        letter-spacing: .3px; text-transform: uppercase; }
input, textarea, select {
  border: 1.5px solid var(--border); border-radius: 10px;
  padding: 13px 15px; font-size: 15px; font-family: inherit;
  outline: none; transition: border-color .2s;
  background: var(--bg2); color: var(--text); }
input:focus, textarea:focus { border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow); }
textarea { resize: vertical; min-height: 100px; }
input::placeholder, textarea::placeholder { color: #555; }

.btn { padding: 13px 28px; border-radius: 10px; border: none; cursor: pointer;
       font-size: 15px; font-weight: 700; font-family: inherit; transition: all .2s; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent-d); transform: translateY(-1px);
                     box-shadow: 0 4px 16px rgba(255,107,43,.3); }
.btn-primary:disabled { opacity:.5; cursor:not-allowed; transform:none; box-shadow:none; }
.btn-sm { padding: 7px 14px; font-size: 13px; border-radius: 8px; }
.btn-outline { background: transparent; border: 1.5px solid var(--border); color: var(--muted); }
.btn-outline:hover { border-color: var(--accent); color: var(--accent); }

.status-bar { padding: 14px 18px; border-radius: 10px; margin-top: 18px;
              font-weight: 600; font-size: 15px; display: none; }
.status-bar.sending { display:block; background:rgba(77,159,255,.12); color:var(--blue); }
.status-bar.success { display:block; background:rgba(45,212,160,.12); color:var(--green); }
.status-bar.error   { display:block; background:rgba(255,77,77,.12); color:var(--red); }

.badge { display:inline-block; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:700; }
.badge-pending   { background:rgba(255,170,50,.15); color:#ffaa32; }
.badge-sent      { background:rgba(77,159,255,.15); color:var(--blue); }
.badge-replied   { background:rgba(45,212,160,.15); color:var(--green); }
.badge-ordered   { background:rgba(167,139,250,.15); color:var(--purple); }
.badge-failed    { background:rgba(255,77,77,.15); color:var(--red); }
.badge-cancelled { background:rgba(122,122,144,.15); color:var(--muted); }

table { width:100%; border-collapse:collapse; }
th { text-align:left; padding:11px 12px; font-size:12px; font-weight:700;
     color:var(--muted); border-bottom:2px solid var(--border);
     letter-spacing:.3px; text-transform:uppercase; }
td { padding:10px 12px; border-bottom:1px solid var(--border);
     vertical-align:middle; font-size:14px; }
tr:hover td { background:rgba(255,107,43,.04); }
td a { color:var(--accent); text-decoration:none; }
td a:hover { text-decoration:underline; }

/* 셀렉트 공통 */
.inline-select { font-size:12px; padding:4px 6px; border:1.5px solid var(--border);
                 border-radius:6px; font-family:inherit; cursor:pointer;
                 background:var(--bg2); color:var(--text); outline:none; }
.inline-select:focus { border-color:var(--accent); }

/* 썸네일 */
.thumb { width:54px; height:54px; object-fit:cover; border-radius:8px;
         border:1px solid var(--border); display:block; flex-shrink:0; }
.thumb-ph { width:54px; height:54px; border-radius:8px; border:1px solid var(--border);
            background:var(--bg2); display:flex; align-items:center;
            justify-content:center; font-size:22px; flex-shrink:0; }
.prod-cell { display:flex; align-items:center; gap:11px; }
.prod-info { display:flex; flex-direction:column; gap:2px; min-width:0; }
.prod-name { font-size:13px; font-weight:700; color:var(--text);
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:200px; }
.prod-company { font-size:12px; color:var(--muted);
                white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:200px; }

/* 폴더 */
.folder-filters { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:18px; }
.folder-btn { padding:6px 16px; border-radius:20px; border:1.5px solid var(--border);
              background:transparent; color:var(--muted); font-size:13px; font-weight:600;
              cursor:pointer; font-family:inherit; transition:all .2s; }
.folder-btn.active { background:var(--accent); color:#fff; border-color:var(--accent); }
.folder-btn:hover:not(.active) { border-color:var(--accent); color:var(--accent); }
.folder-tag { display:inline-block; padding:3px 8px; border-radius:8px;
              font-size:12px; font-weight:600; background:var(--bg2); color:var(--muted); }

/* 모달 */
.modal-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,.7);
                 z-index:100; align-items:center; justify-content:center; }
.modal-overlay.open { display:flex; }
.modal { background:var(--card); border:1px solid var(--border); border-radius:18px;
         padding:32px; width:700px; max-width:92vw; max-height:82vh; overflow-y:auto; }
.modal-header { display:flex; justify-content:space-between;
                align-items:center; margin-bottom:24px; }
.modal-close { background:none; border:none; cursor:pointer;
               font-size:24px; color:var(--muted); line-height:1; }
.detail-row { display:flex; gap:16px; padding:11px 0; border-bottom:1px solid var(--border); }
.detail-label { width:120px; font-weight:700; color:var(--muted);
                font-size:13px; flex-shrink:0; padding-top:2px; }
.detail-value { flex:1; word-break:break-all; line-height:1.6; font-size:15px; }
pre.msg-preview { background:var(--bg); border:1px solid var(--border);
                  border-radius:10px; padding:16px; font-size:13px; color:var(--text);
                  white-space:pre-wrap; overflow-y:auto; max-height:240px;
                  font-family:monospace; margin-top:10px; }

.page { display:none; } .page.active { display:block; }
.empty { text-align:center; padding:60px; color:var(--muted); font-size:16px; }
.toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.hint { font-size:13px; color:var(--muted); margin-top:7px; }

.stat-row { display:flex; gap:14px; margin-bottom:24px; flex-wrap:wrap; }
.stat { flex:1; min-width:110px; background:var(--card); border:1px solid var(--border);
        border-radius:12px; padding:18px 20px; text-align:center; }
.stat-num { font-size:26px; font-weight:900; color:var(--accent); }
.stat-label { font-size:13px; color:var(--muted); margin-top:4px; font-weight:600; }
</style>
</head>
<body>

<header>
  <span class="logo">비코어랩 <span>소싱 매니저</span></span>
  <div class="tabs">
    <button class="tab active" id="tab-new" onclick="switchTab('new', this)">새 문의</button>
    <button class="tab" id="tab-history" onclick="switchTab('history', this)">히스토리</button>
  </div>
</header>

<main>
  <!-- ── 새 문의 ── -->
  <div id="page-new" class="page active">
    <div class="card">
      <div class="section-title">알리바바 업체 문의 발송</div>
      <div class="form-grid">
        <div class="form-group full">
          <label>알리바바 제품 URL *</label>
          <input type="url" id="alibaba_url" placeholder="https://www.alibaba.com/product-detail/...">
          <span class="hint">문의할 알리바바 제품 페이지 URL을 붙여넣으세요.</span>
        </div>
        <div class="form-group full">
          <label>업체명 (선택 — 비워두면 자동 감지)</label>
          <input type="text" id="company" placeholder="예: Shanghai Condibe Hardware Co., Ltd.">
        </div>
        <div class="form-group">
          <label>타겟 단가</label>
          <input type="text" id="target_price" placeholder="예: USD 0.5~1.0 / pcs (EXW)">
        </div>
        <div class="form-group">
          <label>수량 (초도발주 기준)</label>
          <input type="text" id="quantity" placeholder="예: 1,000">
        </div>
        <div class="form-group full">
          <label>규격 / 사이즈 / 색상</label>
          <input type="text" id="spec" placeholder="예: 50×50mm, White, Custom Logo Print">
        </div>
        <div class="form-group full">
          <label>폴더</label>
          <input type="text" id="folder" placeholder="예: 건조기시트, 세제류, 탈취제 (비워두면 기본 폴더)">
        </div>
        <div class="form-group full">
          <label>추가 요청사항</label>
          <textarea id="extra_notes" placeholder="예: Please send a sample before bulk order."></textarea>
        </div>
      </div>
      <div style="margin-top:22px; display:flex; align-items:center; gap:16px;">
        <button class="btn btn-primary" id="send-btn" onclick="sendInquiry()">문의 발송</button>
        <span style="color:var(--muted); font-size:13px;">
          헤드리스 브라우저로 자동 발송 · 완료 시 macOS 알림 전송
        </span>
      </div>
      <div class="status-bar" id="status-bar"></div>
    </div>
  </div>

  <!-- ── 히스토리 ── -->
  <div id="page-history" class="page">
    <div id="stat-row" class="stat-row"></div>
    <div class="card">
      <div class="toolbar">
        <div class="section-title" style="margin-bottom:0;">문의 히스토리</div>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-outline btn-sm" onclick="loadHistory()">새로고침</button>
          <a class="btn btn-outline btn-sm" href="/api/export/csv" download="소싱히스토리.csv">CSV 내보내기</a>
        </div>
      </div>
      <div class="folder-filters" id="folder-filters"></div>
      <div id="history-content"><div class="empty">로딩 중...</div></div>
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

let _allRows = [];
let _currentFolder = null;
const USD_KRW = 1450;

/* ── EXW 수입원가 계산 ── */
function parsePrice(s) {
  const m = (s||'').replace(/,/g,'').match(/[\d.]+/);
  return m ? parseFloat(m[0]) : null;
}
function parseQty(s) {
  const m = (s||'').replace(/,/g,'').match(/\d+/);
  return m ? parseInt(m[0]) : null;
}
function calcImportCost(exwUnit, qty) {
  if (!exwUnit || !qty || exwUnit <= 0 || qty <= 0) return null;
  const exwTotal  = exwUnit * qty;
  const inland    = exwTotal * 0.05;    // 내륙운송+수출통관 5%
  const fob       = exwTotal + inland;
  const freight   = exwTotal * 0.08;    // 해상운임 8%
  const insurance = exwTotal * 0.005;   // 보험 0.5%
  const cif       = fob + freight + insurance;
  const duty      = cif * 0.08;         // 관세 8%
  const vat       = (cif + duty) * 0.10;// 부가세 10%
  const customs   = 100;                // 통관비 USD 100
  const total     = cif + duty + vat + customs;
  const unit      = total / qty;
  return {
    unitUSD: unit.toFixed(2),
    unitKRW: Math.round(unit * USD_KRW).toLocaleString(),
    exwTotal: exwTotal.toFixed(0),
    inland: inland.toFixed(0),
    fob: fob.toFixed(0),
    freight: freight.toFixed(0),
    insurance: insurance.toFixed(0),
    cif: cif.toFixed(0),
    duty: duty.toFixed(0),
    vat: vat.toFixed(0),
    customs, total: total.toFixed(0), qty
  };
}

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
    folder       : document.getElementById('folder').value.trim(),
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
  const res = await fetch('/api/history');
  _allRows  = await res.json();
  _renderFolderFilters();
  _renderHistory();
}

function _renderFolderFilters() {
  const folders = [...new Set(_allRows.map(r => r.folder || '기본'))].sort();
  const container = document.getElementById('folder-filters');
  if (folders.length <= 1) { container.innerHTML = ''; return; }
  container.innerHTML =
    `<button class="folder-btn ${_currentFolder === null ? 'active' : ''}"
             onclick="setFolder(null)">전체 (${_allRows.length})</button>` +
    folders.map(f => {
      const cnt = _allRows.filter(r => (r.folder || '기본') === f).length;
      return `<button class="folder-btn ${_currentFolder === f ? 'active' : ''}"
                      onclick="setFolder('${f.replace(/'/g,"\\'")}')">
                📁 ${f} <span style="opacity:.7">(${cnt})</span></button>`;
    }).join('');
}

function setFolder(f) { _currentFolder = f; _renderFolderFilters(); _renderHistory(); }

function _renderHistory() {
  const rows = _currentFolder === null
    ? _allRows
    : _allRows.filter(r => (r.folder || '기본') === _currentFolder);

  const counts = {pending:0,sent:0,replied:0,ordered:0,failed:0,cancelled:0};
  _allRows.forEach(r => { if (counts[r.status] !== undefined) counts[r.status]++; });
  document.getElementById('stat-row').innerHTML = `
    <div class="stat"><div class="stat-num">${_allRows.length}</div><div class="stat-label">전체</div></div>
    <div class="stat"><div class="stat-num" style="color:#2563eb;">${counts.sent}</div><div class="stat-label">발송완료</div></div>
    <div class="stat"><div class="stat-num" style="color:#059669;">${counts.replied}</div><div class="stat-label">회신받음</div></div>
    <div class="stat"><div class="stat-num" style="color:#7c3aed;">${counts.ordered}</div><div class="stat-label">발주완료</div></div>
    <div class="stat"><div class="stat-num" style="color:#dc2626;">${counts.failed}</div><div class="stat-label">실패</div></div>`;

  if (!rows.length) {
    document.getElementById('history-content').innerHTML =
      '<div class="empty">문의 내역이 없습니다.</div>'; return;
  }

  // 폴더 목록 (드롭다운용)
  const allFolders = [...new Set(_allRows.map(r => r.folder || '기본'))].sort();

  document.getElementById('history-content').innerHTML = `
    <table>
      <thead><tr>
        <th>제품</th><th>날짜</th><th>폴더</th>
        <th>EXW단가</th><th>수입단가</th><th>수량</th><th>상태</th><th>변경</th>
      </tr></thead>
      <tbody>
        ${rows.map(r => {
          const thumbHtml = r.product_image
            ? `<img class="thumb" src="${r.product_image}" alt=""
                    onerror="this.outerHTML='<div class=\\'thumb-ph\\'>📦</div>'">`
            : `<div class="thumb-ph">📦</div>`;
          const topLine = r.product_name
            ? `<div class="prod-name">${r.product_name}</div>`
            : '';
          const botLine = r.company
            ? `<div class="prod-company">${r.company}</div>`
            : `<div class="prod-company" style="color:#b0bec5;">감지중</div>`;

          // 폴더 옵션 — 현재 폴더 + 전체폴더 + 새 폴더 입력
          const folderOpts = ['기본', ...allFolders.filter(f => f !== '기본')]
            .filter((f, i, a) => a.indexOf(f) === i)
            .map(f => `<option value="${f}" ${(r.folder||'기본')===f?'selected':''}>${f}</option>`)
            .join('');

          return `
          <tr onclick="showDetail(${r.id})" style="cursor:pointer;">
            <td>
              <div class="prod-cell">
                ${thumbHtml}
                <div class="prod-info">
                  ${topLine}${botLine}
                  <a href="${r.alibaba_url}" target="_blank"
                     onclick="event.stopPropagation()"
                     style="font-size:11px; color:var(--accent);">링크 ↗</a>
                </div>
              </div>
            </td>
            <td style="white-space:nowrap; font-size:12px; color:var(--muted);">
              ${r.created_at.slice(0,16).replace('T',' ')}</td>
            <td onclick="event.stopPropagation()">
              <select class="inline-select" onchange="updateFolder(${r.id}, this.value, this)">
                ${folderOpts}
                <option value="__new__">+ 새 폴더</option>
              </select>
            </td>
            <td style="white-space:nowrap; font-size:13px;">${r.target_price || '-'}</td>
            <td class="cost-cell">${(() => {
              const c = calcImportCost(parsePrice(r.target_price), parseQty(r.quantity));
              return c
                ? '<span class="cost-usd">$' + c.unitUSD + '</span><br><span class="cost-krw">₩' + c.unitKRW + '</span>'
                : '<span class="cost-na">-</span>';
            })()}</td>
            <td>${r.quantity || '-'}</td>
            <td><span class="badge badge-${r.status}">${STATUS_LABEL[r.status]||r.status}</span></td>
            <td onclick="event.stopPropagation()">
              <select class="inline-select" onchange="updateStatus(${r.id}, this.value)">
                <option value="">변경</option>
                <option value="replied">회신받음</option>
                <option value="ordered">발주완료</option>
                <option value="cancelled">취소</option>
              </select>
            </td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

/* ── 상세 모달 ── */
async function showDetail(id) {
  const res = await fetch('/api/inquiry/' + id);
  const r   = await res.json();
  document.getElementById('modal-body').innerHTML = `
    ${r.product_image ? `
    <div style="text-align:center; margin-bottom:20px;">
      <img src="${r.product_image}" alt="제품 이미지"
           style="max-width:220px; max-height:220px; border-radius:12px;
                  border:1px solid var(--border); object-fit:cover;">
    </div>` : ''}
    <div class="detail-row">
      <span class="detail-label">상태</span>
      <span><span class="badge badge-${r.status}">${STATUS_LABEL[r.status]||r.status}</span></span>
    </div>
    <div class="detail-row">
      <span class="detail-label">폴더</span>
      <span class="detail-value"><span class="folder-tag">📁 ${r.folder || '기본'}</span></span>
    </div>
    ${r.product_name ? `
    <div class="detail-row">
      <span class="detail-label">제품명</span>
      <span class="detail-value">${r.product_name}</span>
    </div>` : ''}
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
      <span class="detail-label">EXW 단가</span>
      <span class="detail-value">${r.target_price||'-'}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">수량</span>
      <span class="detail-value">${r.quantity||'-'}</span>
    </div>
    ${(() => {
      const c = calcImportCost(parsePrice(r.target_price), parseQty(r.quantity));
      if (!c) return '';
      return `
    <div class="detail-row">
      <span class="detail-label">수입단가</span>
      <span class="detail-value">
        <div style="font-weight:800; font-size:17px; color:var(--accent);">USD ${c.unitUSD} / ₩${c.unitKRW}</div>
        <div style="font-size:12px; color:var(--muted); margin-top:4px;">기준환율: ${USD_KRW.toLocaleString()}원/USD · 인코텀즈: EXW</div>
        <details style="margin-top:10px;">
          <summary style="font-size:12px; cursor:pointer; color:var(--accent); font-weight:600;">원가 계산 내역 보기</summary>
          <table style="font-size:12px; margin-top:8px; width:100%; border-collapse:collapse;">
            <tr><td style="padding:4px 0; color:var(--muted);">EXW 합계 (${c.qty}pcs)</td><td style="text-align:right;">USD ${c.exwTotal}</td></tr>
            <tr><td style="padding:4px 0; color:var(--muted);">+ 내륙운송+수출통관 (5%)</td><td style="text-align:right;">USD ${c.inland}</td></tr>
            <tr><td style="padding:4px 0; color:var(--muted);">= FOB</td><td style="text-align:right;">USD ${c.fob}</td></tr>
            <tr><td style="padding:4px 0; color:var(--muted);">+ 해상운임 (8%)</td><td style="text-align:right;">USD ${c.freight}</td></tr>
            <tr><td style="padding:4px 0; color:var(--muted);">+ 보험 (0.5%)</td><td style="text-align:right;">USD ${c.insurance}</td></tr>
            <tr style="border-top:1px solid var(--border);"><td style="padding:4px 0; font-weight:700;">= CIF</td><td style="text-align:right; font-weight:700;">USD ${c.cif}</td></tr>
            <tr><td style="padding:4px 0; color:var(--muted);">+ 관세 (8%)</td><td style="text-align:right;">USD ${c.duty}</td></tr>
            <tr><td style="padding:4px 0; color:var(--muted);">+ 부가세 (10%)</td><td style="text-align:right;">USD ${c.vat}</td></tr>
            <tr><td style="padding:4px 0; color:var(--muted);">+ 통관비</td><td style="text-align:right;">USD ${c.customs}</td></tr>
            <tr style="border-top:2px solid var(--accent);"><td style="padding:6px 0; font-weight:800;">수입원가 합계</td><td style="text-align:right; font-weight:800; color:var(--accent);">USD ${c.total}</td></tr>
          </table>
        </details>
      </span>
    </div>`;
    })()}
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
      <div style="font-size:12px; font-weight:700; color:var(--muted); margin-bottom:4px;">발송된 메시지</div>
      <pre class="msg-preview">${r.message_sent.replace(/</g,'&lt;')}</pre>
    </div>` : ''}`;
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

async function updateFolder(id, folder, selectEl) {
  if (!folder) return;
  if (folder === '__new__') {
    const name = prompt('새 폴더 이름을 입력하세요:');
    if (!name || !name.trim()) { selectEl.value = selectEl.dataset.prev || '기본'; return; }
    folder = name.trim();
  }
  selectEl.dataset.prev = folder;
  await fetch('/api/update_folder', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({id, folder})
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
    from waitress import serve
    init_db()
    print()
    print('  비코어랩 소싱 매니저 실행 중 (waitress)')
    print('  브라우저에서 열기 → http://localhost:8080')
    print()
    serve(app, host='0.0.0.0', port=8080, threads=6,
          channel_timeout=300, recv_bytes=65536)
