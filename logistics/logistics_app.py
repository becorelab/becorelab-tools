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
from datetime import datetime, timedelta

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

# ── Firestore 읽기 캐시 (메모리 + 로컬 파일) — 읽기 쿼터 절약 ──
_sales_cache = {}  # 메모리 캐시: { "2026-03-19": data }
_SALES_FILE_CACHE_DIR = os.path.join(DIR, "data", "sales_cache")

def _get_sales_cached(date_str):
    """sales_daily 데이터를 3단계로 조회: 메모리 → 로컬파일 → Firestore"""
    # 1. 메모리 캐시
    if date_str in _sales_cache:
        return _sales_cache[date_str]

    # 2. 로컬 파일 캐시
    os.makedirs(_SALES_FILE_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(_SALES_FILE_CACHE_DIR, f"{date_str}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            _sales_cache[date_str] = data
            return data
        except Exception:
            pass

    # 3. Firestore (최후 수단)
    if not _firestore_ok:
        return None
    try:
        doc = fdb.db().collection("sales_daily").document(date_str).get()
        data = doc.to_dict() if doc.exists else None
    except Exception as e:
        log.warning(f"Firestore 읽기 실패 ({date_str}): {e}")
        return None

    # 데이터가 있으면 로컬 파일에 캐시 저장 (다음번엔 Firestore 안 읽음)
    if data:
        _sales_cache[date_str] = data
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass
    return data


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

        # 로컬 파일 캐시에도 저장 (Firestore 읽기 쿼터 절약)
        os.makedirs(_SALES_FILE_CACHE_DIR, exist_ok=True)
        try:
            cache_file = os.path.join(_SALES_FILE_CACHE_DIR, f"{sales_date}.json")
            with open(cache_file, "w", encoding="utf-8") as cf:
                json.dump(sales_summary, cf, ensure_ascii=False)
            _sales_cache[sales_date] = sales_summary
            log.info(f"로컬 매출 캐시 저장: {cache_file}")
        except Exception as ce:
            log.warning(f"로컬 매출 캐시 저장 실패: {ce}")

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
def run_scrape(task_id=None, scheduled=False, sales_target_date=None):
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

        result = fetch_all_data(progress=on_progress, sales_target_date=sales_target_date)
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
    sales_target_date = request.json.get("date") # 요청 바디에서 "date" 파라미터 추출
    tasks[task_id] = {
        "status": "running",
        "step": "starting",
        "result": None,
        "error": None,
    }
    # sales_target_date 인자를 run_scrape에 전달
    threading.Thread(target=run_scrape, args=(task_id, False, sales_target_date), daemon=True).start()
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
    """매출 일별 데이터 조회 (쿼리: ?date=2026-03-16 또는 ?days=7)
    메모리 캐시 적용으로 Firestore 읽기 쿼터 절약"""
    if not _firestore_ok:
        return jsonify({"status": "no_firestore"}), 503
    try:
        target_date = request.args.get("date")
        if target_date:
            data = _get_sales_cached(target_date)
            if data:
                return jsonify({"status": "ok", "data": data})
            return jsonify({"status": "empty"}), 204

        days = int(request.args.get("days", 7))
        from datetime import timedelta
        results = []
        for i in range(days):
            d = (datetime.now() - timedelta(days=i+1)).strftime("%Y-%m-%d")
            data = _get_sales_cached(d)
            if data:
                results.append(data)
        return jsonify({"status": "ok", "data": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sales-daily-orders")
def api_sales_daily_orders():
    """옵션별 주문 상세 조회 (쿼리: ?date=2026-04-03)
    각 주문의 상품코드, 옵션명, 수량, 정산금액 등 포함"""
    target_date = request.args.get("date")
    if not target_date:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        orders = _load_sales_orders(target_date)
        if not orders:
            return jsonify({"status": "empty", "date": target_date, "message": "주문 데이터 없음 (이지어드민 수집 필요)"}), 204
        # 옵션별 집계
        by_option = {}
        for o in orders:
            key = f"{o.get('code','?')}_{o.get('option','')}"
            if key not in by_option:
                by_option[key] = {
                    "code": o.get("code", ""),
                    "name": o.get("name", ""),
                    "option": o.get("option", ""),
                    "nameOpt": o.get("nameOpt", ""),
                    "qty": 0,
                    "amount": 0,
                    "settlement": 0,
                    "channels": {},
                }
            by_option[key]["qty"] += o.get("productQty", 0) or o.get("orderQty", 0)
            by_option[key]["amount"] += o.get("amount", 0)
            by_option[key]["settlement"] += o.get("settlement", 0)
            shop = o.get("shop", "기타")
            if shop not in by_option[key]["channels"]:
                by_option[key]["channels"][shop] = {"qty": 0, "settlement": 0}
            by_option[key]["channels"][shop]["qty"] += o.get("productQty", 0) or o.get("orderQty", 0)
            by_option[key]["channels"][shop]["settlement"] += o.get("settlement", 0)
        # 정산금액 순 정렬
        sorted_options = sorted(by_option.values(), key=lambda x: x["settlement"], reverse=True)
        return jsonify({
            "status": "ok",
            "date": target_date,
            "total_orders": len(orders),
            "by_option": sorted_options,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sales-monthly")
def api_sales_monthly():
    """월간 누적 매출 (Firestore 읽기 최소화 — 메모리 캐시 활용)
    쿼리: ?month=2026-03 (생략 시 이번 달)"""
    if not _firestore_ok:
        return jsonify({"status": "no_firestore"}), 503
    try:
        from datetime import timedelta
        month = request.args.get("month", datetime.now().strftime("%Y-%m"))
        year, mon = int(month[:4]), int(month[5:7])

        total_settlement = 0
        total_amount = 0
        total_count = 0
        days_with_data = 0

        # 해당 월의 1일부터 말일까지 순회
        import calendar
        last_day = calendar.monthrange(year, mon)[1]
        today = datetime.now().strftime("%Y-%m-%d")

        for day in range(1, last_day + 1):
            d = f"{year}-{mon:02d}-{day:02d}"
            if d > today:
                break
            data = _get_sales_cached(d)
            if data:
                total_settlement += data.get("total_settlement", 0)
                total_amount += data.get("total_amount", 0)
                total_count += data.get("total_count", 0)
                days_with_data += 1

        return jsonify({
            "status": "ok",
            "month": month,
            "days_with_data": days_with_data,
            "total_settlement": total_settlement,
            "total_amount": total_amount,
            "total_count": total_count,
        })
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


@app.route("/api/cache-sales-from-firestore")
def api_cache_sales_from_firestore():
    """Firestore의 sales_daily를 로컬 파일로 일괄 캐시 (1회 실행용)
    쿼리: ?month=2026-03 (생략 시 이번 달)"""
    if not _firestore_ok:
        return jsonify({"status": "no_firestore"}), 503
    try:
        import calendar
        from datetime import timedelta
        month = request.args.get("month", datetime.now().strftime("%Y-%m"))
        year, mon = int(month[:4]), int(month[5:7])
        last_day = calendar.monthrange(year, mon)[1]
        today = datetime.now().strftime("%Y-%m-%d")

        os.makedirs(_SALES_FILE_CACHE_DIR, exist_ok=True)
        cached = 0
        skipped = 0
        for day in range(1, last_day + 1):
            d = f"{year}-{mon:02d}-{day:02d}"
            if d > today:
                break
            cache_file = os.path.join(_SALES_FILE_CACHE_DIR, f"{d}.json")
            if os.path.exists(cache_file):
                skipped += 1
                continue
            doc = fdb.db().collection("sales_daily").document(d).get()
            if doc.exists:
                data = doc.to_dict()
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                _sales_cache[d] = data
                cached += 1
        return jsonify({"status": "ok", "month": month, "cached": cached, "skipped": skipped})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── 상품코드→상품명 매핑 ──
_PRODUCT_NAMES = {
    "S10357": "건조기시트 코튼블루", "S10358": "건조기시트 베이비크림",
    "S13565": "건조기시트 바이올렛머스크", "10892": "식기세척기세제(하트)",
    "10460": "식기세척기세제", "12594": "캡슐세탁세제 버블코튼",
    "10894": "하트 틴케이스", "S10897": "하트집게 Light Blue",
    "S10896": "하트집게 Deep Blue", "S13591": "섬유탈취제 100ml",
    "S13590": "섬유탈취제 400ml", "10909": "스페셜에디션 패키지",
    "10964": "올인원 세제수세미", "13208": "얼룩제거제 350ml",
    "13209": "얼룩제거제 휴대용100ml", "10377": "이염방지시트",
    "11511": "세제샘플 테스트키트", "11512": "건조기 테스트키트",
    "11789": "감사카드", "13578": "건조기 바이올렛2장추가",
    "13628": "캡슐세제 틴케이스", "13996": "캡슐표백제",
    "13998": "건조기시트 베이비크림(쿠팡)", "13303": "리필세트",
    "09996": "세제보관용기", "9996": "세제보관용기",
    "10378": "다목적세정제", "10530": "에코백",
    "10922": "스페셜에디션(LightBlue)", "10923": "스페셜에디션(DeepBlue)",
    "13234": "건조기 베이비크림 낱장", "S10365": "건조기시트 믹스",
    "13394": "계란보관함", "13600": "스타배송 건조기 코튼블루",
    "13858": "섬유탈취제 샘플키트", "13623": "섬유탈취제카드",
    "S13451": "샘플(소)", "S13452": "샘플(중)", "S13453": "샘플(대)",
    "S13450": "샘플(극소)", "12489": "수세미(유통기한경과)",
    "11756": "식기세척기세제(로켓/2개입)",
    "S13381": "2단구급함(대)", "S13382": "2단구급함(소)",
    "S13383": "멀티탭보관함(그린티-대)", "S13384": "멀티탭보관함(그린티-중)",
    "S13385": "멀티탭보관함(카푸치노-대)", "S13386": "멀티탭보관함(카푸치노-중)",
    "S13388": "와인보관함(1칸)", "S13389": "와인보관함(2칸)", "S13390": "와인보관함(3칸)",
    "S13392": "캡슐보관함(화이트)", "S13393": "캡슐보관함(그린)",
    "13998": "PU가죽홀더",
}

def _product_name(code, by_product=None):
    """상품코드→상품명 변환"""
    if by_product and code in by_product:
        name = by_product[code].get("name", "")
        if name:
            # [비코어랩] 접두사 제거
            import re
            name = re.sub(r'^\[비코어랩\]\s*', '', name)
            name = re.sub(r'^[♥★(공박스)]+\s*', '', name)
            name = name.strip()
            if name:
                return name
    return _PRODUCT_NAMES.get(code, code)

# ── 채널명 정리 ──
def _channel_short(ch):
    """채널명을 짧게 정리"""
    mapping = {
        "비코어랩 카페24 일비아": "카페24",
        "비코어랩 로켓배송": "쿠팡 로켓배송",
        "비코어랩 11번가": "11번가",
        "비코어랩 일비아 스스": "스마트스토어",
        "(주)비코어랩": "자사몰",
        "비코어랩 이마트": "이마트",
        "비코어랩 G마켓": "G마켓",
        "비코어랩 옥션": "옥션",
        "비코어랩 오늘의집": "오늘의집",
    }
    return mapping.get(ch, ch)


@app.route("/api/daily-report")
def api_daily_report():
    """완성된 일매출 보고서 텍스트 반환 (DeepSeek도 그대로 전달 가능)
    쿼리: ?date=2026-03-19 (생략 시 어제)"""
    from datetime import timedelta
    try:
        target = request.args.get("date")
        if not target:
            target = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # 어제 + 전일 매출
        data = _get_sales_cached(target)
        if not data:
            return jsonify({"status": "empty", "report": f"❌ {target} 매출 데이터 없음"}), 204

        # 전일 데이터 (비교용)
        d = datetime.strptime(target, "%Y-%m-%d")
        prev_date = (d - timedelta(days=1)).strftime("%Y-%m-%d")
        prev = _get_sales_cached(prev_date)

        settlement = data.get("total_settlement", 0)
        amount = data.get("total_amount", 0)
        count = data.get("total_count", 0)

        # 전일 대비
        if prev and prev.get("total_settlement"):
            prev_s = prev["total_settlement"]
            change = (settlement - prev_s) / prev_s * 100
            change_str = f"▲{change:.1f}%" if change >= 0 else f"▼{abs(change):.1f}%"
        else:
            change_str = "전일 데이터 없음"

        # 월간 누적
        month = target[:7]
        year, mon = int(month[:4]), int(month[5:7])
        import calendar as cal
        last_day = cal.monthrange(year, mon)[1]
        today_str = datetime.now().strftime("%Y-%m-%d")
        m_total = 0
        m_days = 0
        for day in range(1, last_day + 1):
            dd = f"{year}-{mon:02d}-{day:02d}"
            if dd > today_str:
                break
            dd_data = _get_sales_cached(dd)
            if dd_data:
                m_total += dd_data.get("total_settlement", 0)
                m_days += 1

        # 채널별 (정산금액 큰 순)
        by_ch = data.get("by_channel", {})
        ch_sorted = sorted(by_ch.items(), key=lambda x: x[1].get("settlement", 0), reverse=True)

        # 재고 현황
        cache = load_cache()
        inv = cache.get("inventory", {}) if cache else {}
        by_product = data.get("by_product", {})

        # 재고 알림
        alerts_red = []
        alerts_yellow = []
        for code, info in sorted(inv.items()):
            stock = info.get("stock")
            if stock is None:
                continue
            name = _product_name(code, by_product)
            if isinstance(stock, (int, float)):
                if stock < 0:
                    alerts_red.append(f"🔴 {name} — {stock}개 (마이너스 재고!)")
                elif 0 < stock <= 10:
                    alerts_yellow.append(f"⚠️ {name} — {stock}개")

        # 상품 TOP 5
        pr_sorted = sorted(by_product.items(), key=lambda x: x[1].get("settlement", 0), reverse=True)

        # 보고서 텍스트 생성
        lines = []
        lines.append(f"📊 iLBiA 일간 보고 ({target})")
        lines.append("")
        lines.append(f"💵 총 정산: ₩{settlement:,} (전일 대비 {change_str})")
        lines.append(f"💰 총 판매: ₩{amount:,} (참고)")
        lines.append(f"📦 주문: {count}건")
        lines.append("")
        lines.append(f"📊 {mon}월 누적: ₩{m_total:,} ({m_days}일간)")
        lines.append("")

        # 채널별
        lines.append("📈 채널별 (정산금액 큰 순)")
        for ch_name, ch_data in ch_sorted:
            short = _channel_short(ch_name)
            ch_count = ch_data.get("count", 0)
            ch_settle = ch_data.get("settlement", 0)
            lines.append(f"{short} — {ch_count}건 | ₩{ch_settle:,}")
        lines.append("")

        # 재고 알림
        lines.append("🚨 재고 알림")
        if alerts_red or alerts_yellow:
            for a in alerts_red:
                lines.append(a)
            for a in alerts_yellow:
                lines.append(a)
        else:
            lines.append("✅ 모든 상품 재고 양호")
        lines.append("")

        # 상품 TOP 5
        lines.append("🏷️ 상품 TOP 5 (정산금액)")
        for code, pdata in pr_sorted[:5]:
            name = _product_name(code, by_product)
            qty = pdata.get("qty", 0)
            ps = pdata.get("settlement", 0)
            lines.append(f"{name} — {qty}개 | ₩{ps:,}")

        report = "\n".join(lines)

        # ?format=text 이면 plain text 반환 (인코딩 깨짐 방지)
        if request.args.get("format") == "text":
            resp = make_response(report)
            resp.headers["Content-Type"] = "text/plain; charset=utf-8"
            return resp
        return jsonify({"status": "ok", "date": target, "report": report})
    except Exception as e:
        if request.args.get("format") == "text":
            return make_response(f"❌ 보고서 생성 실패: {str(e)}", 500)
        return jsonify({"status": "error", "report": f"❌ 보고서 생성 실패: {str(e)}"}), 500


@app.route("/api/inventory-report")
def api_inventory_report():
    """완성된 재고 보고서 텍스트 반환 (상품명 매핑 완료)"""
    try:
        cache = load_cache()
        if not cache or "inventory" not in cache:
            return jsonify({"status": "empty", "report": "❌ 재고 데이터 없음"}), 204

        inv = cache["inventory"]
        alerts_red = []
        alerts_yellow = []
        normal = []

        for code in sorted(inv.keys()):
            info = inv[code]
            stock = info.get("stock")
            if stock is None:
                continue
            name = _product_name(code)
            if isinstance(stock, (int, float)):
                if stock < 0:
                    alerts_red.append((name, stock))
                elif 0 < stock <= 10:
                    alerts_yellow.append((name, stock))
                elif stock > 0:
                    normal.append((name, stock))

        lines = ["📦 재고 현황 보고서"]
        lines.append("")

        if alerts_red:
            lines.append("🔴 마이너스 재고 (긴급 발주 필요)")
            for name, stock in sorted(alerts_red, key=lambda x: x[1]):
                lines.append(f"  {name} — {stock}개")
            lines.append("")

        if alerts_yellow:
            lines.append("⚠️ 재고 부족 (10개 이하)")
            for name, stock in sorted(alerts_yellow, key=lambda x: x[1]):
                lines.append(f"  {name} — {stock}개")
            lines.append("")

        if normal:
            lines.append("✅ 정상 재고")
            for name, stock in sorted(normal, key=lambda x: -x[1]):
                lines.append(f"  {name} — {stock:,}개")

        report = "\n".join(lines)
        if request.args.get("format") == "text":
            resp = make_response(report)
            resp.headers["Content-Type"] = "text/plain; charset=utf-8"
            return resp
        return jsonify({"status": "ok", "report": report})
    except Exception as e:
        return jsonify({"status": "error", "report": f"❌ 재고 보고서 생성 실패: {str(e)}"}), 500


@app.route("/api/cost-report")
def api_cost_report():
    """API 비용 현황 보고서 (Anthropic + Gemini + OpenClaw)"""
    import urllib.request
    import urllib.error
    lines = ["💰 API 비용 현황 보고서", ""]

    # 1. Anthropic API 사용량
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sourcing', 'analyzer'))
        from reviews import ANTHROPIC_API_KEY
        if ANTHROPIC_API_KEY:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/usage",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            lines.append("🤖 Anthropic API (소싱콕 리뷰분석)")
            if "input_tokens" in data:
                lines.append(f"  입력 토큰: {data.get('input_tokens', 0):,}")
                lines.append(f"  출력 토큰: {data.get('output_tokens', 0):,}")
            else:
                lines.append(f"  응답: {json.dumps(data, ensure_ascii=False)[:200]}")
        else:
            lines.append("🤖 Anthropic API: 키 없음")
    except Exception as e:
        lines.append(f"🤖 Anthropic API: 조회 실패 ({str(e)[:80]})")
    lines.append("")

    # 2. Gemini API (무료 티어 — 비용 없음)
    lines.append("✨ Google Gemini API (소싱콕 상세분석)")
    lines.append("  플랜: 무료 티어 (Gemini 2.5 Flash)")
    lines.append("  과금: 없음 (무료 한도 내 사용)")
    lines.append("")

    # 3. Claude Code 채널 두리
    lines.append("🐰 Claude Code 채널 두리 (@doori0321_bot)")
    lines.append("  모델: Claude Sonnet 4.6")
    lines.append("  과금: Max 구독 포함 — $0")
    lines.append("")

    # 4. OpenClaw 상태
    try:
        req2 = urllib.request.Request("http://localhost:18789/api/status")
        with urllib.request.urlopen(req2, timeout=3) as r:
            lines.append("🔧 OpenClaw: 실행 중 (Haiku 과금 확인 필요)")
    except Exception:
        lines.append("🔧 OpenClaw: 중지됨 (과금 없음)")

    report = "\n".join(lines)
    if request.args.get("format") == "text":
        resp = make_response(report)
        resp.headers["Content-Type"] = "text/plain; charset=utf-8"
        return resp
    return jsonify({"status": "ok", "report": report})


# ── 발주 분석 API ──

PRODUCTS_LIST = [
    {"code": "S10357", "name": "건조기시트 [코튼블루]", "moq": 2700},
    {"code": "S10358", "name": "건조기시트 [베이비크림]", "moq": 2700},
    {"code": "S13565", "name": "건조기시트 [바이올렛머스크]", "moq": 2700},
    {"code": "10892", "name": "식기세척기세제 (하트)", "moq": 3000},
    {"code": "10460", "name": "식기세척기세제 (일반)", "moq": 3000},
    {"code": "13208", "name": "얼룩제거제 350ml", "moq": 3000},
    {"code": "13209", "name": "얼룩제거제 100ml", "moq": 3000},
    {"code": "S13591", "name": "섬유탈취제 100ml", "moq": 5000},
    {"code": "S13590", "name": "섬유탈취제 400ml", "moq": 5000},
    {"code": "10964", "name": "수세미 36매", "moq": 1500},
    {"code": "12594", "name": "캡슐세탁세제 버블코튼", "moq": 3000},
    {"code": "S10897", "name": "하트 집게 (A)", "moq": 1000},
    {"code": "10894", "name": "하트 틴케이스", "moq": 1000},
    {"code": "S10896", "name": "하트 집게 (B)", "moq": 1000},
    {"code": "13628", "name": "캡슐세제 틴케이스", "moq": 1000},
    {"code": "10378", "name": "다목적세정제", "moq": 3000},
]


@app.route("/api/order-analysis")
def api_order_analysis():
    """발주 분석 — orders.html calcData()와 동일한 로직"""
    import math

    lead = int(request.args.get("lead", 30))
    safety = int(request.args.get("safety", 30))
    target = int(request.args.get("target", 30))
    window = int(request.args.get("window", 90))
    reorder_days = lead + safety

    cache = load_cache()
    if cache is None:
        return jsonify({"status": "no_data", "error": "캐시 데이터 없음"}), 204

    inventory = cache.get("inventory", {})
    orders = cache.get("orders", [])

    purchases_list = []
    moq_override = {}
    if _firestore_ok:
        try:
            doc = fdb.db().collection("logistics").document("purchases").get()
            if doc.exists:
                d = doc.to_dict()
                purchases_list = d.get("purchases", [])
                moq_override = d.get("moq", {})
        except Exception:
            pass

    sales_map = {}
    for o in orders:
        code = o.get("code", "")
        sales_map[code] = sales_map.get(code, 0) + o.get("qty", 0)

    results = []
    for p in PRODUCTS_LIST:
        code = p["code"]
        name = p["name"]
        moq_val = moq_override.get(code, p["moq"])
        total_sold = sales_map.get(code, 0)
        daily_avg = total_sold / window if window > 0 else 0
        stock_info = inventory.get(code, {})
        current_stock = stock_info.get("stock") if stock_info else None

        pending = [x for x in purchases_list if x.get("code") == code and x.get("status") == "pending"]
        pending_qty = sum(x.get("qty", 0) for x in pending)

        reorder_point = reorder_days * daily_avg

        days_to_reorder = None
        days_to_stockout = None
        status = "unknown"

        if current_stock is not None:
            if daily_avg == 0:
                days_to_reorder = 999
                days_to_stockout = 999
                status = "ok"
            else:
                days_to_reorder = (current_stock - reorder_point) / daily_avg
                days_to_stockout = current_stock / daily_avg
                if days_to_reorder <= 0:
                    status = "warning" if pending_qty > 0 else "urgent"
                elif days_to_reorder <= 30:
                    status = "warning"
                else:
                    status = "ok"

        recommend_qty = max(moq_val, math.ceil(target * daily_avg)) if daily_avg > 0 else moq_val

        results.append({
            "code": code,
            "name": name,
            "current_stock": current_stock,
            "daily_avg": round(daily_avg, 1),
            "reorder_point": round(reorder_point),
            "days_to_reorder": round(days_to_reorder, 1) if days_to_reorder is not None else None,
            "days_to_stockout": round(days_to_stockout, 1) if days_to_stockout is not None else None,
            "status": status,
            "recommend_qty": recommend_qty,
            "moq": moq_val,
            "pending_qty": pending_qty,
            "total_sold": total_sold,
            "period_days": window,
        })

    urgent = [r for r in results if r["status"] == "urgent"]
    warning = [r for r in results if r["status"] == "warning"]
    ok = [r for r in results if r["status"] == "ok"]

    fmt = request.args.get("format", "")
    if fmt == "text":
        lines = [f"📦 발주 분석 보고서 ({lead}일 리드타임 + {safety}일 안전재고)\n"]
        if urgent:
            lines.append("🔴 즉시 발주 필요:")
            for r in urgent:
                lines.append(f"  • {r['name']} — 재고 {r['current_stock']}개, 일평균 {r['daily_avg']}개, 권장 {r['recommend_qty']}개")
        if warning:
            lines.append("\n🟡 30일 내 발주:")
            for r in warning:
                pend = f" (발주중 {r['pending_qty']}개)" if r['pending_qty'] > 0 else ""
                lines.append(f"  • {r['name']} — 재고 {r['current_stock']}개, {round(r['days_to_reorder'])}일 후 재주문점{pend}")
        if ok:
            lines.append("\n✅ 양호:")
            for r in ok:
                lines.append(f"  • {r['name']} — 재고 {r['current_stock']}개, {round(r['days_to_reorder'])}일 여유")
        return "\n".join(lines), 200, {"Content-Type": "text/plain; charset=utf-8"}

    return jsonify({
        "status": "ok",
        "summary": {"urgent": len(urgent), "warning": len(warning), "ok": len(ok)},
        "products": results,
    })


if __name__ == "__main__":
    from waitress import serve

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
