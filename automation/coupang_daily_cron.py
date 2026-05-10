#!/usr/bin/env python3
"""쿠팡 광고 일일 자동화 크론 래퍼

흐름:
1. coupang_ad_download.py 로 최신 보고서 다운로드 + JSON 변환
2. coupang_dashboard_update.py 로 구글시트 대시보드 업데이트
3. 전체 과정 로그 기록

사용법:
  python3 coupang_daily_cron.py                 # 양쪽 계정 전부
  python3 coupang_daily_cron.py chaewoom        # 채움컴퍼니만
  python3 coupang_daily_cron.py becorelab       # 비코어랩만
  python3 coupang_daily_cron.py --skip-download # 다운로드 생략, 대시보드만
  python3 coupang_daily_cron.py --headed        # 브라우저 UI 표시 (디버그용)
"""
import os
import sys
import subprocess
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

# ── 설정 ──────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_SCRIPT = os.path.join(SCRIPT_DIR, "coupang_ad_download.py")
DASHBOARD_SCRIPT = os.path.join(SCRIPT_DIR, "coupang_dashboard_update.py")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

# 계정 키 → 다운로드 스크립트 키 매핑
ACCOUNT_KEYS = {
    "chaewoom": "chaewoom",
    "becorelab": "becorelab",
}


def setup_logging():
    """날짜별 로그 파일 설정"""
    os.makedirs(LOG_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOG_DIR, f"coupang_daily_{today}.log")

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
    """coupang_ad_download.py 실행"""
    cmd = [sys.executable, DOWNLOAD_SCRIPT, account_key, "--convert"]
    if headed:
        cmd.append("--headed")

    logging.info(f"[다운로드] {account_key} 시작: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5분 타임아웃
            cwd=SCRIPT_DIR,
        )

        for line in result.stdout.strip().split("\n"):
            if line.strip():
                logging.info(f"  {line}")

        if result.returncode != 0:
            logging.warning(f"[다운로드] {account_key} 종료코드: {result.returncode}")
            if result.stderr.strip():
                for line in result.stderr.strip().split("\n"):
                    logging.warning(f"  STDERR: {line}")
            return False

        logging.info(f"[다운로드] {account_key} 완료")
        return True

    except subprocess.TimeoutExpired:
        logging.error(f"[다운로드] {account_key} 타임아웃 (5분 초과)")
        return False
    except FileNotFoundError:
        logging.error(f"[다운로드] 스크립트 없음: {DOWNLOAD_SCRIPT}")
        return False
    except Exception as e:
        logging.error(f"[다운로드] {account_key} 오류: {e}")
        return False


def run_dashboard_update(account_keys=None):
    """coupang_dashboard_update.py 실행"""
    cmd = [sys.executable, DASHBOARD_SCRIPT]
    if account_keys:
        for key in account_keys:
            cmd.append(key)

    logging.info(f"[대시보드] 업데이트 시작: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2분 타임아웃
            cwd=SCRIPT_DIR,
        )

        for line in result.stdout.strip().split("\n"):
            if line.strip():
                logging.info(f"  {line}")

        if result.returncode != 0:
            logging.warning(f"[대시보드] 종료코드: {result.returncode}")
            if result.stderr.strip():
                for line in result.stderr.strip().split("\n"):
                    logging.warning(f"  STDERR: {line}")
            return False

        logging.info("[대시보드] 업데이트 완료")
        return True

    except subprocess.TimeoutExpired:
        logging.error("[대시보드] 타임아웃 (2분 초과)")
        return False
    except FileNotFoundError:
        logging.error(f"[대시보드] 스크립트 없음: {DASHBOARD_SCRIPT}")
        return False
    except Exception as e:
        logging.error(f"[대시보드] 오류: {e}")
        return False


def main():
    log_file = setup_logging()

    skip_download = "--skip-download" in sys.argv
    headed = "--headed" in sys.argv

    # 계정 필터
    target_accounts = []
    for arg in sys.argv[1:]:
        if arg in ACCOUNT_KEYS:
            target_accounts.append(arg)

    if not target_accounts:
        target_accounts = list(ACCOUNT_KEYS.keys())

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"{'='*60}")
    logging.info(f"쿠팡 광고 일일 자동화 시작")
    logging.info(f"  시간: {now}")
    logging.info(f"  계정: {', '.join(target_accounts)}")
    logging.info(f"  다운로드: {'건너뜀' if skip_download else '실행'}")
    logging.info(f"  로그: {log_file}")
    logging.info(f"{'='*60}")

    results = {"download": {}, "dashboard": False}

    # Step 1: 보고서 다운로드
    if not skip_download:
        logging.info("")
        logging.info("=" * 40 + " STEP 1: 다운로드 " + "=" * 40)
        for acct_key in target_accounts:
            success = run_download(acct_key, headed=headed)
            results["download"][acct_key] = success
    else:
        logging.info("\n[다운로드] --skip-download 옵션 — 건너뜁니다")

    # Step 2: 대시보드 업데이트
    logging.info("")
    logging.info("=" * 40 + " STEP 2: 대시보드 " + "=" * 40)
    dashboard_success = run_dashboard_update(target_accounts)
    results["dashboard"] = dashboard_success

    # 결과 요약
    logging.info("")
    logging.info("=" * 60)
    logging.info("결과 요약:")
    if not skip_download:
        for acct, ok in results["download"].items():
            status = "✅ 성공" if ok else "❌ 실패"
            logging.info(f"  다운로드 [{acct}]: {status}")
    logging.info(f"  대시보드: {'✅ 성공' if results['dashboard'] else '❌ 실패'}")
    logging.info(f"{'='*60}")

    # 실패 시 비정상 종료
    all_ok = results["dashboard"]
    if not skip_download:
        all_ok = all_ok and all(results["download"].values())

    if not all_ok:
        logging.warning("일부 작업이 실패했습니다")
        sys.exit(1)


if __name__ == "__main__":
    main()
