"""
쿠팡 서플라이허브 입고상세내역 스크레이퍼 (그로스급 세션재활용, 2026-06-11)
- 9222 상주 헤드리스 CDP 크롬에 connect_over_cdp → 로그인 0회, Akamai 회피
- 세션 만료 시 백업쿠키(supplyhub_session_cookies.json) 주입 → 복원
- 백업쿠키도 만료면: automation/supplyhub_relogin.py 실행 → 대표님 headful 1회 로그인
- 수집 성공 시 쿠키 재백업(세션 갱신분 저장)
※ curl_cffi 로그인(supplyhub_login)은 Akamai 403으로 은퇴 — 재시도 금지(달굼+계정잠김 위험)
"""

import json
import logging
import os
import re
import time
from datetime import date, timedelta, datetime
from html import unescape

log = logging.getLogger("supplyhub")

SUPPLYHUB_ID = os.environ.get("SUPPLYHUB_ID", "")
SUPPLYHUB_PW = os.environ.get("SUPPLYHUB_PW", "")

try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'erp'))
    from config import SUPPLYHUB_ID, SUPPLYHUB_PW
except ImportError:
    pass

BASE_URL = "https://supplier.coupang.com"
DETAIL_URL = f"{BASE_URL}/scm/receive/detail"
CDP_URL = "http://127.0.0.1:9223"  # 서플라이허브 전용 크롬. 9222는 그로스/윙(채움 계정)과 공유 → SSO 계정 충돌로 becorelab 세션이 깨짐. 전용 격리로 세션 보존.
COOKIE_BACKUP = "/Users/macmini_ky/ClaudeAITeam/automation/supplyhub_session_cookies.json"
# coupang 도메인 쿠키 주입하되, 상주 크롬의 Akamai 신뢰 쿠키(_abck/bm_* 등)는 보호(미주입)
AKAMAI_PREFIXES = ("_abck", "bm_", "ak_bmsc")


def _clean_cookies(raw):
    out = []
    for c in raw:
        if "coupang" not in (c.get("domain") or ""):
            continue
        if any((c.get("name") or "").startswith(pfx) for pfx in AKAMAI_PREFIXES):
            continue
        d = {k: c[k] for k in ("name", "value", "domain", "path") if k in c}
        if c.get("expires", -1) > 0:
            d["expires"] = c["expires"]
        d["httpOnly"] = c.get("httpOnly", False)
        d["secure"] = c.get("secure", False)
        ss = c.get("sameSite", "Lax")
        d["sameSite"] = ss if ss in ("Strict", "Lax", "None") else "Lax"
        out.append(d)
    return out


def _session_ok(page):
    if "xauth" in page.url:
        return False
    try:
        return "Access Denied" not in page.inner_text("body")
    except Exception:
        return False


def supplyhub_login():
    """curl_cffi로 서플라이허브 로그인, 세션 쿠키 반환"""
    from curl_cffi import requests as cf_requests

    session = cf_requests.Session(impersonate="chrome131")

    resp0 = session.get(BASE_URL, allow_redirects=False, timeout=30)
    redirect_url = resp0.headers.get("Location", "")

    if redirect_url:
        resp1 = session.get(redirect_url, allow_redirects=True, timeout=30)
    else:
        resp1 = session.get(BASE_URL, allow_redirects=True, timeout=30)

    login_html = resp1.text
    login_url = resp1.url

    kc_match = re.search(r'"loginAction"\s*:\s*"([^"]+)"', login_html)
    if not kc_match:
        log.error("서플라이허브 loginAction 못 찾음")
        return None

    action_url = unescape(kc_match.group(1))

    resp2 = session.post(action_url, data={
        "username": SUPPLYHUB_ID,
        "password": SUPPLYHUB_PW,
        "credentialId": "",
    }, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://xauth.coupang.com",
        "Referer": login_url,
    }, allow_redirects=False, timeout=30)

    while resp2.status_code in (301, 302, 303, 307):
        redir = resp2.headers.get("Location", "")
        if not redir:
            break
        if redir.startswith("/"):
            base = re.match(r'(https?://[^/]+)', resp2.url or action_url)
            if base:
                redir = base.group(1) + redir
        resp2 = session.get(redir, allow_redirects=False, timeout=30)

    if resp2.status_code == 200:
        cookies = []
        for cookie in session.cookies.jar:
            c = {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain or ".coupang.com",
                "path": cookie.path or "/",
            }
            if cookie.secure:
                c["secure"] = True
            cookies.append(c)
        log.info(f"서플라이허브 로그인 성공, 쿠키 {len(cookies)}개")
        return cookies

    log.error(f"서플라이허브 로그인 실패: {resp2.status_code}")
    return None


def scrape_supplyhub(target_date=None, date_end=None, progress=None):
    """서플라이허브 입고상세내역 스크래핑

    Args:
        target_date: 시작일 (YYYY-MM-DD), 기본 어제
        date_end: 종료일 (YYYY-MM-DD), 기본 target_date와 같음
        progress: 진행 콜백

    Returns:
        dict: {date, total_amount, total_supply, total_vat, count, items: [...]}
    """
    from playwright.sync_api import sync_playwright

    if target_date is None:
        target_date = (date.today() - timedelta(days=1)).isoformat()
    if date_end is None:
        date_end = target_date

    if progress:
        progress("supplyhub_connect")

    log.info(f"서플라이허브 입고상세내역 수집: {target_date} ~ {date_end}")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL, timeout=30000)
        context = browser.contexts[0]

        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            url = f"{DETAIL_URL}?page=1&startDate={target_date}&endDate={date_end}"
            log.info(f"  입고상세내역 페이지 이동: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)

            # 세션 만료 → 백업쿠키 주입 후 1회 재시도 (그로스 패턴)
            if not _session_ok(page):
                log.info("  세션 없음/만료 → 백업쿠키 주입 재시도")
                page.close()
                if os.path.exists(COOKIE_BACKUP):
                    try:
                        with open(COOKIE_BACKUP, encoding="utf-8") as f:
                            context.add_cookies(_clean_cookies(json.load(f)))
                    except Exception as e:
                        log.error(f"  백업쿠키 주입 실패: {e}")
                page = context.new_page()
                page.set_default_timeout(60000)
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)

            if not _session_ok(page):
                log.error("서플라이허브 세션 만료 — 백업쿠키도 만료. "
                          "automation/supplyhub_relogin.py 로 대표님 재로그인 필요")
                page.close()
                return None

            if progress:
                progress("supplyhub_scraping")

            body = page.inner_text("body")
            summary_text = body
            server_total = _parse_server_summary(summary_text)
            log.info(f"  서버 합계: 단가={server_total.get('total_unit_price', 0):,}, "
                     f"공급가={server_total.get('total_supply_price', 0):,}, "
                     f"건수={server_total.get('total_count', 0)}")

            all_data = []
            max_pages = 50
            page_size = 10

            for pg in range(1, max_pages + 1):
                if pg > 1:
                    pg_url = f"{DETAIL_URL}?page={pg}&startDate={target_date}&endDate={date_end}"
                    page.goto(pg_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(3)

                rows = _extract_table_rows(page)
                if not rows:
                    log.info(f"  페이지 {pg}: 데이터 없음, 수집 종료")
                    break

                all_data.extend(rows)
                log.info(f"  페이지 {pg}: {len(rows)}건 (누적 {len(all_data)}건)")

                if len(rows) < page_size:
                    break

                if progress:
                    progress(f"supplyhub_page_{pg}")

            # 수집 성공 → 쿠키 재백업 (세션 갱신분 저장, 그로스 패턴)
            try:
                with open(COOKIE_BACKUP, "w", encoding="utf-8") as f:
                    json.dump(context.cookies(), f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            page.close()  # 탭만 닫기 — 상주 크롬 유지 (browser.close() 금지)

            total_unit = 0
            total_supply = 0
            total_vat = 0

            for row in all_data:
                total_unit += _parse_num(row.get("총단가", "0"))
                total_supply += _parse_num(row.get("총공급가액", "0"))
                total_vat += _parse_num(row.get("총세액", "0"))

            result = {
                "date": target_date,
                "date_end": date_end,
                "total_unit_price": total_unit,
                "total_supply_price": total_supply,
                "total_vat": total_vat,
                "count": len(all_data),
                "server_summary": server_total,
                "items": all_data,
            }

            log.info(f"서플라이허브 수집 완료: {len(all_data)}건, "
                     f"단가합계={total_unit:,}, 공급가합계={total_supply:,}")

            if progress:
                progress("supplyhub_done")

            return result

        except Exception as e:
            log.error(f"서플라이허브 스크래핑 오류: {e}")
            try:
                page.close()
            except Exception:
                pass
            return None


def _parse_num(v):
    """숫자 문자열 → int"""
    if not v:
        return 0
    try:
        return int(str(v).replace(",", "").replace("원", "").strip())
    except (ValueError, TypeError):
        return 0


def _parse_server_summary(text):
    """페이지 상단 합계 파싱"""
    result = {}
    patterns = [
        ("total_unit_price", r"총\s*단가\s*합계\s*[\n\r]*\s*([\d,]+)"),
        ("total_supply_price", r"총\s*공급가\s*합계\s*[\n\r]*\s*([\d,]+)"),
        ("total_vat", r"총\s*세액\s*합계\s*[\n\r]*\s*([\d,]+)"),
        ("total_count", r"검색\s*건수\s*[\n\r]*\s*([\d,]+)"),
    ]
    for key, pattern in patterns:
        m = re.search(pattern, text)
        if m:
            result[key] = _parse_num(m.group(1))
    return result


def _extract_table_rows(page):
    """테이블에서 데이터 행 추출

    페이지에 테이블이 여러 개(합계/달력 위젯 포함) — '구분' th를 가진 게 데이터 테이블.
    헤더는 공백 제거 정규화 ('총 공급가액' → '총공급가액').
    """
    headers = [
        "구분", "번호", "SKU번호", "SKU명", "입고/반출일자",
        "물류센터", "세금타입", "수량", "단가", "공급가액",
        "세액", "총단가", "총공급가액", "총세액", "계산서번호", "지급일"
    ]

    rows = []
    table = None
    for t in page.query_selector_all("table"):
        ths_txt = [th.inner_text().strip() for th in t.query_selector_all("th")]
        if "구분" in ths_txt:
            table = t
            break
    if not table:
        table = page.query_selector("table")
    if not table:
        return rows

    ths = table.query_selector_all("th")
    if ths:
        headers = [th.inner_text().strip().replace(" ", "")
                   for th in ths if th.inner_text().strip()]

    trs = table.query_selector_all("tbody tr")
    for tr in trs:
        cells = tr.query_selector_all("td")
        if not cells:
            continue
        values = [c.inner_text().strip() for c in cells]
        if not any(values):
            continue
        row_dict = {}
        for i, v in enumerate(values):
            key = headers[i] if i < len(headers) else f"col_{i}"
            row_dict[key] = v
        rows.append(row_dict)

    return rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = scrape_supplyhub()
    if result:
        print(f"\n수집 완료: {result['count']}건")
        print(f"단가 합계: {result['total_unit_price']:,}원")
        print(f"공급가 합계: {result['total_supply_price']:,}원")
    else:
        print("\n수집 실패")
