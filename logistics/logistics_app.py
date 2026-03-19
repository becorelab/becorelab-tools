#!/usr/bin/env python3
"""
iLBiA 물류 대시보드 서버
- 발주대시보드 HTML 서빙
- 이지어드민 데이터 자동 수집 API
- 매일 10시 예약 수집 (APScheduler)
- 로컬 캐시 (data/cache.json) + Firebase Firestore 실시간 연동
"""
import io
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
from openpyxl import Workbook

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
    # 기준 금액: total_settlement (정산금액) — 대표님 판매현황 리포트 기준
    # 참고 금액: total_amount (판매가/소비자가)
    sales = payload.get("sales")
    if sales and sales.get("date"):
        sales_date = sales["date"]
        # orders 필드는 너무 크므로 요약만 저장
        sales_summary = {
            "date": sales_date,
            "timestamp": ts,
            "total_amount": sales.get("total_amount", 0),         # 판매가 (참고용)
            "total_settlement": sales.get("total_settlement", 0), # 정산금액 (기준)
            "total_count": sales.get("total_count", 0),
            "by_channel": sales.get("by_channel", {}),
            "by_product": sales.get("by_product", {}),
        }
        db.collection("sales_daily").document(sales_date).set(sales_summary)
        log.info(f"Firestore sales_daily/{sales_date} 저장 완료 (정산금액: {sales_summary['total_settlement']:,}원)")

        # ERP용 주문 상세 데이터 저장 (sales_daily_orders 컬렉션)
        orders = sales.get("orders", [])
        if orders:
            # Firestore 문서 크기 제한(1MB)을 고려하여 500건씩 분할 저장
            chunk_size = 500
            chunks = [orders[i:i+chunk_size] for i in range(0, len(orders), chunk_size)]
            for idx, chunk in enumerate(chunks):
                db.collection("sales_daily_orders").document(f"{sales_date}_part{idx}").set({
                    "date": sales_date,
                    "part": idx,
                    "total_parts": len(chunks),
                    "orders": chunk,
                })
            log.info(f"Firestore sales_daily_orders/{sales_date} 저장 완료 ({len(orders)}건, {len(chunks)}파트)")


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


# ── 거래처코드 매핑 (이카운트 ERP용) ──
_ERP_CUSTOMER_CODES_PATH = os.path.join(DIR, "erp_customer_codes.json")
_erp_customer_codes = {}
if os.path.exists(_ERP_CUSTOMER_CODES_PATH):
    with open(_ERP_CUSTOMER_CODES_PATH, "r", encoding="utf-8") as _f:
        _erp_customer_codes = json.load(_f)
    log.info(f"ERP 거래처코드 매핑 로드: {len(_erp_customer_codes)}건")


def _load_sales_orders(target_date):
    """매출 주문 상세 데이터 로드 (로컬 캐시 → Firestore 순서)"""
    # 1. 로컬 캐시에서 시도
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
            sales = cache.get("sales", {})
            if sales and sales.get("date") == target_date:
                orders = sales.get("orders", [])
                if orders:
                    log.info(f"ERP: 로컬 캐시에서 {target_date} 주문 {len(orders)}건 로드")
                    return orders
        except Exception as e:
            log.warning(f"ERP: 로컬 캐시 로드 실패: {e}")

    # 2. Firestore에서 시도
    if _firestore_ok:
        try:
            db = fdb.db()
            # 파트 0부터 조회하여 모든 파트 합치기
            all_orders = []
            for part_idx in range(100):  # 최대 100파트
                doc = db.collection("sales_daily_orders").document(f"{target_date}_part{part_idx}").get()
                if not doc.exists:
                    break
                data = doc.to_dict()
                all_orders.extend(data.get("orders", []))
            if all_orders:
                log.info(f"ERP: Firestore에서 {target_date} 주문 {len(all_orders)}건 로드")
                return all_orders
        except Exception as e:
            log.warning(f"ERP: Firestore 로드 실패: {e}")

    return []


def _lookup_customer_code(shop_name):
    """판매처 이름으로 거래처코드 조회 (부분 매칭 지원)"""
    # 정확한 매칭 우선
    if shop_name in _erp_customer_codes:
        return _erp_customer_codes[shop_name]

    # 부분 매칭 (shop_name이 매핑 키에 포함되거나, 매핑 키가 shop_name에 포함)
    shop_lower = shop_name.strip()
    for key, code in _erp_customer_codes.items():
        if shop_lower in key or key in shop_lower:
            return code

    return ""


def _build_erp_rows(orders):
    """주문 데이터를 ERP 양식 행으로 변환"""
    rows = []
    for order in orders:
        shop = order.get("shop", "")
        date_raw = order.get("date", "")
        # 일자: YYYY-MM-DD → YYYYMMDD
        erp_date = date_raw.replace("-", "")

        # 거래처코드 조회
        customer_code = _lookup_customer_code(shop)

        # 품목코드 (상품코드)
        product_code = order.get("code", "")

        # 수량
        qty = order.get("productQty", 0)

        # 정산금액 (supply_price)
        settlement = order.get("settlement", 0)

        # 배송비 (선결제금액) — 현재 데이터에 없으므로 0
        shipping_fee = 0

        # 공급가액 = ROUND(정산금액/1.1, 0) + ROUND(배송비/1.1, 0)
        supply_amount = round(settlement / 1.1) + round(shipping_fee / 1.1)

        # 부가세 = ROUND(공급가액 * 0.1, 0)
        vat = round(supply_amount * 0.1)

        # 공급가합계 = 공급가액 + 부가세
        total_supply = supply_amount + vat

        # ERP 행 구성 (A~Y열 = 25컬럼)
        row = [
            erp_date,           # A: 일자
            "",                 # B: (auto-calculated, skip)
            customer_code,      # C: 거래처코드
            "",                 # D: (skip)
            "00002",            # E: 담당자
            "200",              # F: 출하창고
            "11",               # G: 거래유형
            "",                 # H: 통화
            "",                 # I: 환율
            product_code,       # J: 품목코드
            "",                 # K: 품목명 (ERP 자동)
            "",                 # L: 규격
            qty,                # M: 수량
            "",                 # N: 단가(vat포함)
            "",                 # O: 단가
            "",                 # P: 외화금액
            supply_amount,      # Q: 공급가액
            vat,                # R: 부가세
            total_supply,       # S: 공급가합계
            "",                 # T: 주문번호
            "",                 # U: 수취인
            "",                 # V: 수령자전화
            "",                 # W: 수령자휴대폰
            "",                 # X: 운송장번호
            shipping_fee,       # Y: 배송비
        ]
        rows.append(row)

    return rows


@app.route("/api/sales-daily-erp")
def api_sales_daily_erp():
    """매출 데이터를 이카운트 ERP 양식 엑셀로 다운로드

    쿼리 파라미터:
        date: YYYY-MM-DD (기본값: 오늘)

    반환: .xlsx 파일 다운로드
    """
    target_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))

    try:
        # 주문 상세 데이터 로드
        orders = _load_sales_orders(target_date)
        if not orders:
            return jsonify({
                "status": "empty",
                "message": f"{target_date} 주문 데이터가 없습니다. 먼저 데이터를 수집해주세요."
            }), 404

        # ERP 행 변환
        erp_rows = _build_erp_rows(orders)

        # Excel 생성
        wb = Workbook()
        ws = wb.active
        ws.title = "2.판매입력"

        # 헤더 행
        headers = [
            "일자", "", "거래처코드", "", "담당자", "출하창고", "거래유형",
            "통화", "환율", "품목코드", "품목명", "규격", "수량",
            "단가(vat포함)", "단가", "외화금액", "공급가액", "부가세",
            "공급가합계", "주문번호", "수취인", "수령자전화",
            "수령자휴대폰", "운송장번호", "배송비"
        ]
        ws.append(headers)

        # 데이터 행
        for row in erp_rows:
            ws.append(row)

        # 열 너비 조정
        col_widths = {
            'A': 10, 'C': 14, 'E': 8, 'F': 8, 'G': 8,
            'J': 10, 'M': 8, 'Q': 12, 'R': 10, 'S': 12, 'Y': 10
        }
        for col, width in col_widths.items():
            ws.column_dimensions[col].width = width

        # BytesIO에 저장
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # 매핑 실패 건수 집계
        unmapped = sum(1 for r in erp_rows if not r[2])  # C열(거래처코드)이 빈 건
        if unmapped:
            log.warning(f"ERP 변환: 거래처코드 매핑 실패 {unmapped}건")

        filename = f"이카운트_매출입력_{target_date}.xlsx"
        log.info(f"ERP 엑셀 생성 완료: {target_date} ({len(erp_rows)}건, 매핑실패 {unmapped}건)")

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        log.error(f"ERP 엑셀 생성 오류: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/settlements/<month>")
def api_settlements(month):
    """매출 정산 데이터 조회 (Firestore settlements 컬렉션)"""
    if not _firestore_ok:
        return jsonify({"status": "error", "message": "Firestore 미연결"}), 503
    try:
        db = fdb.db()
        uid = 'JCyLkAQDUmN8DulO3EeQ7FR8pCG3'
        month_doc = db.collection('settlements').document(uid).collection('months').document(month).get()
        result = month_doc.to_dict() if month_doc.exists else {}
        if not result:
            return '', 204
        return jsonify({"status": "ok", "month": month, "data": result})
    except Exception as e:
        log.error(f"[settlements] 조회 오류: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/settlements")
def api_settlements_list():
    """저장된 매출 정산 월 목록 조회"""
    if not _firestore_ok:
        return jsonify({"status": "error", "message": "Firestore 미연결"}), 503
    try:
        db = fdb.db()
        uid = 'JCyLkAQDUmN8DulO3EeQ7FR8pCG3'
        month_docs = db.collection('settlements').document(uid).collection('months').get()
        months = [md.id for md in month_docs]
        months.sort(reverse=True)
        return jsonify({"status": "ok", "months": months})
    except Exception as e:
        log.error(f"[settlements] 목록 오류: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


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
