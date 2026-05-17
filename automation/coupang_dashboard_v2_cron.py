#!/usr/bin/env python3
"""쿠팡 광고 대시보드 v2 — 일일 자동화 크론

흐름:
1. coupang_ad_download.py 로 최신 보고서 다운로드 + JSON 변환
2. coupang_dashboard_v2.py 로 구글시트 대시보드 업데이트 (내림차순)

사용법:
  python3 coupang_dashboard_v2_cron.py                  # 전체 (다운로드+업데이트)
  python3 coupang_dashboard_v2_cron.py --skip-download   # 업데이트만
  python3 coupang_dashboard_v2_cron.py becorelab          # 비코어랩만
  python3 coupang_dashboard_v2_cron.py chaewoom            # 채움컴퍼니만
"""
import os
import sys
import subprocess
import logging
import glob
from datetime import datetime

# ── 설정 ──────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_SCRIPT = os.path.join(SCRIPT_DIR, "coupang_ad_download.py")
DASHBOARD_V2_SCRIPT = os.path.join(SCRIPT_DIR, "coupang_dashboard_v2.py")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
DOWNLOAD_DIR = "/Users/macmini_ky/ClaudeAITeam/marketing/coupang_data/downloads"
DATA_DIR = "/Users/macmini_ky/ClaudeAITeam/marketing/coupang_data"

ACCOUNT_KEYS = {
    "chaewoom": "chaewoom",
    "becorelab": "becorelab",
}


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOG_DIR, f"coupang_dashboard_v2_{today}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file


def run_download(account_key, headed=False):
    cmd = [sys.executable, DOWNLOAD_SCRIPT, account_key, "--convert"]
    if headed:
        cmd.append("--headed")

    logging.info(f"[다운로드] {account_key} 시작")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=420, cwd=SCRIPT_DIR,
        )
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                logging.info(f"  {line}")
        if result.returncode != 0:
            logging.warning(f"[다운로드] {account_key} 종료코드: {result.returncode}")
            if result.stderr.strip():
                for line in result.stderr.strip().split("\n")[:5]:
                    logging.warning(f"  STDERR: {line}")
            return False
        logging.info(f"[다운로드] {account_key} 완료")
        return True
    except subprocess.TimeoutExpired:
        logging.error(f"[다운로드] {account_key} 타임아웃")
        return False
    except Exception as e:
        logging.error(f"[다운로드] {account_key} 오류: {e}")
        return False


def run_dashboard_v2(account_keys=None):
    cmd = [sys.executable, DASHBOARD_V2_SCRIPT]
    if account_keys:
        for key in account_keys:
            cmd.append(key)

    logging.info(f"[대시보드 v2] 업데이트 시작")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180, cwd=SCRIPT_DIR,
        )
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                logging.info(f"  {line}")
        if result.returncode != 0:
            logging.warning(f"[대시보드 v2] 종료코드: {result.returncode}")
            if result.stderr.strip():
                for line in result.stderr.strip().split("\n")[:5]:
                    logging.warning(f"  STDERR: {line}")
            return False
        logging.info("[대시보드 v2] 업데이트 완료")
        return True
    except subprocess.TimeoutExpired:
        logging.error("[대시보드 v2] 타임아웃")
        return False
    except Exception as e:
        logging.error(f"[대시보드 v2] 오류: {e}")
        return False


def convert_missing_xlsx():
    """downloads/ 폴더의 XLSX 중 DATA_DIR에 JSON이 없는 파일을 변환.
    다운로드 실패 시에도 수동 다운로드 XLSX로 대시보드 업데이트 가능하게 함.
    """
    xlsx_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*_pa_daily_keyword_*.xlsx"))
    converted = 0

    for xlsx_path in xlsx_files:
        basename = os.path.splitext(os.path.basename(xlsx_path))[0]
        json_path = os.path.join(DATA_DIR, f"{basename}.json")

        if not os.path.exists(json_path):
            try:
                sys.path.insert(0, SCRIPT_DIR)
                from coupang_ad_download import excel_to_json
                result = excel_to_json(xlsx_path, DATA_DIR)
                if result:
                    logging.info(f"  ✅ 변환: {os.path.basename(xlsx_path)} → JSON")
                    converted += 1
            except Exception as e:
                logging.warning(f"  ❌ 변환 실패: {os.path.basename(xlsx_path)} — {e}")

    if converted:
        logging.info(f"  총 {converted}개 XLSX → JSON 변환 완료")
    else:
        logging.info("  변환 대상 없음 (모든 XLSX에 대응 JSON 존재)")


def main():
    log_file = setup_logging()

    skip_download = "--skip-download" in sys.argv
    headed = "--headed" in sys.argv

    target_accounts = []
    for arg in sys.argv[1:]:
        if arg in ACCOUNT_KEYS:
            target_accounts.append(arg)
    if not target_accounts:
        target_accounts = list(ACCOUNT_KEYS.keys())

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"{'='*60}")
    logging.info(f"쿠팡 광고 대시보드 v2 — 일일 자동화")
    logging.info(f"  시간: {now}")
    logging.info(f"  계정: {', '.join(target_accounts)}")
    logging.info(f"  다운로드: {'건너뜀' if skip_download else '실행'}")
    logging.info(f"  로그: {log_file}")
    logging.info(f"{'='*60}")

    # Step 1: 보고서 다운로드
    if not skip_download:
        logging.info("\n" + "=" * 30 + " STEP 1: 다운로드 " + "=" * 30)
        for acct_key in target_accounts:
            run_download(acct_key, headed=headed)

    # Step 1.5: downloads/ 의 XLSX 중 JSON 없는 것 자동 변환
    logging.info("\n" + "=" * 30 + " STEP 1.5: XLSX→JSON 변환 " + "=" * 30)
    convert_missing_xlsx()

    # Step 2: 대시보드 v2 업데이트
    logging.info("\n" + "=" * 30 + " STEP 2: 대시보드 v2 " + "=" * 30)
    dashboard_success = run_dashboard_v2(target_accounts)

    # 결과
    logging.info(f"\n{'='*60}")
    logging.info(f"대시보드 v2: {'✅ 성공' if dashboard_success else '❌ 실패'}")
    logging.info(f"{'='*60}")

    if not dashboard_success:
        sys.exit(1)


if __name__ == "__main__":
    main()
