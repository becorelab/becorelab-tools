#!/usr/bin/env python3
"""
iLBiA 물류 대시보드 서버
- 발주대시보드 HTML 서빙
- 이지어드민 데이터 자동 수집 API
- 매일 10시 예약 수집 (APScheduler)
- 서버 캐시 (data/cache.json)
"""
import json
import logging
import os
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, jsonify, make_response, request, send_file

from ezadmin_scraper import fetch_all_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(DIR, "data", "cache.json")

# 태스크 저장소
tasks = {}

# 동시 실행 방지 lock
scrape_lock = threading.Lock()


# ── 캐시 관리 ──
def save_cache(result):
    """수집 결과를 data/cache.json에 atomic write"""
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    payload = {
        "timestamp": datetime.now().isoformat(),
        "inventory": result["inventory"],
        "orders": result["orders"],
    }
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CACHE_PATH), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, CACHE_PATH)
        log.info(f"캐시 저장 완료: {CACHE_PATH}")
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_cache():
    """캐시 파일 로드. 없으면 None"""
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"캐시 로드 실패: {e}")
        return None


# ── macOS 알림 ──
def notify_macos(title, message):
    """macOS 알림 표시"""
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "{title}"',
            ],
            timeout=5,
        )
    except Exception as e:
        log.warning(f"macOS 알림 실패: {e}")


# ── 수집 실행 ──
def run_scrape(task_id=None, scheduled=False):
    """데이터 수집 실행 (lock으로 동시 실행 방지)"""
    if not scrape_lock.acquire(blocking=False):
        msg = "이미 수집이 진행 중입니다"
        log.warning(msg)
        if task_id and task_id in tasks:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["error"] = msg
        return

    try:
        if scheduled:
            notify_macos(
                "iLBiA 물류 대시보드",
                "예약 수집이 시작됩니다. 브라우저에서 보안코드를 입력해주세요.",
            )

        def on_progress(step):
            if task_id and task_id in tasks:
                tasks[task_id]["step"] = step
            log.info(f"[{task_id or 'scheduled'}] {step}")

        result = fetch_all_data(progress=on_progress)
        save_cache(result)

        if task_id and task_id in tasks:
            tasks[task_id]["status"] = "done"
            tasks[task_id]["result"] = result
        log.info(
            f"[{task_id or 'scheduled'}] 완료: "
            f"재고 {len(result['inventory'])}건, 주문 {len(result['orders'])}건"
        )

        if scheduled:
            notify_macos(
                "iLBiA 수집 완료",
                f"재고 {len(result['inventory'])}품목, 주문 {len(result['orders'])}건",
            )

    except Exception as e:
        if task_id and task_id in tasks:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["error"] = str(e)
        log.error(f"[{task_id or 'scheduled'}] 오류: {e}")

        if scheduled:
            notify_macos("iLBiA 수집 실패", str(e)[:80])
    finally:
        scrape_lock.release()


# ── 예약 수집 ──
def scheduled_scrape():
    """매일 10시 예약 수집"""
    log.info("=== 예약 수집 시작 (10:00) ===")
    run_scrape(scheduled=True)


# ── 라우트 ──
@app.route("/")
def index():
    resp = make_response(send_file(os.path.join(DIR, "발주대시보드.html")))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.route("/api/cached-data")
def api_cached_data():
    """캐시된 데이터 반환"""
    cache = load_cache()
    if cache is None:
        return jsonify({"status": "empty"}), 204
    return jsonify({"status": "ok", "data": cache})


@app.route("/api/fetch-data", methods=["POST"])
def api_fetch_data():
    task_id = uuid.uuid4().hex[:8]
    tasks[task_id] = {
        "status": "running",
        "step": "starting",
        "result": None,
        "error": None,
    }
    threading.Thread(target=run_scrape, args=(task_id,), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/fetch-status/<task_id>")
def api_fetch_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    from waitress import serve

    # APScheduler — 매일 10시 자동 수집
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        scheduled_scrape,
        CronTrigger(hour=10, minute=0),
        id="daily_scrape",
        name="매일 10시 이지어드민 수집",
        misfire_grace_time=3600,
    )
    scheduler.start()
    log.info("APScheduler 시작 — 매일 10:00 자동 수집 예약됨")

    port = 8090
    print(f"\n  iLBiA 물류 대시보드")
    print(f"  http://localhost:{port}")
    print(f"  매일 10:00 자동 수집 활성화")
    print(f"  Ctrl+C로 종료\n")
    serve(app, host="0.0.0.0", port=port, threads=4, channel_timeout=300)
