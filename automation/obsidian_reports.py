"""하치 옵시디언 일일 보고서 누적 스크립트
- macOS launchd에서 매일 05:50에 실행 (morning_collect 03:50 이후)
- 매출: POST /api/daily-report-obsidian → 서버가 Claude 스타일 HTML로 저장
- 재고: POST /api/inventory-report-obsidian → 서버가 Claude 스타일 HTML로 저장
- 실패 시 두리 봇으로 에러 알림
"""
import os
import sys
from datetime import datetime

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    DATA_DIR,
    OBSIDIAN_SALES_DIR,
    OBSIDIAN_STOCK_DIR,
    OBSIDIAN_VAULT,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from dashboard_updater import update_dashboard

BASE_LOGISTICS = "http://localhost:8082"
REPORT_LOG = os.path.join(DATA_DIR, "obsidian_reports.log")

AREAS_DIR = os.path.join(OBSIDIAN_VAULT, "01. Becorelab AI Agent Team", "2️⃣ Areas")
SALES_DASH = os.path.join(AREAS_DIR, "📊 Operations", "📊 Sales Report", "📊 Sales Report.md")
STOCK_DASH = os.path.join(AREAS_DIR, "📊 Operations", "📦 Stock & Order", "📦 Stock & Order.md")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts} {msg}"
    print(line)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPORT_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def notify_error(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"⚠️ 옵시디언 보고서 오류\n{msg}"},
            timeout=10,
        )
    except Exception:
        pass


def call_endpoint(path, label):
    try:
        r = requests.post(f"{BASE_LOGISTICS}{path}", timeout=60)
        if r.status_code == 200:
            data = r.json()
            log(f"{label} 저장: {data.get('file', '?')}")
            return True
        log(f"{label} 실패: {r.status_code} {r.text[:200]}")
        notify_error(f"{label} 보고서 {r.status_code}: {r.text[:120]}")
        return False
    except Exception as e:
        log(f"{label} 오류: {e}")
        notify_error(f"{label} 보고서 예외: {e}")
        return False


def refresh_dashboard(dash_path, reports_folders, label):
    try:
        updated, last_date, count = update_dashboard(
            dash_path, reports_folders, limit=7, status_label="정상 운영 중"
        )
        if updated:
            log(f"{label} 대시보드 갱신: 최근 {count}건, 마지막 {last_date or '없음'}")
        else:
            log(f"{label} 대시보드 마커 없음 — 스킵")
    except Exception as e:
        log(f"{label} 대시보드 갱신 오류: {e}")


def main():
    log("=" * 40)
    log(f"옵시디언 보고서 시작 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    sales_ok = call_endpoint("/api/daily-report-obsidian", "매출")
    inv_ok = call_endpoint("/api/inventory-report-obsidian", "재고")
    refresh_dashboard(SALES_DASH, OBSIDIAN_SALES_DIR, "매출")
    refresh_dashboard(STOCK_DASH, OBSIDIAN_STOCK_DIR, "재고")
    log(f"완료 — 매출 {'OK' if sales_ok else 'FAIL'} / 재고 {'OK' if inv_ok else 'FAIL'}")
    log("=" * 40)


if __name__ == "__main__":
    main()
