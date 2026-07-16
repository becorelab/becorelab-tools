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
import requests
from datetime import date, timedelta
from playwright.sync_api import sync_playwright

from config import EZADMIN

log = logging.getLogger(__name__)

BASE = "https://ka04.ezadmin.co.kr"


def get_browser(p):
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
    )
    page = context.new_page()
    page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, context, page


def ezadmin_login(page):
    """로그인 + 보안코드 대기 (www.ezadmin.co.kr 메인 로그인)"""
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
    log.info("보안코드 대기...")
    return True


def _find_anthropic_key():
    """클로드 키 탐색: 환경변수 → logistics/.env → sourcing/analyzer/.env (2026-07-16 Gemini 유출로 전환)"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    for env_path in (
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        "/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/.env",
    ):
        try:
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("ANTHROPIC_API_KEY="):
                            return line.split("=", 1)[1].strip()
        except Exception as e:
            log.warning(f".env 탐색 실패({env_path}): {e}")
    return ""


def _read_captcha_with_vision(screenshot_path, max_retries=2):
    """스크린샷에서 보안코드 숫자를 Claude Vision으로 읽기 (Gemini 키 유출로 2026-07-16 전환)"""
    import base64
    api_key = _find_anthropic_key()
    if not api_key:
        log.error("ANTHROPIC_API_KEY를 찾을 수 없음")
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

        # Claude Vision으로 읽기
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
        // ① 알려진 팝업 클래스/ID
        document.querySelectorAll('.dim, .modal-pop, .modal-dialog, [id^=modalRequired]')
            .forEach(el => el.remove());
        // ② 화면을 크게 덮는 z-index 높은 fixed/absolute 오버레이 (광고 팝업 포함)
        document.querySelectorAll('div, iframe').forEach(el => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            const z = parseInt(s.zIndex) || 0;
            const covers = r.width > 250 && r.height > 200;
            const floating = (s.position === 'fixed' || s.position === 'absolute');
            // 광고 iframe / 높은 z-index 부유 오버레이만 (본문 테이블은 position:static이라 안 걸림)
            if (covers && floating && z >= 1000) el.remove();
            if (el.tagName === 'IFRAME' && /ad|banner|promo|epost|notice/i.test(el.src || '')) el.remove();
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


def scrape_sales(page, target_date=None, date_end=None, progress=None):
    """확장주문검색2 (DS00) — 판매처별 주문 + 매출 데이터 수집
    컬럼 매핑 (검증 완료):
      grid1_shop_id = 판매처
      grid1_collect_date = 발주일
      grid1_product_id = 상품코드
      grid1_name = 상품명
      grid1_product_name_options = 상품명+옵션
      grid1_p_options = 옵션명
      grid1_qty = 주문수량
      grid1_order_products_qty = 상품수량
      grid1_amount = 판매가
      grid1_supply_price = 정산금액
      grid1_stock = 현재고
    검색 기준: 주문일 (고객 실제 주문일 — 발주일은 이지어드민 수집일이라 주말이 뭉침)
    """
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
            # (로그인 1번 세션 내에서 날짜만 바꿔 반복 → 캡챠 추가 없음)
            sales_history = []
            if sales_target_date is not None:
                sales_history.append(scrape_sales(page, target_date=sales_target_date, progress=progress))
            else:
                for i in range(1, sales_days + 1):
                    ds = (date.today() - timedelta(days=i)).isoformat()
                    sales_history.append(scrape_sales(page, target_date=ds, progress=progress))
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
    """주문일 기준으로 날짜별 매출 재수집 (한번 로그인, 날짜별 루프)

    Returns: dict of {date_str: sales_data}
    """
    from datetime import datetime
    results = {}
    current = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    total_days = (end - current).days + 1

    with sync_playwright() as p:
        browser, context, page = get_browser(p)
        try:
            if progress:
                progress(f"batch_login")
            ezadmin_login(page)
            clear_popups(page)
            wait_for_captcha(page, progress=progress, timeout_sec=300)
            clear_popups(page)

            day_num = 0
            while current <= end:
                day_num += 1
                ds = current.isoformat()
                if progress:
                    progress(f"batch_sales_{day_num}/{total_days}_{ds}")
                log.info(f"=== 배치 재수집 {day_num}/{total_days}: {ds} ===")
                try:
                    sales = scrape_sales(page, target_date=ds, progress=None)
                    results[ds] = sales
                    log.info(f"  → {ds}: {sales['total_count']}건, 정산 {sales['total_settlement']:,}원")
                except Exception as e:
                    log.error(f"  → {ds} 수집 실패: {e}")
                    results[ds] = {"date": ds, "total_amount": 0, "total_settlement": 0,
                                   "total_count": 0, "by_channel": {}, "by_product": {}, "orders": []}
                current += timedelta(days=1)

            if progress:
                progress("batch_done")
            log.info(f"배치 재수집 완료: {len(results)}일, 총 {sum(r['total_count'] for r in results.values())}건")
            return results
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
