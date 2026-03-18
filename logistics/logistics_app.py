#!/usr/bin/env python3
"""
iLBiA 물류 대시보드 서버
- 발주대시보드 HTML 서빙
- 이지어드민 데이터 자동 수집 API
- 매일 10시 예약 수집 (APScheduler)
- 로컬 캐시 (data/cache.json) + Firebase Firestore 실시간 연동
"""
import json
import logging
import os
import sys
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, jsonify, make_response, request, send_file
from flask_cors import CORS

from ezadmin_scraper import fetch_all_data

# Firestore 연동 — sourcing/analyzer/firestore_db.py 재사용
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sourcing', 'analyzer'))
try:
    import firestore_db as fdb
    fdb.init_firestore()
    _firestore_ok = True
except Exception as e:
    _firestore_ok = False
    logging.warning(f"Firestore 연결 실패 (로컬 캐시만 사용): {e}")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(DIR, "data", "cache.json")

# 태스크 저장소
tasks = {}

# 동시 실행 방지 lock
scrape_lock = threading.Lock()


# ── 캐시 관리 ──
def save_cache(result):
    """수집 결과를 로컬 캐시 + Firestore에 동시 저장"""
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    payload = {
        "timestamp": datetime.now().isoformat(),
        "inventory": result["inventory"],
        "orders": result["orders"],
        "sales": result.get("sales"),
    }
    # 1. 로컬 캐시 저장
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CACHE_PATH), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, CACHE_PATH)
        log.info(f"로컬 캐시 저장 완료: {CACHE_PATH}")
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

    # 2. Firestore 저장
    if _firestore_ok:
        try:
            _save_to_firestore(payload)
            log.info("Firestore 동기화 완료")
        except Exception as e:
            log.warning(f"Firestore 저장 실패 (로컬 캐시는 정상): {e}")


def _save_to_firestore(payload):
    """Firestore에 물류 데이터 저장 (logistics 컬렉션)"""
    db = fdb.db()
    ts = payload["timestamp"]

    # 최신 스냅샷 저장 (서버에서 바로 조회용)
    db.collection("logistics").document("latest").set({
        "timestamp": ts,
        "inventory": payload["inventory"],
        "orders": payload["orders"],
        "updated_at": datetime.now().isoformat(),
    })

    # 일별 히스토리 저장 (매출 추이용)
    today = datetime.now().strftime("%Y-%m-%d")
    db.collection("logistics_daily").document(today).set({
        "date": today,
        "timestamp": ts,
        "inventory": payload["inventory"],
        "orders": payload["orders"],
    })

    # 매출 데이터 저장 (sales_daily 컬렉션)
    sales = payload.get("sales")
    if sales and sales.get("date"):
        sales_date = sales["date"]
        # orders 필드는 너무 크므로 요약만 저장
        sales_summary = {
            "date": sales_date,
            "timestamp": ts,
            "total_amount": sales.get("total_amount", 0),
            "total_settlement": sales.get("total_settlement", 0),
            "total_count": sales.get("total_count", 0),
            "by_channel": sales.get("by_channel", {}),
            "by_product": sales.get("by_product", {}),
        }
        db.collection("sales_daily").document(sales_date).set(sales_summary)
        log.info(f"Firestore sales_daily/{sales_date} 저장 완료")


def load_cache():
    """캐시 로드: 로컬 파일 → Firestore 폴백"""
    # 1. 로컬 캐시
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"로컬 캐시 로드 실패: {e}")

    # 2. Firestore 폴백 (서버 환경에서 유용)
    if _firestore_ok:
        try:
            doc = fdb.db().collection("logistics").document("latest").get()
            if doc.exists:
                data = doc.to_dict()
                log.info("Firestore에서 데이터 로드 완료")
                return data
        except Exception as e:
            log.warning(f"Firestore 로드 실패: {e}")

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


# ── 발주/MOQ Firestore 동기화 API ──
@app.route("/api/purchases", methods=["GET"])
def api_get_purchases():
    """Firestore에서 발주 데이터 로드"""
    if not _firestore_ok:
        return jsonify({"status": "no_firestore"}), 503
    try:
        doc = fdb.db().collection("logistics").document("purchases").get()
        if doc.exists:
            return jsonify({"status": "ok", "data": doc.to_dict()})
        return jsonify({"status": "empty"}), 204
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sales-daily")
def api_sales_daily():
    """매출 일별 데이터 조회 (쿼리: ?date=2026-03-16 또는 ?days=7)"""
    if not _firestore_ok:
        return jsonify({"status": "no_firestore"}), 503
    try:
        target_date = request.args.get("date")
        if target_date:
            doc = fdb.db().collection("sales_daily").document(target_date).get()
            if doc.exists:
                return jsonify({"status": "ok", "data": doc.to_dict()})
            return jsonify({"status": "empty"}), 204

        days = int(request.args.get("days", 7))
        from datetime import timedelta
        results = []
        for i in range(days):
            d = (datetime.now() - timedelta(days=i+1)).strftime("%Y-%m-%d")
            doc = fdb.db().collection("sales_daily").document(d).get()
            if doc.exists:
                results.append(doc.to_dict())
        return jsonify({"status": "ok", "data": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chrome-upload", methods=["POST"])
def api_chrome_upload():
    """클로드 인 크롬에서 재고 + 주문 + 매출 데이터를 한 번에 수신"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "JSON 데이터가 없습니다"}), 400

        inventory = data.get("inventory", {})
        orders = data.get("orders", [])
        sales = data.get("sales")

        today = datetime.now().strftime("%Y-%m-%d")

        # inventory 항목에 updated 날짜 추가
        for code in inventory:
            inventory[code]["updated"] = today

        # save_cache()와 동일한 형식으로 payload 구성
        result = {
            "inventory": inventory,
            "orders": orders,
            "sales": sales,
        }
        save_cache(result)

        # 응답 구성
        saved = {
            "inventory": len(inventory),
            "orders": len(orders),
        }
        if sales and sales.get("date"):
            saved["sales_date"] = sales["date"]

        sales_msg = f", 매출 {saved['sales_date']}" if "sales_date" in saved else ""
        log.info(f"[chrome-upload] 저장 완료: 재고 {saved['inventory']}건, 주문 {saved['orders']}건{sales_msg}")

        return jsonify({
            "status": "ok",
            "message": "데이터 저장 완료",
            "saved": saved,
        })

    except Exception as e:
        log.error(f"[chrome-upload] 오류: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/purchases", methods=["POST"])
def api_save_purchases():
    """발주 + MOQ 데이터를 Firestore에 저장"""
    if not _firestore_ok:
        return jsonify({"status": "no_firestore"}), 503
    try:
        data = request.get_json()
        fdb.db().collection("logistics").document("purchases").set({
            "purchases": data.get("purchases", []),
            "moq": data.get("moq", {}),
            "updated_at": datetime.now().isoformat(),
        })
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

    port = int(os.environ.get('PORT', 8082))
    print(f"\n  iLBiA 물류 대시보드")
    print(f"  http://localhost:{port}")
    print(f"  매일 10:00 자동 수집 활성화")
    print(f"  Ctrl+C로 종료\n")
    serve(app, host="0.0.0.0", port=port, threads=4, channel_timeout=300)
