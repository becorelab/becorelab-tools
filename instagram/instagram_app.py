"""
instagram_app.py — iLBiA 인스타그램 공동구매 대시보드
Flask 웹서버 + APScheduler 24시간 자동화
"""

import asyncio
import random
import threading
import logging
import os
from datetime import datetime, date, timedelta

from flask import Flask, jsonify, request, render_template
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from instagram_bot import (
    init_db, get_db, get_setting, get_dm_count_today,
    run_bot, DMSender, SESSION_PATH, FOLLOWUP_TEMPLATE
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone='Asia/Seoul')
bot_lock = threading.Lock()
bot_running = False


# ──────────────────────────────────────────
# 스케줄러
# ──────────────────────────────────────────
def scheduled_job():
    global bot_running
    if get_setting('bot_active') != 'true':
        return
    if not bot_lock.acquire(blocking=False):
        logger.info("봇이 이미 실행 중 — 스킵")
        return
    bot_running = True
    try:
        asyncio.run(run_bot())
    except Exception as e:
        logger.error(f"스케줄 실행 오류: {e}")
    finally:
        bot_running = False
        bot_lock.release()


def setup_scheduler():
    # 1시간마다 체크 (오전 9시 ~ 오후 11시 사이에만 실행)
    scheduler.add_job(
        scheduled_job,
        IntervalTrigger(hours=1),
        id='dm_hourly',
        replace_existing=True,
    )
    scheduler.start()
    logger.info("스케줄러 시작 (1시간 간격)")


# ──────────────────────────────────────────
# 라우트
# ──────────────────────────────────────────
@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/api/stats')
def api_stats():
    conn = get_db()
    today = date.today().isoformat()

    total_sent = conn.execute("SELECT COUNT(*) as c FROM dm_log WHERE status='sent'").fetchone()['c']
    sent_today = conn.execute(
        "SELECT COUNT(*) as c FROM dm_log WHERE status='sent' AND date(sent_at)=?", (today,)
    ).fetchone()['c']
    total_failed = conn.execute("SELECT COUNT(*) as c FROM dm_log WHERE status='failed'").fetchone()['c']
    total_replied = conn.execute("SELECT COUNT(*) as c FROM dm_log WHERE status='replied'").fetchone()['c']
    pending_count = conn.execute("SELECT COUNT(*) as c FROM accounts WHERE status='pending'").fetchone()['c']
    total_accounts = conn.execute("SELECT COUNT(*) as c FROM accounts").fetchone()['c']
    filtered_count = conn.execute("SELECT COUNT(*) as c FROM accounts WHERE status='filtered'").fetchone()['c']

    # 최근 7일 발송 추이
    weekly = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        cnt = conn.execute(
            "SELECT COUNT(*) as c FROM dm_log WHERE status='sent' AND date(sent_at)=?", (d,)
        ).fetchone()['c']
        weekly.append({'date': d, 'count': cnt})

    conn.close()

    return jsonify({
        'total_sent': total_sent,
        'sent_today': sent_today,
        'total_failed': total_failed,
        'total_replied': total_replied,
        'reply_rate': round(total_replied / total_sent * 100, 1) if total_sent > 0 else 0,
        'pending_accounts': pending_count,
        'total_accounts': total_accounts,
        'filtered_accounts': filtered_count,
        'bot_active': get_setting('bot_active') == 'true',
        'bot_running': bot_running,
        'weekly': weekly,
        'daily_min': int(get_setting('daily_min') or 20),
        'daily_max': int(get_setting('daily_max') or 30),
    })


@app.route('/api/dm_log')
def api_dm_log():
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    conn = get_db()
    logs = conn.execute(
        "SELECT * FROM dm_log ORDER BY sent_at DESC LIMIT ? OFFSET ?",
        (per_page, offset)
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) as c FROM dm_log").fetchone()['c']
    conn.close()

    return jsonify({
        'logs': [dict(r) for r in logs],
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page,
    })


@app.route('/api/accounts')
def api_accounts():
    status = request.args.get('status', '')
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    conn = get_db()
    if status:
        rows = conn.execute(
            "SELECT * FROM accounts WHERE status=? ORDER BY discovered_at DESC LIMIT ? OFFSET ?",
            (status, per_page, offset)
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) as c FROM accounts WHERE status=?", (status,)
        ).fetchone()['c']
    else:
        rows = conn.execute(
            "SELECT * FROM accounts ORDER BY discovered_at DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM accounts").fetchone()['c']
    conn.close()

    return jsonify({'accounts': [dict(r) for r in rows], 'total': total})


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    conn = get_db()
    if request.method == 'POST':
        data = request.json or {}
        for k, v in data.items():
            conn.execute('UPDATE settings SET value=? WHERE key=?', (str(v), k))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    conn.close()
    result = {r['key']: r['value'] for r in rows}
    if result.get('ig_password'):
        result['ig_password'] = '••••••••'
    return jsonify(result)


@app.route('/api/bot/toggle', methods=['POST'])
def api_bot_toggle():
    conn = get_db()
    current = get_setting('bot_active')
    new_val = 'false' if current == 'true' else 'true'
    conn.execute("UPDATE settings SET value=? WHERE key='bot_active'", (new_val,))
    conn.commit()
    conn.close()
    logger.info(f"봇 상태 변경: {new_val}")
    return jsonify({'bot_active': new_val == 'true'})


@app.route('/api/bot/run_now', methods=['POST'])
def api_bot_run_now():
    """즉시 실행"""
    global bot_running
    if bot_running:
        return jsonify({'ok': False, 'message': '이미 실행 중이에요!'})

    def _run():
        global bot_running
        if not bot_lock.acquire(blocking=False):
            return
        bot_running = True
        try:
            asyncio.run(run_bot())
        except Exception as e:
            logger.error(f"즉시 실행 오류: {e}")
        finally:
            bot_running = False
            bot_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'ok': True, 'message': '봇 실행 시작!'})


@app.route('/api/login', methods=['POST'])
def api_login():
    """인스타그램 로그인 & 세션 저장"""
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'ok': False, 'message': '아이디/비밀번호를 입력해주세요'})

    async def _login():
        sender = DMSender()
        await sender.start()
        # Playwright 로그인은 login_manual.py 사용 권장
        await sender.stop()
        return False

    try:
        success = asyncio.run(_login())
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)})

    if success:
        conn = get_db()
        conn.execute("UPDATE settings SET value=? WHERE key='ig_username'", (username,))
        conn.execute("UPDATE settings SET value=? WHERE key='ig_password'", (password,))
        conn.commit()
        conn.close()

    return jsonify({'ok': success, 'message': '로그인 성공!' if success else '로그인 실패. 아이디/비밀번호를 확인해주세요.'})


@app.route('/api/dm_log/<int:log_id>/replied', methods=['POST'])
def api_mark_replied(log_id):
    """답장 수동 기록"""
    conn = get_db()
    reply_text = (request.json or {}).get('reply', '')
    conn.execute(
        "UPDATE dm_log SET status='replied', reply=?, reply_at=datetime('now','localtime') WHERE id=?",
        (reply_text, log_id)
    )
    # 계정 상태도 업데이트
    row = conn.execute("SELECT username FROM dm_log WHERE id=?", (log_id,)).fetchone()
    if row:
        conn.execute(
            "UPDATE accounts SET replied_at=datetime('now','localtime'), status='replied' WHERE username=?",
            (row['username'],)
        )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/followup/<username>')
def api_followup_msg(username):
    """2차 DM 메시지 생성 (복사용)"""
    msg = FOLLOWUP_TEMPLATE.replace('{username}', f'@{username}')
    return jsonify({'message': msg})


@app.route('/api/account/<username>/skip', methods=['POST'])
def api_skip_account(username):
    """계정 스킵"""
    conn = get_db()
    conn.execute("UPDATE accounts SET status='skipped' WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


if __name__ == '__main__':
    init_db()
    setup_scheduler()
    print("━" * 50)
    print("  iLBiA 인스타그램 공동구매 대시보드")
    print("  http://localhost:8081")
    print("━" * 50)
    app.run(host='0.0.0.0', port=8081, debug=False, use_reloader=False)
