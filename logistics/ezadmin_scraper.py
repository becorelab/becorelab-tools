#!/usr/bin/env python3
"""
이지어드민 데이터 자동 수집 스크래퍼
- 로그인 + 보안코드 자동인식 + 재고현황(I100) + 재고수불부(I500) 출고량 수집
"""
import logging
import re
import time
import os
import base64
import tempfile
import io
import platform
import requests
from datetime import date, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

try:
    from config import EZADMIN as _LEGACY_EZADMIN
except (ImportError, ModuleNotFoundError):
    _LEGACY_EZADMIN = {}


def _load_local_env() -> None:
    """Load logistics/.env without adding a python-dotenv dependency."""
    env_path = Path(__file__).resolve().with_name(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()
EZADMIN = {
    "url": os.environ.get("EZADMIN_URL", _LEGACY_EZADMIN.get("url", "")),
    "domain": os.environ.get("EZADMIN_DOMAIN", _LEGACY_EZADMIN.get("domain", "")),
    "id": os.environ.get("EZADMIN_ID", _LEGACY_EZADMIN.get("id", "")),
    "pw": os.environ.get("EZADMIN_PASSWORD", _LEGACY_EZADMIN.get("pw", "")),
}

log = logging.getLogger(__name__)

BASE = "https://ka04.ezadmin.co.kr"


def get_browser(p, headless=False):
    if platform.system() == "Windows":
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    else:
        user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    browser = p.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent=user_agent,
        viewport={"width": 1440, "height": 900},
    )
    page = context.new_page()
    page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, context, page


def ezadmin_login(page):
    """로그인 + 보안코드 대기 (www.ezadmin.co.kr 메인 로그인)"""
    missing = [key for key, value in EZADMIN.items() if not value]
    if missing:
        raise RuntimeError(
            "이지어드민 로그인 설정이 없습니다: " + ", ".join(missing)
            + ". logistics/.env 또는 Windows 환경변수를 설정하세요."
        )
    log.info("이지어드민 로그인 중...")
    page.goto(EZADMIN["url"], timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    # 로그인 팝업 표시
    page.evaluate("document.getElementById('login-popup').style.display = 'block'")
    page.wait_for_timeout(1000)

    # Playwright fill()로 입력 (jQuery .val()이 인식하도록)
    page.fill("#login-domain", EZADMIN["domain"])
    page.fill("#login-id", EZADMIN["id"])
    page.fill("#login-pwd", EZADMIN["pw"])

    # login_check → do_login (RSA 암호화 후 submit)
    page.evaluate("login_check(null)")
    page.wait_for_timeout(8000)
    log.info(f"로그인 전송 완료 — 현재 URL: {page.url}")

    # ── 작업서버 자동 추출 (2026-07-22, ACG 이전 대응) ──
    # 이지어드민은 도메인(업체)마다 물리서버가 다름: bypl=ka04, ACG(annexcombine)=ga69.
    # BASE를 하드코딩하면 서버 이전 시 "mysqli 연결 불가"로 전 데이터 0건이 됨(7/15~ 매출 ₩0 원인).
    # 로그인 후 실제 origin으로 BASE를 갱신 → 서버가 또 바뀌어도 자동 대응.
    global BASE
    try:
        origin = page.evaluate("() => location.origin")
        if origin and origin.startswith("https://") and "ezadmin.co.kr" in origin:
            if origin != BASE:
                log.info(f"작업서버 자동갱신: {BASE} → {origin}")
            BASE = origin
    except Exception as e:
        log.warning(f"작업서버 origin 추출 실패, BASE 유지({BASE}): {e}")

    log.info("보안코드 대기...")
    return True


def _find_anthropic_key():
    return os.environ.get("ANTHROPIC_API_KEY", "")


def _read_captcha_with_openai(screenshot_path, max_retries=2):
    """Read the captcha with OpenAI Vision when an API key is configured."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        img_b64 = base64.standard_b64encode(Path(screenshot_path).read_bytes()).decode()
    except Exception as e:
        log.error(f"캡차 이미지 읽기 실패: {e}")
        return None

    body = {
        "model": os.environ.get("OPENAI_VISION_MODEL", "gpt-5.6"),
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "이미지의 보안코드 숫자 4자리만 출력하세요."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                },
            ],
        }],
        "max_completion_tokens": 20,
    }
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
            if response.status_code != 200:
                log.error(f"OpenAI Vision API {response.status_code} (시도 {attempt + 1})")
                continue
            payload = response.json()
            output_text = payload["choices"][0]["message"]["content"]
            digits = "".join(char for char in output_text if char.isdigit())
            if len(digits) >= 4:
                return digits[:4]
        except Exception as e:
            log.error(f"OpenAI Vision 호출 실패 (시도 {attempt + 1}): {e}")
    return None


def _read_captcha_with_vision(screenshot_path, max_retries=2):
    """Use OpenAI first, then legacy Anthropic; return None for manual entry."""
    openai_code = _read_captcha_with_openai(screenshot_path, max_retries=max_retries)
    if openai_code:
        return openai_code
    import base64
    api_key = _find_anthropic_key()
    if not api_key:
        log.info("Vision API 키 없음 — 브라우저 수동 보안코드 입력으로 전환")
        return None

    try:
        with open(screenshot_path, "rb") as f:
            img_b64 = base64.standard_b64encode(f.read()).decode()
    except Exception as e:
        log.error(f"캡차 이미지 읽기 실패: {e}")
        return None

    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 10,
        "messages": [
            {"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": "이 이미지의 보안코드 숫자 4자리를 읽어라. 설명 없이 숫자 4개만."},
            ]},
            {"role": "assistant", "content": "보안코드:"},  # prefill — 설명 못 붙이게 강제 (끝 공백 금지)
        ],
    }
    for attempt in range(max_retries):
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json=body, timeout=30)
            if r.status_code != 200:
                log.error(f"Claude Vision API {r.status_code}: {r.text[:120]} (시도 {attempt+1})")
                continue
            code = r.json()["content"][0]["text"].strip()
            digits = ''.join(c for c in code if c.isdigit())
            if len(digits) >= 4:
                return digits[:4]
            log.warning(f"보안코드 인식 결과 부족: '{code}' (시도 {attempt+1})")
        except Exception as e:
            log.error(f"Claude Vision 호출 실패 (시도 {attempt+1}): {e}")
    return None


def _enter_captcha(page, code):
    """보안코드 입력 + 확인 버튼 클릭"""
    result = page.evaluate("""
        ((code) => {
            const blocks = document.querySelectorAll('.blockUI.blockMsg');
            for (const b of blocks) {
                if (b.offsetWidth <= 0 || b.offsetHeight <= 0) continue;
                if (b.querySelector('#wrap')) continue;
                // input 필드 찾기
                const inputs = b.querySelectorAll('input');
                for (const inp of inputs) {
                    if (inp.type === 'hidden') continue;
                    inp.value = code;
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                }
                // 확인 버튼 클릭
                const btns = b.querySelectorAll('button, input[type="submit"], input[type="button"], a');
                for (const btn of btns) {
                    const txt = btn.textContent || btn.value || '';
                    if (txt.includes('확인') || txt.includes('인증') || txt.includes('전송')) {
                        btn.click();
                        return 'clicked: ' + txt;
                    }
                }
                // 버튼 못 찾으면 첫 번째 버튼 클릭
                if (btns.length > 0) {
                    btns[0].click();
                    return 'clicked first button';
                }
                return 'no button found';
            }
            return 'no captcha block';
        })
    """, code)
    log.info(f"보안코드 입력 결과: {result}")
    return result


def wait_for_captcha(page, progress=None, timeout_sec=120):
    """보안코드 자동 인식 — 없으면 바로 통과, 있으면 Vision AI로 읽고 입력"""
    if progress:
        progress("captcha_wait")

    # 보안코드 팝업 확인 (5초 대기)
    has_captcha = False
    for i in range(5):
        has_captcha = page.evaluate(
            """
            (() => {
                const blocks = document.querySelectorAll('.blockUI.blockMsg');
                for (const b of blocks) {
                    if (b.offsetWidth <= 0 || b.offsetHeight <= 0) continue;
                    if (b.querySelector('#wrap')) continue;
                    // 진짜 캡차 판별: '보안코드' 텍스트 + 입력필드 존재 (우체국 광고 팝업 오탐 방지 2026-07-16)
                    const t = b.innerText || '';
                    const hasInput = b.querySelector('input:not([type=hidden])');
                    if ((t.includes('보안코드') || t.includes('인증')) && hasInput) return true;
                }
                return false;
            })()
            """
        )
        if has_captcha:
            break
        time.sleep(1)

    if not has_captcha:
        log.info("보안코드 없음 — 이미 인증됨, 바로 진행")
        return True

    # 보안코드 자동 인식 시도 (최대 3회)
    log.info("보안코드 발견! AI 자동 인식 시도...")
    if progress:
        progress("captcha_input")

    for attempt in range(3):
        # 스크린샷 촬영 — 캡차 블록 요소만 크롭 (전체화면이면 숫자가 작아 인식률↓)
        screenshot_path = os.path.join(tempfile.gettempdir(), f"captcha_{attempt}.png")
        shot = False
        try:
            handle = page.evaluate_handle(
                """
                (() => {
                    const blocks = document.querySelectorAll('.blockUI.blockMsg');
                    for (const b of blocks) {
                        if (b.offsetWidth > 0 && b.offsetHeight > 0 && !b.querySelector('#wrap'))
                            return b;
                    }
                    return null;
                })()
                """
            )
            el = handle.as_element()
            if el:
                el.screenshot(path=screenshot_path)
                shot = True
        except Exception as e:
            log.warning(f"캡차 크롭 실패, 전체화면으로 폴백: {e}")
        if not shot:
            page.screenshot(path=screenshot_path)
        log.info(f"스크린샷 촬영 완료: {screenshot_path} (크롭={shot})")

        # 설정된 Vision provider로 읽기 (없으면 이후 수동 입력으로 폴백)
        code = _read_captcha_with_vision(screenshot_path)
        if not code:
            log.warning(f"보안코드 인식 실패 (시도 {attempt+1}/3)")
            time.sleep(2)
            continue

        log.info(f"인식된 보안코드: {code} (시도 {attempt+1}/3)")

        # 보안코드 입력
        _enter_captcha(page, code)
        page.wait_for_timeout(5000)

        # 통과 확인
        still_blocked = page.evaluate(
            """
            (() => {
                const blocks = document.querySelectorAll('.blockUI.blockMsg');
                for (const b of blocks) {
                    if (b.offsetWidth > 0 && b.offsetHeight > 0
                        && !b.querySelector('#wrap')) return true;
                }
                return false;
            })()
            """
        )

        if not still_blocked:
            log.info("보안코드 자동 통과 성공!")
            return True

        log.warning(f"보안코드 통과 실패, 재시도... (시도 {attempt+1}/3)")
        time.sleep(2)

    # 3회 실패 시 수동 대기로 폴백
    log.warning("AI 자동 인식 3회 실패 — 수동 입력 대기로 전환")
    for i in range(timeout_sec):
        has_block = page.evaluate(
            """
            (() => {
                const blocks = document.querySelectorAll('.blockUI.blockMsg');
                for (const b of blocks) {
                    if (b.offsetWidth > 0 && b.offsetHeight > 0
                        && !b.querySelector('#wrap')) return true;
                }
                return false;
            })()
            """
        )
        if not has_block:
            log.info("보안코드 통과!")
            return True
        time.sleep(1)
    raise TimeoutError("보안코드 대기 시간 초과 (120초)")


def clear_popups(page):
    """화면을 덮는 팝업/광고 오버레이 전부 제거 (이지어드민이 순차로 여러 광고를 띄움 — 2026-07-16 공격적 버전).
    판매처 테이블 등 본문은 z-index 낮아 보존됨."""
    page.evaluate("try { $('.blockUI').remove(); } catch(e) {}")
    page.evaluate("""
        // ① 광고/공지 팝업만 콕 집어 제거 (⚠️ .modal-dialog 통째 제거 금지 — 업로드 모달도 그 클래스라 죽음, 2026-07-16 교훈)
        document.querySelectorAll('#pagecode-popup, .pagecode-popup-cont, [id^=modalRequired]')
            .forEach(el => el.remove());
        // dim 오버레이는 위 광고팝업이 남긴 것만 (업로드 모달의 dim은 보존 위해 光告 제거 후에만)
        document.querySelectorAll('.dim').forEach(el => {
            // 업로드 모달(modal-dialog)이 살아있으면 그 dim은 건드리지 않음
            if (!document.querySelector('.modal-dialog')) el.remove();
        });
        // ② 광고/공지 팝업의 '닫기' 버튼을 실제 클릭 (DOM 제거로 안 죽는 GLOBOX/우체국 광고 대응)
        document.querySelectorAll('.popup-close, .page-close, .aside-close, [class*=popup-close], [class*=btn-close]')
            .forEach(el => { try { if (el.offsetWidth > 0) el.click(); } catch(e) {} });
        // ③ 화면을 크게 덮는 z-index 높은 fixed/absolute 오버레이 제거
        document.querySelectorAll('div, iframe').forEach(el => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            const z = parseInt(s.zIndex) || 0;
            const covers = r.width > 250 && r.height > 200;
            const floating = (s.position === 'fixed' || s.position === 'absolute');
            if (covers && floating && z >= 1000) el.remove();
            if (el.tagName === 'IFRAME' && /ad|banner|promo|epost|notice|globox/i.test(el.src || '')) el.remove();
        });
        document.body.style.overflow = 'auto';
    """)
    page.wait_for_timeout(500)


def click_search(page):
    """검색(F2) 버튼 클릭"""
    page.evaluate(
        """
        (() => {
            const spans = document.querySelectorAll('span.flip');
            for (const s of spans) {
                if (s.textContent.trim() === '검색') { s.click(); return; }
            }
            const all = document.querySelectorAll('button, input[type="button"], input[type="submit"], a, span');
            for (const b of all) {
                const t = (b.textContent || b.value || '').trim();
                if (t.startsWith('검색') && b.offsetWidth > 0) { b.click(); return; }
            }
        })()
        """
    )


def set_max_page_size(page):
    """jqGrid 페이지 사이즈를 최대로 설정"""
    page.evaluate(
        """
        (() => {
            const sels = document.querySelectorAll('.ui-pg-selbox');
            sels.forEach(sel => {
                const opts = [...sel.options];
                const maxOpt = opts[opts.length - 1];
                if (maxOpt) { sel.value = maxOpt.value; sel.dispatchEvent(new Event('change')); }
            });
        })()
        """
    )


def go_next_page(page):
    """jqGrid 다음 페이지 이동. 성공 시 True"""
    return page.evaluate(
        """
        (() => {
            const nextBtn = document.querySelector('.ui-pg-button [class*="seek-next"]');
            if (!nextBtn) return false;
            const parent = nextBtn.closest('.ui-pg-button, td');
            if (parent && !parent.classList.contains('ui-state-disabled')) {
                parent.click(); return true;
            }
            return false;
        })()
        """
    )


def scrape_inventory(page, progress=None):
    """재고현황 (I100) — 상품코드 + 정상재고"""
    if progress:
        progress("scraping_inventory")
    log.info("재고현황 페이지 이동 (I100)...")
    page.goto(f"{BASE}/template35.htm?template=I100", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    clear_popups(page)

    click_search(page)
    page.wait_for_timeout(6000)
    clear_popups(page)

    set_max_page_size(page)
    page.wait_for_timeout(3000)

    inventory = page.evaluate(
        """
        (() => {
            const tbl = document.getElementById('grid1') || document.querySelector('.ui-jqgrid-btable');
            if (!tbl) return {error: 'no_grid'};
            const rows = [...tbl.querySelectorAll('tr')];
            const data = [];
            rows.forEach(tr => {
                const codeCell = tr.querySelector('td[aria-describedby$="_key"]');
                const stockCell = tr.querySelector('td[aria-describedby$="_stock"]');
                if (!codeCell || !stockCell) return;
                const code = codeCell.textContent.trim();
                const stock = parseInt(stockCell.textContent.trim().replace(/,/g, '')) || 0;
                if (code && code.length > 2) data.push({code, stock});
            });
            return data;
        })()
        """
    )

    if isinstance(inventory, dict) and inventory.get("error"):
        log.warning(f"재고 컬럼 찾기 실패: {inventory}")
        return {}

    log.info(f"재고 데이터 {len(inventory)}건 수집")
    today_str = date.today().isoformat()
    return {item["code"]: {"stock": item["stock"], "updated": today_str} for item in inventory}


def scrape_outbound(page, days=90, progress=None, collect_inbound=False):
    """재고수불부 (I500) — 상품별 일자별 (출고+배송) 수량 수집
    컬럼 매핑 (검증 완료 2026-06-25):
      grid1_product_id = 상품코드
      grid1_crdate = 일자
      grid1_stockout = 출고 (로켓배송 직송)
      grid1_trans = 배송 (일반 배송)
      grid1_stockin = 입고 (collect_inbound=True 시 함께 수집)
      grid1_supply_name = 공급처
    판매량 = 출고 + 배송
    collect_inbound=True 면 (출고집계, 입고집계) 튜플을 반환. 기본은 출고집계만 반환(기존 호환).
    """
    if progress:
        progress("scraping_outbound")
    log.info("재고수불부 페이지 이동 (I500)...")
    page.goto(f"{BASE}/template35.htm?template=I500", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    clear_popups(page)

    # 날짜 필드 탐색 및 설정
    start_date = (date.today() - timedelta(days=days)).isoformat()
    end_date = date.today().isoformat()
    date_result = page.evaluate(
        f"""
        (() => {{
            // 모든 텍스트 input 중 날짜 형식(yyyy-mm-dd) 값을 가진 필드 찾기
            const allInputs = [...document.querySelectorAll('input')];
            const datePattern = /^\\d{{4}}-\\d{{2}}-\\d{{2}}$/;
            const dateInputs = allInputs.filter(el => datePattern.test(el.value.trim()));
            const info = dateInputs.map(el => ({{
                id: el.id, name: el.name, value: el.value, type: el.type
            }}));
            if (dateInputs.length >= 2) {{
                dateInputs[0].value = '{start_date}';
                dateInputs[1].value = '{end_date}';
                return {{ok: true, found: info}};
            }}
            // 폴백: 모든 input 정보 반환
            return {{ok: false, all: allInputs.slice(0, 30).map(el => ({{
                id: el.id, name: el.name, type: el.type, value: el.value.substring(0, 30)
            }}))}};
        }})()
        """
    )
    log.info(f"날짜 필드 탐색: {date_result}")

    # 검색 실행
    click_search(page)
    page.wait_for_timeout(8000)
    clear_popups(page)

    set_max_page_size(page)
    page.wait_for_timeout(5000)

    # 전체 데이터 수집 (하드코딩된 컬럼명 사용)
    CODE_COL = "grid1_product_id"
    DATE_COL = "grid1_crdate"
    OUT_COL = "grid1_stockout"
    SHIP_COL = "grid1_trans"

    all_data = []
    all_inbound = []
    max_pages = 50

    for pg in range(max_pages):
        page_data = page.evaluate(
            """
            (() => {
                const tbl = document.getElementById('grid1') || document.querySelector('.ui-jqgrid-btable');
                if (!tbl) return [];
                const rows = [...tbl.querySelectorAll('tr')];
                const data = [];
                const inbound = [];
                rows.forEach(tr => {
                    const codeCell = tr.querySelector('td[aria-describedby="grid1_product_id"]');
                    const nameCell = tr.querySelector('td[aria-describedby="grid1_name"]');
                    const dateCell = tr.querySelector('td[aria-describedby="grid1_crdate"]');
                    const outCell = tr.querySelector('td[aria-describedby="grid1_stockout"]');
                    const shipCell = tr.querySelector('td[aria-describedby="grid1_trans"]');
                    const inCell = tr.querySelector('td[aria-describedby="grid1_stockin"]');
                    const supCell = tr.querySelector('td[aria-describedby="grid1_supply_name"]');
                    if (!codeCell || !dateCell) return;
                    const code = codeCell.textContent.trim();
                    const name = nameCell ? nameCell.textContent.trim() : '';
                    const d = dateCell.textContent.trim().substring(0, 10);
                    const outQty = outCell ? (parseInt(outCell.textContent.trim().replace(/,/g, '')) || 0) : 0;
                    const shipQty = shipCell ? (parseInt(shipCell.textContent.trim().replace(/,/g, '')) || 0) : 0;
                    const inQty = inCell ? (parseInt(inCell.textContent.trim().replace(/,/g, '')) || 0) : 0;
                    const supplier = supCell ? supCell.textContent.trim() : '';
                    const totalQty = outQty + shipQty;
                    if (code && code.length > 2 && d.length === 10) {
                        if (totalQty > 0) {
                            data.push({code, name, date: d, qty: totalQty, out: outQty, ship: shipQty});
                        }
                        if (inQty > 0) {
                            inbound.push({code, name, date: d, qty: inQty, supplier});
                        }
                    }
                });
                return {out: data, inb: inbound};
            })()
            """
        )

        page_out = (page_data or {}).get("out", [])
        page_inb = (page_data or {}).get("inb", [])
        if not page_out and not page_inb:
            if pg == 0:
                log.warning("I500 첫 페이지 데이터 없음 — 날짜 설정 실패 가능성")
            break

        all_data.extend(page_out)
        all_inbound.extend(page_inb)

        if pg == 0:
            for item in page_out[:3]:
                log.info(f"  샘플(출고): {item['code']} {item['date']} 출고={item['out']} 배송={item['ship']} 합계={item['qty']}")
            for item in page_inb[:3]:
                log.info(f"  샘플(입고): {item['code']} {item['date']} 입고={item['qty']} 공급처={item.get('supplier','')}")

        if not go_next_page(page):
            log.info(f"페이지 {pg+1} — 마지막 도달 ({len(all_data)}건)")
            break
        log.info(f"페이지 {pg+1} 완료 ({len(all_data)}건) — 다음 페이지로...")
        page.wait_for_timeout(4000)
        clear_popups(page)

    log.info(f"재고수불부 출고+배송 총 {len(all_data)}건 수집")

    # 상품코드→상품명 매핑 (첫 등장 기준)
    name_map = {}
    for o in all_data:
        if o["code"] not in name_map and o.get("name"):
            name_map[o["code"]] = o["name"]

    # 날짜+상품코드별 집계
    agg = {}
    for o in all_data:
        key = f"{o['date']}|{o['code']}"
        if key in agg:
            agg[key]["qty"] += o["qty"]
        else:
            agg[key] = {"date": o["date"], "code": o["code"], "qty": o["qty"]}
    result = list(agg.values())
    log.info(f"일별 집계 {len(result)}건")

    # 전체 상품 요약 (상품명 포함)
    product_totals = {}
    for r in result:
        product_totals[r["code"]] = product_totals.get(r["code"], 0) + r["qty"]
    ranked = sorted(product_totals.items(), key=lambda x: -x[1])
    for code, total in ranked:
        name = name_map.get(code, "?")
        log.info(f"  {code} [{name}]: 총 {total}개 ({total/max(days,1):.1f}개/일)")

    if collect_inbound:
        # 입고 날짜+상품코드별 집계 (공급처/상품명 유지)
        in_agg = {}
        for o in all_inbound:
            key = f"{o['date']}|{o['code']}"
            if key in in_agg:
                in_agg[key]["qty"] += o["qty"]
            else:
                in_agg[key] = {
                    "date": o["date"], "code": o["code"], "qty": o["qty"],
                    "name": o.get("name", ""), "supplier": o.get("supplier", ""),
                }
        inbound_result = list(in_agg.values())
        log.info(f"입고 집계 {len(inbound_result)}건 (원시 {len(all_inbound)}건)")
        return result, inbound_result

    return result


# ─────────────────────────────────────────────────────────────────────────────
# DS00 매출 = "다운로드 방식" (2026-07-22, ACG 이전 대응 최종 해결)
# ─────────────────────────────────────────────────────────────────────────────
# 배경: ACG(annexcombine) 이지어드민 계정은 확장주문검색2(DS00) '화면 그리드'에
#   판매가·정산금액·상품코드 컬럼이 없다(주문/배송 정보만). 금액은 오직 '다운로드
#   양식'(판매데이터 확인용 = DS00_file_13)에만 있다. → 화면 스크랩 불가, 다운로드 필수.
# reCAPTCHA: save_file_go()가 function.htm에 template=recaptcha&action=check_log_web
#   POST → 서버가 {"error":0|1} 반환. error==1일 때만 이미지 캡차(download_check_invisible).
#   error==0(정상 다운로드 빈도)이면 캡차 없이 바로 진행. "매번 뜬다"는 오해였음(2026-07-22 실측).
# 다운로드 흐름: ins_download_worklist(작업큐 등록) → get_download_worklist 폴링(status==2)
#   → file_name(https://.../*.xls, HTML테이블 형식) 다운로드 → pandas.read_html 파싱.
# 캡차 회피 설계: 다운로드 1회당 error 판정 → 날짜별 개별 대신 "범위 1회 다운로드 후
#   주문일 그룹핑"으로 다운로드 횟수 최소화(일일 롤링·배치 모두 1회).

DS00_DOWNLOAD_FIELD = "DS00_file_13"  # '판매데이터 확인용' 양식(금액 포함). 바뀌면 이 값만 갱신.


class CaptchaRequired(Exception):
    """다운로드 시 서버가 reCAPTCHA를 요구(check_log_web error=1). 봇 의심/과다 다운로드."""


def _ds00_search(page, date_from, date_to):
    """DS00 페이지 열고 주문일 기준 date_from~date_to 검색 (myform에 비코어랩 판매처 필터 세팅)."""
    page.goto(f"{BASE}/template35.htm?template=DS00", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    clear_popups(page)
    # 날짜타입 → 주문일
    page.evaluate(
        """() => { for (const sel of document.querySelectorAll('select')) {
            const o=[...sel.options].find(o=>o.text.includes('주문일'));
            if(o){sel.value=o.value;sel.dispatchEvent(new Event('change',{bubbles:true}));return;} } }"""
    )
    page.wait_for_timeout(800)
    page.evaluate(
        f"""() => {{ const s=document.getElementById('start_date'), e=document.getElementById('end_date');
            if(s)s.value='{date_from}'; if(e)e.value='{date_to}'; }}"""
    )
    click_search(page)
    page.wait_for_timeout(8000)
    clear_popups(page)


def _worklist_max_seq(page):
    """현재 다운로드 워크리스트의 최대 seq (신규 작업 식별용)."""
    try:
        wl = page.evaluate(
            """async () => new Promise(r=>{ $.post("main35_func.php",
                {action:"get_download_worklist", timeFlag: Date()}, function(d){ r(d); }); })"""
        )
        import json as _json
        data = _json.loads(wl).get("data", [])
        return max((int(d.get("seq", 0)) for d in data), default=0)
    except Exception:
        return 0


def _queue_ds00_download(page):
    """검색된 상태에서 판매데이터 확인용(DS00_file_13) 다운로드 작업을 큐에 등록하고
    생성 완료된 파일 URL을 반환. reCAPTCHA 요구 시 CaptchaRequired 발생."""
    # 다운로드 양식/타입 선택
    page.evaluate(
        f"""() => {{ const df=document.getElementById('download_field');
            if(df){{df.value='{DS00_DOWNLOAD_FIELD}';df.dispatchEvent(new Event('change',{{bubbles:true}}));}}
            const dt=document.getElementById('download_type');
            if(dt){{dt.value='0';dt.dispatchEvent(new Event('change',{{bubbles:true}}));}} }}"""
    )
    page.wait_for_timeout(700)

    prev_max = _worklist_max_seq(page)

    # save_file_go() 로직 재현 → download_form 채우기
    page.evaluate(
        """() => {
            const df = document.forms['download_form']; df.reset();
            df.par.value = $("#myform").serialize();
            df.panel_open.value = (typeof panel_open!=='undefined')?panel_open:'true';
            df.download_type.value = $("#download_type").val();
            df.download_field.value = $("#download_field").val();
            if(df.seq_list) df.seq_list.value = "";
            if(df.include_sum) df.include_sum.value = "0";
            if(df.include_img_url) df.include_img_url.value = "0";
            if(df.include_pw) df.include_pw.value = "0";
            df.action.value = "save_file_DS00";
            df.bck_search.value = "0";
        }"""
    )
    # reCAPTCHA 필요 여부 판정
    chk = page.evaluate(
        """async () => new Promise(r=>{ $.post("function.htm",
            {template:"recaptcha", action:"check_log_web", check_template:"DS00",
             download_form: $("#download_form").serialize()}, function(d){ r(d); }); })"""
    )
    if '"error":1' in str(chk) or str(chk).strip() == "1":
        raise CaptchaRequired(f"check_log_web 응답: {chk}")
    log.info(f"다운로드 캡차판정 통과(error=0): {chk}")

    # 작업 큐 등록
    page.evaluate(
        """async () => new Promise(r=>{ $.post("/function.htm",
            {template:"download", action:"ins_download_worklist",
             work_template:"DS00", work_func:"save_file_DS00", par: $("#download_form").serialize()},
            function(d){ r(d); }); })"""
    )

    # 워크리스트 폴링 — prev_max보다 큰 seq의 status==2(완료) DS00 작업
    import json as _json
    for i in range(40):  # 최대 ~120초
        time.sleep(3)
        wl = page.evaluate(
            """async () => new Promise(r=>{ $.post("main35_func.php",
                {action:"get_download_worklist", timeFlag: Date()}, function(d){ r(d); }); })"""
        )
        try:
            data = _json.loads(wl).get("data", [])
        except Exception:
            continue
        news = [d for d in data if int(d.get("seq", 0)) > prev_max
                and d.get("work_template") == "DS00"
                and str(d.get("file_name", "")).startswith("http")]
        done = [d for d in news if d.get("status") == "2"]
        if done:
            done.sort(key=lambda d: int(d.get("seq", 0)), reverse=True)
            f = done[0]
            log.info(f"다운로드 파일 생성완료: rows={f.get('total_rows')} {f.get('file_name')}")
            return f["file_name"], int(f.get("total_rows", 0) or 0)
        if news and any(d.get("status") in ("3", "9") for d in news):  # 실패/오류 상태 방어
            raise RuntimeError(f"다운로드 작업 실패 상태: {[d.get('status') for d in news]}")
    raise TimeoutError("다운로드 파일 생성 대기 시간 초과(120초)")


# 다운로드 xls(HTML테이블) 헤더 → 표준 필드 매핑
_DS00_COL = {
    "주문번호": "orderId", "상품코드": "code", "상품명": "name", "판매처": "shop",
    "판매처 상품명": "nameOpt", "판매처 옵션": "option", "주문수량": "orderQty",
    "상품수량": "productQty", "상품별판매금액": "amount", "정산금액": "settlement",
    "주문일": "date",
}


def _parse_ds00_file(path):
    """다운로드된 HTML테이블 .xls 파싱 → 표준 order dict 리스트."""
    import pandas as pd
    raw = pd.read_html(path, header=None)[0]
    header = [str(x).strip() for x in raw.iloc[0]]
    body = raw.iloc[1:]
    idx = {name: i for i, name in enumerate(header)}

    def cell(row, colname, numeric=False):
        i = idx.get(colname)
        if i is None:
            return 0 if numeric else ""
        v = row.iloc[i]
        if numeric:
            try:
                return int(float(str(v).replace(",", "").replace("₩", "").strip() or 0))
            except (ValueError, TypeError):
                return 0
        s = str(v).strip()
        return "" if s == "nan" else s

    orders = []
    for _, row in body.iterrows():
        code = cell(row, "상품코드")
        if not code:
            continue
        orders.append({
            "orderId": cell(row, "주문번호"),
            "code": code,
            "name": cell(row, "상품명"),
            "shop": cell(row, "판매처"),
            "nameOpt": cell(row, "판매처 상품명") or cell(row, "상품명"),
            "option": cell(row, "판매처 옵션") or cell(row, "옵션명"),
            "orderQty": cell(row, "주문수량", numeric=True),
            "productQty": cell(row, "상품수량", numeric=True) or cell(row, "주문수량", numeric=True),
            "amount": cell(row, "상품별판매금액", numeric=True) or cell(row, "판매가", numeric=True),
            "settlement": cell(row, "정산금액", numeric=True),
            "date": cell(row, "주문일"),
            "stock": 0,
        })
    return orders


def _summarize_day(orders, target_date):
    """하루치 order 리스트 → 채널/상품별 집계 요약 dict (기존 scrape_sales 반환구조와 동일)."""
    channel_summary, product_summary = {}, {}
    total_amount = total_settlement = 0
    for row in orders:
        shop, code = row["shop"], row["code"]
        cs = channel_summary.setdefault(shop, {"count": 0, "qty": 0, "amount": 0, "settlement": 0})
        cs["count"] += 1
        cs["qty"] += row["productQty"]
        cs["amount"] += row["amount"]
        cs["settlement"] += row["settlement"]
        ps = product_summary.setdefault(code, {"name": row["nameOpt"] or row["name"],
                                               "qty": 0, "amount": 0, "settlement": 0})
        ps["qty"] += row["productQty"]
        ps["amount"] += row["amount"]
        ps["settlement"] += row["settlement"]
        total_amount += row["amount"]
        total_settlement += row["settlement"]
    log.info(f"=== {target_date} 매출 요약 (다운로드) ===")
    log.info(f"  총 판매금액: {total_amount:,}원 / 정산: {total_settlement:,}원 ({len(orders)}건)")
    for shop, d in sorted(channel_summary.items(), key=lambda x: -x[1]["amount"]):
        log.info(f"  {shop}: {d['count']}건, 수량 {d['qty']}, 판매 {d['amount']:,}원, 정산 {d['settlement']:,}원")
    return {
        "date": target_date,
        "total_amount": total_amount,
        "total_settlement": total_settlement,
        "total_count": len(orders),
        "by_channel": channel_summary,
        "by_product": product_summary,
        "orders": orders,
    }


def scrape_sales_range(page, date_from, date_to, progress=None):
    """주문일 date_from~date_to를 '다운로드 1회'로 수집 → {날짜: 요약dict} 반환.
    다운로드 파일은 이미 주문단위로 dedup되어 있어 화면 스크랩의 4~7배 중복 제거가 불필요."""
    if progress:
        progress("scraping_sales_download")
    log.info(f"DS00 매출 다운로드 — 주문일 {date_from} ~ {date_to}")
    _ds00_search(page, date_from, date_to)
    url, total_rows = _queue_ds00_download(page)
    save_path = os.path.join(tempfile.gettempdir(), f"ds00_{date_from}_{date_to}.xls")
    resp = page.context.request.get(url)
    if resp.status != 200:
        raise RuntimeError(f"파일 다운로드 실패 HTTP {resp.status}: {url}")
    with open(save_path, "wb") as f:
        f.write(resp.body())
    orders = _parse_ds00_file(save_path)
    log.info(f"파싱 {len(orders)}건 (파일 total_rows={total_rows})")

    # 주문일 그룹핑 (파일 날짜가 요청범위를 벗어나면 방어적으로 필터)
    by_date = {}
    for o in orders:
        d = o.get("date", "")
        if not re.match(r"\d{4}-\d{2}-\d{2}", d):
            continue
        if d < date_from or d > date_to:
            continue
        by_date.setdefault(d, []).append(o)

    results = {}
    cur = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    while cur <= end:
        ds = cur.isoformat()
        results[ds] = _summarize_day(by_date.get(ds, []), ds)
        cur += timedelta(days=1)
    return results


def scrape_sales(page, target_date=None, date_end=None, progress=None):
    """확장주문검색2(DS00) 매출 수집 — 다운로드 방식(2026-07-22~).
    단일 날짜(target_date)면 그날, date_end 지정 시 범위 전체를 '다운로드 1회'로 수집.
    반환: date_end 없으면 target_date 하루치 요약dict(기존 호출부 호환).
          date_end 있으면 범위 전체를 하나로 합친 요약dict(date=target_date)."""
    if target_date is None:
        target_date = (date.today() - timedelta(days=1)).isoformat()
    if date_end is None:
        date_end = target_date
    results = scrape_sales_range(page, target_date, date_end, progress=progress)
    if date_end == target_date:
        return results.get(target_date, _summarize_day([], target_date))
    merged = []
    for ds in sorted(results):
        merged.extend(results[ds]["orders"])
    return _summarize_day(merged, target_date)


def _scrape_sales_screen_DEPRECATED(page, target_date=None, date_end=None, progress=None):
    """[폐기 2026-07-22] 화면 그리드 스크랩 방식. ACG 계정은 화면에 금액컬럼이 없어 사용 불가.
    참고용으로 보존. 실제 매출 수집은 scrape_sales_range(다운로드) 사용.
    (구 컬럼 매핑: grid1_shop_id=판매처 / grid1_amount=판매가 / grid1_supply_price=정산금액 등)"""
    if progress:
        progress("scraping_sales")
    if target_date is None:
        target_date = (date.today() - timedelta(days=1)).isoformat()
    if date_end is None:
        date_end = target_date
    log.info(f"확장주문검색2 페이지 이동 (DS00) — 주문일 기준: {target_date} ~ {date_end}")
    page.goto(f"{BASE}/template35.htm?template=DS00", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    clear_popups(page)

    # 날짜 타입을 "주문일"로 변경 (기본값 "발주일" → "주문일")
    page.evaluate(
        """
        (() => {
            const selects = [...document.querySelectorAll('select')];
            for (const sel of selects) {
                const opts = [...sel.options];
                const orderOpt = opts.find(o => o.text.includes('주문일'));
                if (orderOpt) {
                    sel.value = orderOpt.value;
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                    return {ok: true, value: orderOpt.value, text: orderOpt.text};
                }
            }
            return {ok: false};
        })()
        """
    )
    page.wait_for_timeout(1000)

    # 날짜 설정
    page.evaluate(
        f"""
        (() => {{
            const s = document.getElementById('start_date');
            const e = document.getElementById('end_date');
            if (s) s.value = '{target_date}';
            if (e) e.value = '{date_end}';
        }})()
        """
    )

    # 검색 실행
    click_search(page)
    page.wait_for_timeout(8000)
    clear_popups(page)

    # 페이지 크기 최대로 → 재검색으로 반영
    set_max_page_size(page)
    page.wait_for_timeout(2000)
    click_search(page)
    page.wait_for_timeout(6000)
    clear_popups(page)

    # 그리드 로딩 안정화 대기 (2026-06-29): 공동구매 등 주문이 폭발한 날은 그리드 로딩이 느려
    # 고정 대기로는 로딩 전에 읽어 0건/빈 order_id(과대)가 발생함(6/22·6/25 사례).
    # 행 수가 더 안 늘고 안정될 때까지 polling 대기(최대 ~30초).
    prev_cnt, stable = -1, 0
    for _ in range(15):
        cnt = page.evaluate(
            "() => { const t=document.getElementById('grid1')||document.querySelector('.ui-jqgrid-btable');"
            " return t ? t.querySelectorAll('tr.jqgrow').length : 0; }"
        )
        if cnt > 0 and cnt == prev_cnt:
            stable += 1
            if stable >= 2:  # 2회 연속 동일 = 로딩 완료
                break
        else:
            stable = 0
        prev_cnt = cnt
        page.wait_for_timeout(2000)
    log.info(f"그리드 로딩 안정화: {prev_cnt}행")

    # 전체 데이터 수집 (페이지네이션)
    all_data = []
    max_pages = 20

    for pg in range(max_pages):
        page_data = page.evaluate(
            """
            (() => {
                const tbl = document.getElementById('grid1') || document.querySelector('.ui-jqgrid-btable');
                if (!tbl) return [];
                const rows = [...tbl.querySelectorAll('tr.jqgrow')];
                const data = [];
                rows.forEach(tr => {
                    const get = key => {
                        const td = tr.querySelector('td[aria-describedby="grid1_' + key + '"]');
                        return td ? td.textContent.trim() : '';
                    };
                    const parseNum = v => parseInt((v || '0').replace(/,/g, '')) || 0;

                    const shop = get('shop_id');
                    const orderId = get('order_id');
                    const dt = get('collect_date');
                    const code = get('product_id');
                    const name = get('name');
                    const nameOpt = get('product_name_options');
                    const option = get('p_options');
                    const orderQty = parseNum(get('qty'));
                    const productQty = parseNum(get('order_products_qty'));
                    const amount = parseNum(get('amount'));
                    const settlement = parseNum(get('supply_price'));
                    const stock = parseNum(get('stock'));

                    if (code) {
                        data.push({
                            shop, orderId, date: dt, code, name, nameOpt,
                            option, orderQty, productQty,
                            amount, settlement, stock
                        });
                    }
                });
                return data;
            })()
            """
        )

        if not page_data:
            if pg == 0:
                log.warning("DS00 첫 페이지 데이터 없음")
            break

        all_data.extend(page_data)

        if pg == 0:
            for item in page_data[:3]:
                log.info(f"  샘플: {item['shop']} | {item['code']} {item['nameOpt']} | "
                         f"수량={item['productQty']} 판매가={item['amount']:,} 정산={item['settlement']:,}")

        if not go_next_page(page):
            log.info(f"DS00 페이지 {pg+1} — 마지막 도달 ({len(all_data)}건)")
            break
        log.info(f"DS00 페이지 {pg+1} 완료 ({len(all_data)}건) — 다음 페이지로...")
        page.wait_for_timeout(4000)
        clear_popups(page)

    log.info(f"확장주문검색2 총 {len(all_data)}건 수집")

    # ── DS00 그리드 중복행 제거 + 주문일 보정 (2026-06-29 검증) ──
    # DS00은 한 주문×상품을 4~7배 중복 출력함. (채널,주문번호)로 묶어 첫행만 쓰면
    # 멀티상품 주문의 나머지 상품 금액을 통째로 버려 -33% 과소가 됨.
    # → 완전동일행(주문번호+상품+옵션+금액+수량)만 제거해 상품행은 보존.
    #   검증: 완전동일행 dedup + 정산금액(supply) = 스스 -3% / 카페24 +4% (정답지 일치)
    # 날짜도 collect_date(발주일=수집일, 주말 뭉침) → 주문일(order_id 앞 8자리)로 교정.
    seen = set()
    deduped = []
    for row in all_data:
        key = (row.get("orderId", ""), row["code"], row["option"],
               row["amount"], row["settlement"], row["orderQty"], row["productQty"])
        if key in seen:
            continue
        seen.add(key)
        m = re.match(r"(\d{8})", str(row.get("orderId", "")))
        if m:
            row["date"] = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}"
        deduped.append(row)
    log.info(f"DS00 중복행 제거: {len(all_data)} → {len(deduped)}행 (그리드 4~7배 반복 제거)")
    all_data = deduped

    # order_id 빈값 방어 (2026-06-29): order_id가 비면 주문일 보정이 안 돼 발주일(collect_date)로
    # 폴백 → 여러 날 주문이 한 날로 뭉쳐 과대해짐(실제 6/22가 383행·676만으로 부풀었음).
    # 빈값 비율이 높으면 그리드 수집 자체가 불완전한 것이므로 그날 수집을 무효화한다.
    # (빈 결과 → 멱등 저장이 기존 데이터 보존 → 과대 데이터 유입 차단, 다음 수집 때 정상화)
    empty_oid = sum(1 for r in all_data if not r.get("orderId"))
    if all_data and empty_oid / len(all_data) > 0.2:
        log.warning(f"⚠️ DS00 order_id 빈 행 {empty_oid}/{len(all_data)} "
                    f"({empty_oid / len(all_data) * 100:.0f}%) — 주문일 보정 불가, "
                    f"{target_date} 수집 무효화(과대 방지)")
        all_data = []

    # 채널별 집계
    channel_summary = {}
    product_summary = {}
    total_amount = 0
    total_settlement = 0

    for row in all_data:
        shop = row["shop"]
        code = row["code"]

        if shop not in channel_summary:
            channel_summary[shop] = {"count": 0, "qty": 0, "amount": 0, "settlement": 0}
        channel_summary[shop]["count"] += 1
        channel_summary[shop]["qty"] += row["productQty"]
        channel_summary[shop]["amount"] += row["amount"]
        channel_summary[shop]["settlement"] += row["settlement"]

        if code not in product_summary:
            product_summary[code] = {"name": row["nameOpt"] or row["name"], "qty": 0, "amount": 0, "settlement": 0}
        product_summary[code]["qty"] += row["productQty"]
        product_summary[code]["amount"] += row["amount"]
        product_summary[code]["settlement"] += row["settlement"]

        total_amount += row["amount"]
        total_settlement += row["settlement"]

    # 로그 출력
    log.info(f"=== {target_date} 매출 요약 ===")
    log.info(f"  총 판매금액: {total_amount:,}원 / 정산예정: {total_settlement:,}원")
    for shop, d in sorted(channel_summary.items(), key=lambda x: -x[1]["amount"]):
        log.info(f"  {shop}: {d['count']}건, 수량 {d['qty']}, 판매 {d['amount']:,}원, 정산 {d['settlement']:,}원")

    return {
        "date": target_date,
        "total_amount": total_amount,
        "total_settlement": total_settlement,
        "total_count": len(all_data),
        "by_channel": channel_summary,
        "by_product": product_summary,
        "orders": all_data,
    }


def fetch_all_data(progress=None, sales_target_date=None, sales_days=1):
    """전체 데이터 수집 오케스트레이션

    Args:
        progress: 진행 상황 콜백 함수
        sales_target_date: 매출 수집 타겟 날짜 (YYYY-MM-DD). 지정 시 그 1일만.
        sales_days: 매출 롤링 재수집 일수 (sales_target_date 없을 때만). 어제부터 N일치.
    """
    if progress:
        progress("starting")

    with sync_playwright() as p:
        browser, context, page = get_browser(p)
        try:
            if progress:
                progress("logging_in")
            ezadmin_login(page)
            clear_popups(page)
            wait_for_captcha(page, progress=progress, timeout_sec=120)
            clear_popups(page)

            inventory = scrape_inventory(page, progress=progress)
            orders, inbound = scrape_outbound(page, days=90, progress=progress, collect_inbound=True)

            # 매출: 롤링 재수집 — 취소/환불/지연주문은 며칠에 걸쳐 발생하므로
            # 최근 sales_days일을 매번 다시 긁어 덮어써야 오차가 누적되지 않음.
            # 다운로드 방식(2026-07-22~): 범위 '1회 다운로드' 후 날짜 그룹핑(캡차 위험 최소화).
            sales_history = []
            if sales_target_date is not None:
                date_from = date_to = sales_target_date
            else:
                date_to = (date.today() - timedelta(days=1)).isoformat()
                date_from = (date.today() - timedelta(days=sales_days)).isoformat()
            day_results = scrape_sales_range(page, date_from, date_to, progress=progress)
            # 최신 날짜가 sales[0]에 오도록 역순 정렬(기존: 어제부터)
            for ds in sorted(day_results, reverse=True):
                sales_history.append(day_results[ds])
            sales = sales_history[0] if sales_history else None

            if progress:
                progress("done")

            return {
                "inventory": inventory,
                "orders": orders,
                "inbound": inbound,
                "sales": sales,
                "sales_history": sales_history,
            }
        except Exception as e:
            log.error(f"데이터 수집 오류: {e}")
            raise
        finally:
            browser.close()


def batch_rescrape_sales(start_date, end_date, progress=None):
    """주문일 기준 매출 재수집 — '다운로드 1회'로 범위 전체 수집 후 날짜 그룹핑.
    (기존 날짜별 루프 = 다운로드 N회 → reCAPTCHA 위험. 범위 1회로 개선 2026-07-22)

    Returns: dict of {date_str: sales_data}
    """
    with sync_playwright() as p:
        browser, context, page = get_browser(p)
        try:
            if progress:
                progress("batch_login")
            ezadmin_login(page)
            clear_popups(page)
            wait_for_captcha(page, progress=progress, timeout_sec=300)
            clear_popups(page)

            if progress:
                progress(f"batch_download_{start_date}~{end_date}")
            results = scrape_sales_range(page, start_date, end_date, progress=progress)

            if progress:
                progress("batch_done")
            log.info(f"배치 재수집 완료: {len(results)}일, "
                     f"총 {sum(r['total_count'] for r in results.values())}건")
            return results
        except CaptchaRequired as e:
            log.error(f"배치 재수집 reCAPTCHA 차단: {e}")
            raise
        except Exception as e:
            log.error(f"배치 재수집 오류: {e}")
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = fetch_all_data(progress=lambda s: print(f"[{s}]"))
    print(f"\n재고: {len(result['inventory'])}건")
    print(f"주문: {len(result['orders'])}건")
    for code, info in list(result["inventory"].items())[:5]:
        print(f"  {code}: {info['stock']}개")
    for o in result["orders"][:5]:
        print(f"  {o['date']} {o['code']} {o['qty']}개")
