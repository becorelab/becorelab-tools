#!/usr/bin/env python3
"""
iLBiA 물류 대시보드 서버
- 발주대시보드 HTML 서빙
- 이지어드민 데이터 자동 수집 API
"""
import logging
import threading
import uuid
import os
from flask import Flask, jsonify, send_file, request, make_response

from ezadmin_scraper import fetch_all_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
DIR = os.path.dirname(os.path.abspath(__file__))

# 태스크 저장소
tasks = {}


@app.route("/")
def index():
    resp = make_response(send_file(os.path.join(DIR, "발주대시보드.html")))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.route("/api/fetch-data", methods=["POST"])
def api_fetch_data():
    task_id = uuid.uuid4().hex[:8]
    tasks[task_id] = {"status": "running", "step": "starting", "result": None, "error": None}

    def run():
        try:
            def on_progress(step):
                tasks[task_id]["step"] = step
                log.info(f"[{task_id}] {step}")

            result = fetch_all_data(progress=on_progress)
            tasks[task_id]["status"] = "done"
            tasks[task_id]["result"] = result
            log.info(f"[{task_id}] 완료: 재고 {len(result['inventory'])}건, 주문 {len(result['orders'])}건")
        except Exception as e:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["error"] = str(e)
            log.error(f"[{task_id}] 오류: {e}")

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/fetch-status/<task_id>")
def api_fetch_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    from waitress import serve

    port = 8090
    print(f"\n  iLBiA 물류 대시보드")
    print(f"  http://localhost:{port}")
    print(f"  Ctrl+C로 종료\n")
    serve(app, host="0.0.0.0", port=port, threads=4, channel_timeout=300)
