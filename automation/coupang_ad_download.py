"""쿠팡 광고센터 보고서 자동 다운로드 + JSON 변환

흐름:
1. stealth + Chrome으로 xauth.coupang.com 로그인
2. 광고센터 보고서 페이지 접속
3. 보고서 목록 스캔 → 다운로드
4. 엑셀 → JSON 변환
"""
import os
import sys
import time
import json
import glob
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

sys.path.insert(0, os.path.dirname(__file__))
from coupang_ad_config import ACCOUNTS, AD_CENTER_URL, DOWNLOAD_DIR, DATA_DIR

WING_AUTH_URL = "https://advertising.coupang.com/user/login?_cap_client=WING&returnUrl=%2Fdashboard"
REPORT_PAGE_URL = f"{AD_CENTER_URL}/marketing-reporting/billboard/reports/pa"


def login_and_download_all(account_key="chaewoom", headless=True, max_reports=10):
    """로그인 → 보고서 목록 스캔 → 전체 다운로드"""
    acct = ACCOUNTS[account_key]
    print(f"[{acct['name']}] 쿠팡 광고 보고서 자동 다운로드")
    print(f"  headless={headless}, max_reports={max_reports}")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            locale="ko-KR",
            accept_downloads=True,
        )
        stealth = Stealth()
        page = context.new_page()
        stealth.apply_stealth_sync(page)

        # 1) 로그인
        print("\n[1/3] Wing 로그인...")
        page.goto(WING_AUTH_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        body_text = page.inner_text('body')
        if "Access Denied" in body_text:
            print("  ❌ Akamai Access Denied")
            browser.close()
            return []

        try:
            page.wait_for_selector('input[name="username"]', timeout=30000)
        except Exception:
            print("  ⚠️ 로그인 폼 없음 — 1회 재시도")
            page.reload(wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
            try:
                page.wait_for_selector('input[name="username"]', timeout=30000)
            except Exception:
                print("  ❌ 로그인 폼 없음 (재시도 실패)")
                browser.close()
                return []

        page.fill('input[name="username"]', acct["id"])
        page.fill('input[name="password"]', acct["pw"])
        time.sleep(1)

        login_success = False
        for attempt in range(3):
            if attempt > 0:
                print(f"  🔄 로그인 재시도 ({attempt+1}/3) — 30초 대기...")
                time.sleep(30)
                page.goto(WING_AUTH_URL, wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)
                try:
                    page.wait_for_selector('input[name="username"]', timeout=15000)
                except Exception:
                    continue
                page.fill('input[name="username"]', acct["id"])
                page.fill('input[name="password"]', acct["pw"])
                time.sleep(1)

            try:
                with page.expect_navigation(timeout=30000, wait_until="load"):
                    page.click('input[name="login"]')
                time.sleep(3)
            except Exception:
                time.sleep(3)

            if "xauth" in page.url and "advertising.coupang.com" not in page.url:
                body_text = page.inner_text('body')[:100]
                if "Access Denied" in body_text:
                    print(f"  ⚠️ Akamai 차단 (attempt {attempt+1})")
                else:
                    print(f"  ⚠️ 로그인 실패 (attempt {attempt+1})")
                continue
            else:
                login_success = True
                break

        if not login_success:
            print("  ❌ 로그인 실패 (3회 재시도 후 포기)")
            browser.close()
            return []

        print(f"  ✅ 로그인 성공 → {page.url}")

        # 2) 보고서 페이지
        print(f"\n[2/3] 보고서 페이지...")
        page.goto(REPORT_PAGE_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(10)

        # 보고서 행 스캔
        rows = page.query_selector_all('div[role="row"][row-id]')
        print(f"  보고서 {len(rows)}개 발견")

        reports = []
        for row in rows[:max_reports]:
            row_id = row.get_attribute("row-id")
            text = row.inner_text().strip().replace('\n', ' | ')
            reports.append({"row_id": row_id, "text": text})
            print(f"    [{row_id}] {text[:120]}")

        # 3) 다운로드
        print(f"\n[3/3] 다운로드 시작...")
        dl_buttons = page.query_selector_all('button:has-text("다운로드")')
        downloaded = []

        for i, btn in enumerate(dl_buttons[:max_reports]):
            # 모달이 열려 있으면 닫기
            modal_close = page.query_selector('.ant-modal-wrap .ant-modal-close, .ant-modal-wrap button:has-text("닫기")')
            if modal_close:
                try:
                    modal_close.click()
                    time.sleep(1)
                except Exception:
                    page.keyboard.press("Escape")
                    time.sleep(1)

            try:
                with page.expect_download(timeout=30000) as dl_info:
                    btn.click()
                download = dl_info.value
                filename = download.suggested_filename
                save_path = os.path.join(DOWNLOAD_DIR, filename)
                download.save_as(save_path)
                size = os.path.getsize(save_path)
                print(f"  ✅ [{i+1}/{len(dl_buttons)}] {filename} ({size:,} bytes)")
                downloaded.append(save_path)
                time.sleep(2)
            except Exception as e:
                # 모달 닫기 재시도
                page.keyboard.press("Escape")
                time.sleep(1)
                try:
                    with page.expect_download(timeout=30000) as dl_info:
                        btn.click()
                    download = dl_info.value
                    filename = download.suggested_filename
                    save_path = os.path.join(DOWNLOAD_DIR, filename)
                    download.save_as(save_path)
                    size = os.path.getsize(save_path)
                    print(f"  ✅ [{i+1}/{len(dl_buttons)}] {filename} ({size:,} bytes) (재시도)")
                    downloaded.append(save_path)
                    time.sleep(2)
                except Exception as e2:
                    print(f"  ❌ [{i+1}/{len(dl_buttons)}] 실패: {e2}")

        # 쿠키 저장
        cookies = context.cookies()
        with open(os.path.join(DOWNLOAD_DIR, "cookies.json"), "w") as f:
            json.dump(cookies, f, indent=2)

        browser.close()
        print(f"\n완료! {len(downloaded)}개 다운로드됨")
        return downloaded


def excel_to_json(xlsx_path, output_dir=None):
    """엑셀 보고서 → JSON 변환"""
    try:
        import openpyxl
    except ImportError:
        print("openpyxl 설치 필요: pip3 install openpyxl")
        return None

    if output_dir is None:
        output_dir = DATA_DIR
    os.makedirs(output_dir, exist_ok=True)

    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        print(f"  빈 파일: {xlsx_path}")
        return None

    headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
    data = []
    for row in rows[1:]:
        record = {}
        for j, val in enumerate(row):
            if j < len(headers):
                if isinstance(val, datetime):
                    val = val.strftime("%Y-%m-%d")
                record[headers[j]] = val
        data.append(record)

    basename = os.path.splitext(os.path.basename(xlsx_path))[0]
    json_path = os.path.join(output_dir, f"{basename}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  {os.path.basename(xlsx_path)} → {os.path.basename(json_path)} ({len(data)}행)")
    wb.close()
    return json_path


if __name__ == "__main__":
    headless = "--headed" not in sys.argv
    convert = "--convert" in sys.argv or "--json" in sys.argv
    account = "chaewoom"
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            account = arg
            break

    print(f"=== 쿠팡 광고 보고서 자동화 ===")
    print(f"    계정: {account}, headless: {headless}")
    print(f"    시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    downloaded = login_and_download_all(account, headless=headless)

    if downloaded and convert:
        print(f"\n=== JSON 변환 ===")
        for path in downloaded:
            if path.endswith('.xlsx'):
                excel_to_json(path)

    if not downloaded:
        sys.exit(1)
