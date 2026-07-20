#!/usr/bin/env python3
"""쿠팡 광고센터 보고서 '생성' 자동화 (2026-07-16, 대표님 요청: 생성→다운→분석 논스톱의 1단계)

대표님 생성 기준 (스샷 2026-07-16 04:50 확인):
- 기간: 지정일 (기본 = 어제 하루)
- 기간 단위: 일별(daily)
- 캠페인: 전체선택
- 보고서 구조: [일별] 키워드 (반드시 명시 선택; 기본값은 캠페인이라 분석에 사용 불가)

사용:
  python3 coupang_ad_create.py                       # 채움, 어제
  python3 coupang_ad_create.py --account becorelab   # 비코어랩, 어제
  python3 coupang_ad_create.py --from 2026-07-10 --to 2026-07-10
  python3 coupang_ad_create.py --wait                # 생성 완료까지 폴링

주의: 생성만 함. 다운로드는 기존 coupang_ad_download.py (크론 07:00) 또는 --wait 후 별도 실행.
"""
import sys, time, argparse
from datetime import date, timedelta

sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from coupang_ad_config import ACCOUNTS, REPORT_LIST_URL

WING_AUTH_URL = "https://advertising.coupang.com/user/login?_cap_client=WING&returnUrl=%2Fdashboard"
KEYWORD_STRUCTURE_LABEL = "캠페인 > 광고그룹 > 상품 > 키워드"


def _select_keyword_level(page):
    """보고서 구조를 '키워드'로 명시 선택하고 실제 체크 상태까지 검증한다."""
    # 구조 선택지는 캠페인 선택을 확정한 뒤에만 렌더링된다.
    try:
        exact = page.get_by_role("radio", name=KEYWORD_STRUCTURE_LABEL, exact=True)
        exact.wait_for(state="visible", timeout=10000)
        exact.check(force=True)
        if not exact.is_checked():
            raise RuntimeError("키워드 단위 선택이 적용되지 않음")
        print(f"  키워드 단위 선택 ✓ ({KEYWORD_STRUCTURE_LABEL})")
        return
    except Exception:
        pass

    value_matches = []
    label_matches = []
    for radio in page.query_selector_all("input[type=radio]"):
        if not radio.is_visible():
            continue
        value = (radio.get_attribute("value") or "").strip().lower()
        label = radio.evaluate(
            "el => el.closest('label')?.innerText || "
            "el.closest('.ant-radio-wrapper')?.innerText || "
            "el.nextElementSibling?.innerText || ''"
        ).strip()
        candidate = (radio, value, label)
        if value in {"keyword", "keywords"}:
            value_matches.append(candidate)
        elif label.replace(" ", "") == KEYWORD_STRUCTURE_LABEL.replace(" ", ""):
            label_matches.append(candidate)

    candidates = value_matches or label_matches
    if not candidates:
        raise RuntimeError("키워드 단위 라디오를 찾지 못함 — 캠페인 보고서 생성 방지를 위해 중단")

    radio, value, label = candidates[0]
    radio.click(force=True)
    time.sleep(1)
    if not radio.is_checked():
        raise RuntimeError("키워드 단위 선택이 적용되지 않음 — 보고서 생성 중단")
    print(f"  키워드 단위 선택 ✓ (value={value or '-'}, label={label or '-'})")


def _select_clicked_keywords_only(page):
    """기존 일일보고서 표준인 '클릭 발생 키워드만 포함'을 명시 적용한다."""
    label = "클릭이 발생한 키워드만 보고서에 포함"
    checkbox = page.get_by_role("checkbox", name=label, exact=True)
    checkbox.wait_for(state="visible", timeout=10000)
    checkbox.check(force=True)
    if not checkbox.is_checked():
        raise RuntimeError("클릭 발생 키워드만 포함 설정이 적용되지 않음")
    print(f"  {label} ✓")


def _completed_keyword_row_text(page, date_from, date_to):
    """AG-grid 전체 행에서 요청한 기간·구조의 완료 보고서를 찾는다."""
    expected_range = f"{date_from} ~ {date_to}"
    expected_structure = f"[일별] {KEYWORD_STRUCTURE_LABEL}"
    for row in page.query_selector_all('div[role="row"][row-id]'):
        text = row.inner_text().replace("\n", " ")
        if (expected_range in text and expected_structure in text
                and "생성 완료" in text):
            return text
    return ""


def _login(page, acct, max_tries=1):
    for i in range(max_tries):
        page.goto(WING_AUTH_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        # 로그인 방식 선택 화면(윙/서플라이허브/대행사)이 뜨면 첫 번째(윙) 로그인하기 클릭
        try:
            if page.query_selector('text=쿠팡 광고센터 로그인'):
                page.query_selector_all('text=로그인하기')[0].click()
                time.sleep(3)
        except Exception:
            pass
        # 로그인 폼이 있으면 입력
        try:
            page.wait_for_selector('input[name="username"]', timeout=15000)
            page.fill('input[name="username"]', acct["id"])
            page.fill('input[name="password"]', acct["pw"])
            page.click('input[name="login"]')
            time.sleep(5)
        except Exception:
            pass  # 이미 로그인된 세션이면 폼이 없을 수 있음
        # 성공 판정: 광고센터 대시보드/보고서 접근 가능해야 함
        if ("advertising.coupang.com" in page.url and "user/login" not in page.url) \
           or "wing.coupang.com" in page.url or "dashboard" in page.url:
            return
        time.sleep(3)
    raise RuntimeError(f"로그인 실패({max_tries}회) — 최소 30분 쿨다운 필요: {page.url[:80]}")


def create_in_page(page, date_from, date_to, wait_done=True, wait_timeout_sec=600):
    """이미 로그인된 page 객체로 보고서 생성 (다운로드 스크립트 세션 재활용용).
    반환: (성공여부, 메시지). 2026-07-16 폼 요소 실검증 완료 (기간custom/daily/전체선택+확인)."""
    from coupang_ad_config import REPORT_LIST_URL as _URL
    for i in range(3):
        page.goto(_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector("text=보고서 만들기", timeout=45000)
            break
        except Exception:
            if i == 2:
                return False, "보고서 페이지 로드 실패"
            time.sleep(5)
    time.sleep(3)

    def radios():
        return [e for e in page.query_selector_all("input[type=radio]") if e.is_visible()]

    # ① 기간 custom
    custom = [r for r in radios() if not r.get_attribute("value") or r.get_attribute("value") == "custom"]
    custom[0].click(force=True)
    time.sleep(2)
    start = page.query_selector('input[placeholder="시작일"]')
    end = page.query_selector('input[placeholder="종료일"]')
    for inp, val in ((start, date_from), (end, date_to)):
        inp.click(); inp.press("Meta+a"); inp.type(val, delay=30); inp.press("Enter"); time.sleep(1)
    page.keyboard.press("Escape"); time.sleep(1)
    # ② daily
    [r for r in radios() if r.get_attribute("value") == "daily"][0].click(force=True)
    time.sleep(1)
    # ③ 캠페인 전체선택 + 확인
    page.get_by_role("button", name="캠페인을 선택하세요").click(); time.sleep(3)
    all_cb = None
    for e in page.query_selector_all("input[type=checkbox]"):
        if e.is_visible() and "전체선택" in e.evaluate("el => el.closest('label')?.innerText || el.parentElement?.innerText || ''"):
            all_cb = e; break
    if not all_cb:
        return False, "전체선택 체크박스 못 찾음"
    all_cb.click(force=True); time.sleep(1)
    page.get_by_role("button", name="확인").click(); time.sleep(2)
    # ④ 캠페인 확정 뒤 렌더링되는 보고서 구조에서 키워드 선택
    _select_keyword_level(page)
    _select_clicked_keywords_only(page)
    # ⑤ 생성
    make = page.get_by_role("button", name="보고서 만들기")
    if not make.is_enabled():
        page.screenshot(path="/tmp/create_error.png")
        return False, "보고서 만들기 버튼 비활성 (입력 미반영)"
    make.click(); time.sleep(4)
    # ⑥ 완료 폴링
    if wait_done:
        deadline = time.time() + wait_timeout_sec
        while time.time() < deadline:
            page.reload(wait_until="domcontentloaded")
            try:
                page.wait_for_selector("text=보고서 만들기", timeout=30000)
            except Exception:
                time.sleep(10); continue
            time.sleep(3)
            row_text = _completed_keyword_row_text(page, date_from, date_to)
            if row_text:
                return True, f"생성 완료: {row_text[:80]}"
            time.sleep(20)
        return False, "생성 대기 타임아웃 (요청은 됨)"
    return True, "생성 요청 완료"


def create_report(account_key="chaewoom", date_from=None, date_to=None,
                  headless=True, wait_done=False, wait_timeout_sec=600):
    """보고서 생성. 반환: (성공여부, 메시지)"""
    acct = ACCOUNTS[account_key]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    date_from = date_from or yesterday
    date_to = date_to or yesterday
    print(f"[{acct['name']}] 보고서 생성: {date_from} ~ {date_to} (일별/전체캠페인)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, channel="chrome",
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            locale="ko-KR")
        stealth = Stealth()
        page = ctx.new_page()
        stealth.apply_stealth_sync(page)
        try:
            _login(page, acct)
            for i in range(3):
                page.goto(REPORT_LIST_URL, wait_until="domcontentloaded", timeout=60000)
                try:
                    page.wait_for_selector("text=보고서 만들기", timeout=45000)
                    break
                except Exception:
                    if i == 2:
                        raise
                    time.sleep(5)
            time.sleep(3)

            def radios():
                return [e for e in page.query_selector_all("input[type=radio]") if e.is_visible()]

            # ① 기간 설정(custom) → 시작/종료일 입력
            custom = [r for r in radios() if not r.get_attribute("value")]
            if not custom:
                custom = [r for r in radios() if r.get_attribute("value") == "custom"]
            custom[0].click(force=True)
            time.sleep(2)
            start = page.query_selector('input[placeholder="시작일"]')
            end = page.query_selector('input[placeholder="종료일"]')
            for inp, val in ((start, date_from), (end, date_to)):
                inp.click()
                inp.press("Meta+a")
                inp.type(val, delay=30)
                inp.press("Enter")
                time.sleep(1)
            # 달력 팝업 닫힘 보장
            page.keyboard.press("Escape")
            time.sleep(1)
            got = (start.get_attribute("value"), end.get_attribute("value"))
            print(f"  기간 입력됨: {got}")
            if got != (date_from, date_to):
                raise RuntimeError(f"기간 입력 불일치: {got}")

            # ② 일별
            daily = [r for r in radios() if r.get_attribute("value") == "daily"]
            daily[0].click(force=True)
            time.sleep(1)
            print("  일별 선택 ✓")

            # ③ 캠페인 전체선택
            page.get_by_role("button", name="캠페인을 선택하세요").click()
            time.sleep(3)
            all_cb = None
            for e in page.query_selector_all("input[type=checkbox]"):
                if not e.is_visible():
                    continue
                label = e.evaluate("el => el.closest('label')?.innerText || el.parentElement?.innerText || ''")
                if "전체선택" in label:
                    all_cb = e
                    break
            if not all_cb:
                raise RuntimeError("전체선택 체크박스 못 찾음")
            all_cb.click(force=True)
            time.sleep(1)
            # 패널의 [확인] 버튼으로 선택 적용 (Escape는 선택 취소됨 — 2026-07-16 검증)
            page.get_by_role("button", name="확인").click()
            time.sleep(2)
            print("  캠페인 전체선택 + 확인 ✓")

            # ④ 캠페인 확정 뒤 렌더링되는 보고서 구조에서 키워드 선택
            _select_keyword_level(page)
            _select_clicked_keywords_only(page)

            # ⑤ 생성
            before = len(page.query_selector_all("table tr"))
            page.get_by_role("button", name="보고서 만들기").click()
            time.sleep(4)
            page.screenshot(path="/tmp/after_create.png")
            body = page.inner_text("body")
            if "생성" not in body:
                raise RuntimeError("생성 후 상태 확인 실패")
            print("  보고서 만들기 클릭 ✓")

            # ⑥ (옵션) 생성 완료 폴링
            if wait_done:
                deadline = time.time() + wait_timeout_sec
                while time.time() < deadline:
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_selector("text=보고서 만들기", timeout=30000)
                    time.sleep(3)
                    row_text = _completed_keyword_row_text(page, date_from, date_to)
                    if row_text:
                        print(f"  ✅ 생성 완료: {row_text[:100]}")
                        browser.close()
                        return True, "생성 완료"
                    print(f"  ⏳ 대기 중... ({row_text[:60]})")
                    time.sleep(20)
                browser.close()
                return False, "생성 대기 타임아웃 (보고서는 요청됨)"
            browser.close()
            return True, "생성 요청 완료 (완료 대기는 --wait)"
        except Exception as e:
            page.screenshot(path="/tmp/create_error.png")
            browser.close()
            return False, f"실패: {e}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="chaewoom")
    ap.add_argument("--from", dest="date_from", default=None)
    ap.add_argument("--to", dest="date_to", default=None)
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    ok, msg = create_report(args.account, args.date_from, args.date_to,
                            headless=not args.headed, wait_done=args.wait)
    print(("✅ " if ok else "❌ ") + msg)
    sys.exit(0 if ok else 1)
