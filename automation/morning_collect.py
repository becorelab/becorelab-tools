"""
비코어랩 새벽 자동화 스크립트
- 서버 체크 + 자동 복구
- 골드박스 수집
- 이지어드민 수집
- 매출/재고/발주 데이터 수집
- API 비용 수집
- 결과 저장 (morning_data.json)
- 에러 시 텔레그램 알림

Windows 작업 스케줄러에서 매일 03:50에 실행
"""
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

import requests

# config 임포트
sys.path.insert(0, os.path.dirname(__file__))
from config import (
    SERVICES, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    DEEPSEEK_API_KEY, DATA_DIR, OUTPUT_JSON, LOG_FILE, yesterday_str,
)

# ── 로깅 설정 ──
def setup_logging():
    os.makedirs(DATA_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("morning")

log = setup_logging()


# ── 유틸리티 ──
def check_http(url, timeout=5):
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code < 500
    except Exception:
        return False


def check_socket(url, timeout=2):
    """포트 LISTENING 상태만 체크 (SSE 등 long-polling 엔드포인트용)"""
    import socket
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def check_process(keyword):
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%{keyword}%'\").ProcessId"],
            capture_output=True, text=True, timeout=10,
        )
        pids = [l.strip() for l in result.stdout.strip().split("\n") if l.strip().isdigit()]
        return len(pids) > 0
    except Exception:
        return False


def start_service(name, cmd, cwd):
    try:
        subprocess.Popen(
            cmd, cwd=cwd,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        log.info(f"  -> {name} 기동 명령 실행")
        return True
    except Exception as e:
        log.error(f"  -> {name} 기동 실패: {e}")
        return False


def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        log.error(f"텔레그램 전송 실패: {e}")


# ── 1단계: 서버 체크 + 자동 복구 ──
def step1_health_check():
    log.info("=" * 40)
    log.info("[1단계] 서버 체크 + 자동 복구")
    results = {}

    for key, svc in SERVICES.items():
        name = svc["name"]

        if svc.get("url"):
            # SSE 엔드포인트는 long-polling이라 HTTP GET이 timeout됨 → socket 체크
            if "/sse" in svc.get("health_path", ""):
                alive = check_socket(svc["url"])
            else:
                alive = check_http(svc["url"] + svc.get("health_path", "/"))
        else:
            alive = check_process(svc["process_keyword"])

        if alive:
            log.info(f"  {name}: 정상")
            results[key] = "ok"
        else:
            log.warning(f"  {name}: 죽어있음 -> 재시작")
            # Chrome CDP는 기존 크롬 먼저 죽이고 재시작
            if key == "chrome_cdp":
                log.info("  -> 기존 크롬 프로세스 종료 중...")
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force"],
                    capture_output=True, timeout=10,
                )
                time.sleep(3)
            ok = start_service(name, svc["start_cmd"], svc["cwd"])
            results[key] = "restarted" if ok else "failed"

    # 재시작한 서비스 있으면 60초까지 5초마다 재확인 (점진적 재시도)
    restarted = [k for k, v in results.items() if v == "restarted"]
    if restarted:
        log.info("  부팅 대기 후 재확인 (최대 60초)...")
        max_wait = 60
        elapsed = 0
        pending = list(restarted)
        while pending and elapsed < max_wait:
            time.sleep(5)
            elapsed += 5
            still_dead = []
            for key in pending:
                svc = SERVICES[key]
                if svc.get("url"):
                    if "/sse" in svc.get("health_path", ""):
                        alive = check_socket(svc["url"])
                    else:
                        alive = check_http(svc["url"] + svc.get("health_path", "/"))
                else:
                    alive = check_process(svc["process_keyword"])
                if alive:
                    log.info(f"  {svc['name']}: 재시작 성공 ({elapsed}초)")
                else:
                    still_dead.append(key)
            pending = still_dead

        for key in pending:
            results[key] = "failed"
            log.error(f"  {SERVICES[key]['name']} 재시작 실패! ({max_wait}초 초과)")

    return results


# ── 1.5단계: 쿠팡윙 로그인 ──
def step1_5_wing_login():
    log.info("[1.5단계] 쿠팡윙 로그인")
    base = "http://localhost:8090"
    try:
        # 상태 확인
        r = requests.get(f"{base}/api/wing/status", timeout=10)
        status = r.json()
        if status.get("wing_ok") and status.get("logged_in"):
            log.info("  쿠팡윙: 이미 로그인됨")
            return "already_logged_in"
        # 로그인 시도
        r = requests.post(f"{base}/api/wing/login", timeout=60)
        log.info(f"  쿠팡윙 로그인 시도: {r.json().get('message', '')}")
        time.sleep(15)
        # 재확인
        r = requests.get(f"{base}/api/wing/status", timeout=10)
        if r.json().get("wing_ok"):
            log.info("  쿠팡윙: 로그인 성공")
            return "ok"
        else:
            log.warning("  쿠팡윙: 로그인 실패")
            return "failed"
    except Exception as e:
        log.error(f"  쿠팡윙 로그인 실패: {e}")
        return f"error: {e}"


# ── 2단계: 골드박스 수집 ──
def step2_goldbox_scan():
    log.info("[2단계] 골드박스 수집")
    base = "http://localhost:8090"

    # 골드박스 크롤링 시작
    r = requests.post(f"{base}/api/goldbox/start", timeout=10)
    log.info(f"  골드박스 크롤링 시작: {r.status_code}")

    # 2분 대기
    log.info("  2분 대기 (크롤링 중)...")
    time.sleep(120)

    # 자동 스캔 시작
    r = requests.post(f"{base}/api/goldbox/auto-scan", json={"delay": 15}, timeout=10)
    log.info(f"  자동 스캔 시작: {r.status_code}")

    # 폴링 (30초 간격, 최대 20분)
    data = {}
    for i in range(40):
        time.sleep(30)
        try:
            r = requests.get(f"{base}/api/goldbox/auto-scan/status", timeout=10)
            data = r.json()
            phase = data.get("phase", "")
            log.info(f"  스캔 상태: {phase}")
            if phase in ("done", "error"):
                break
        except Exception as e:
            log.warning(f"  폴링 실패: {e}")

    # TOP 3 추출
    results = data.get("results", [])
    top3 = sorted(results, key=lambda x: x.get("opportunity_score", 0), reverse=True)[:3]
    log.info(f"  골드박스 TOP 3: {len(top3)}개")
    return top3


# ── 3단계: 이지어드민 수집 ──
def step3_ezadmin_fetch():
    log.info("[3단계] 이지어드민 데이터 수집")
    base = "http://localhost:8082"

    r = requests.post(f"{base}/api/fetch-data", json={}, timeout=10)
    task_id = r.json().get("task_id")
    log.info(f"  수집 시작 (task_id: {task_id})")

    status = "unknown"
    error = None
    for i in range(40):  # 15초 x 40 = 10분
        time.sleep(15)
        try:
            r = requests.get(f"{base}/api/fetch-status/{task_id}", timeout=10)
            task = r.json()
            status = task.get("status", "")
            step = task.get("step", "")
            error = task.get("error")
            log.info(f"  상태: {status} / {step}")
            if status in ("done", "error", "failed"):
                break
        except Exception as e:
            log.warning(f"  폴링 실패: {e}")

    return {"task_id": task_id, "status": status, "error": error}


# ── 4단계: 매출/재고/발주 데이터 수집 ──
def step4_collect_reports():
    log.info("[4단계] 매출/재고/발주 데이터 수집")
    base = "http://localhost:8082"
    yesterday = yesterday_str()
    reports = {}

    endpoints = {
        "daily_report": "/api/daily-report?format=text",
        "inventory": "/api/inventory-report?format=text",
        "order_analysis": "/api/order-analysis?format=text",
        "sales_daily": f"/api/sales-daily?date={yesterday}",
    }

    for key, path in endpoints.items():
        try:
            r = requests.get(f"{base}{path}", timeout=15)
            if r.status_code in (200, 204):
                if r.status_code == 204 or not r.text.strip():
                    reports[key] = "data_empty"
                    log.info(f"  {key}: 데이터 없음 (204/빈 응답)")
                    continue
                ct = r.headers.get("Content-Type", "")
                if "json" in ct:
                    reports[key] = r.json()
                else:
                    reports[key] = r.text
                log.info(f"  {key}: OK")
            else:
                reports[key] = f"HTTP {r.status_code}"
                log.warning(f"  {key}: HTTP {r.status_code}")
        except Exception as e:
            reports[key] = f"error: {e}"
            log.error(f"  {key} 실패: {e}")

    return reports


# ── 5단계: API 비용 수집 ──
def step5_api_costs():
    log.info("[5단계] API 비용 수집")
    costs = {}

    # DeepSeek 잔액
    try:
        r = requests.get(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            costs["deepseek"] = data
            log.info(f"  DeepSeek: {data}")
        else:
            costs["deepseek"] = f"HTTP {r.status_code}"
            log.warning(f"  DeepSeek: HTTP {r.status_code}")
    except Exception as e:
        costs["deepseek"] = f"error: {e}"
        log.warning(f"  DeepSeek 실패: {e}")

    # Z.AI - API 조회 불가 (대시보드만)
    costs["z_ai"] = "$10 monthly (dashboard: z.ai/dashboard)"

    # Fireworks - API 조회 불가
    costs["fireworks"] = "dashboard: fireworks.ai/account/usage"

    # Google AI - API 조회 불가
    costs["google_ai"] = "dashboard: aistudio.google.com/billing"

    # Anthropic - API 조회 불가
    costs["anthropic"] = "Max plan (dashboard: console.anthropic.com)"

    log.info("  Z.AI/Fireworks/Google/Anthropic: 대시보드 확인 필요")
    return costs


# ── 6단계: 결과 저장 ──
def step6_save_results(server_status, goldbox_top3, ezadmin, reports, api_costs, errors):
    log.info("[6단계] 결과 저장")
    os.makedirs(DATA_DIR, exist_ok=True)

    result = {
        "timestamp": datetime.now().isoformat(),
        "date": yesterday_str(),
        "weekday": ["월", "화", "수", "목", "금", "토", "일"][datetime.now().weekday()],
        "server_status": server_status,
        "goldbox_top3": goldbox_top3,
        "ezadmin_fetch": ezadmin,
        "daily_report": reports.get("daily_report"),
        "inventory": reports.get("inventory"),
        "order_analysis": reports.get("order_analysis"),
        "sales_daily": reports.get("sales_daily"),
        "api_costs": api_costs,
        "errors": errors,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info(f"  저장 완료: {OUTPUT_JSON}")
    return result


# ── 7단계: 텔레그램 에러 알림 ──
def step7_telegram_alert(server_status, errors):
    log.info("[7단계] 에러 체크")
    critical = []

    for key, status in server_status.items():
        if status == "failed":
            name = SERVICES[key]["name"]
            critical.append(f"- {name} 복구 실패")

    if critical or errors:
        lines = ["[새벽 자동화 알림]", ""]
        if critical:
            lines.append("서버 복구 실패:")
            lines.extend(critical)
        if errors:
            lines.append("")
            lines.append("기타 에러:")
            for e in errors[:5]:
                lines.append(f"- {e}")

        send_telegram("\n".join(lines))
        log.info("  텔레그램 에러 알림 전송")
    else:
        log.info("  에러 없음 - 알림 미전송")


# ── 메인 ──
def main():
    log.info("=" * 50)
    log.info(f"새벽 자동화 시작 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    errors = []

    # 1단계: 서버 체크
    try:
        server_status = step1_health_check()
    except Exception as e:
        log.error(f"1단계 실패: {e}")
        server_status = {"error": str(e)}
        errors.append(f"1단계(서버체크): {e}")

    # 1.5단계: 쿠팡윙 로그인
    try:
        step1_5_wing_login()
    except Exception as e:
        log.error(f"1.5단계 실패: {e}")
        errors.append(f"1.5단계(윙로그인): {e}")

    # 2단계: 골드박스
    goldbox_top3 = []
    try:
        goldbox_top3 = step2_goldbox_scan()
    except Exception as e:
        log.error(f"2단계 실패: {e}")
        errors.append(f"2단계(골드박스): {e}")

    # 3단계: 이지어드민
    ezadmin = {}
    try:
        ezadmin = step3_ezadmin_fetch()
    except Exception as e:
        log.error(f"3단계 실패: {e}")
        errors.append(f"3단계(이지어드민): {e}")

    # 4단계: 매출/재고/발주
    reports = {}
    try:
        reports = step4_collect_reports()
    except Exception as e:
        log.error(f"4단계 실패: {e}")
        errors.append(f"4단계(보고서): {e}")

    # 5단계: API 비용
    api_costs = {}
    try:
        api_costs = step5_api_costs()
    except Exception as e:
        log.error(f"5단계 실패: {e}")
        errors.append(f"5단계(API비용): {e}")

    # 6단계: 저장
    try:
        step6_save_results(server_status, goldbox_top3, ezadmin, reports, api_costs, errors)
    except Exception as e:
        log.error(f"6단계 실패: {e}")
        errors.append(f"6단계(저장): {e}")

    # 7단계: 에러 알림
    try:
        step7_telegram_alert(server_status, errors)
    except Exception as e:
        log.error(f"7단계 실패: {e}")

    # 8단계: 일일 백업
    try:
        log.info("[8단계] 일일 백업")
        from daily_backup import run_backup
        success, failed = run_backup()
        log.info(f"  백업 완료: 성공 {success}건, 실패 {failed}건")
    except Exception as e:
        log.error(f"8단계 실패: {e}")

    # 9단계: 메타 광고 일일보고서 생성 (옵시디언)
    try:
        log.info("[9단계] 메타 광고 일일보고서 생성")
        from meta_daily_report import run_yesterday
        report_path = run_yesterday()
        log.info(f"  보고서 저장: {report_path}")
    except Exception as e:
        log.error(f"9단계 실패: {e}")
        errors.append(f"9단계(메타보고서): {e}")

    log.info(f"새벽 자동화 완료 (에러 {len(errors)}건)")
    log.info("=" * 50)


if __name__ == "__main__":
    main()
