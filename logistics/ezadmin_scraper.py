#!/usr/bin/env python3
"""
이지어드민 데이터 자동 수집 스크래퍼
- 로그인 + 보안코드 자동인식 + 재고현황(I100) + 재고수불부(I500) 출고량 수집
"""
import logging
import time
import os
import base64
import tempfile
import io
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


def _read_captcha_with_vision(screenshot_path, max_retries=2):
    """스크린샷에서 보안코드 숫자를 Gemini Vision으로 읽기"""
    try:
        import google.generativeai as genai
        from PIL import Image
    except ImportError as e:
        log.error(f"Gemini/Pillow 모듈 없음: {e}")
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("GEMINI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            break
        except Exception as e:
            log.warning(f".env에서 GEMINI_API_KEY 탐색 실패: {e}")

    if not api_key:
        log.error("GEMINI_API_KEY를 찾을 수 없음")
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    for attempt in range(max_retries):
        try:
            with Image.open(screenshot_path) as img:
                response = model.generate_content([
                    "이 이미지에 보안코드 숫자 4자리가 보입니다. 숫자만 정확히 알려주세요. 숫자 4자리만 출력하세요. 예: 1234",
                    img,
                ])
            code = (response.text or "").strip()
            digits = ''.join(c for c in code if c.isdigit())
            if len(digits) >= 4:
                return digits[:4]
            log.warning(f"보안코드 인식 결과 부족: '{code}' (시도 {attempt+1})")
        except Exception as e:
            log.error(f"Gemini Vision API 호출 실패 (시도 {attempt+1}): {e}")

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
                    if (b.offsetWidth > 0 && b.offsetHeight > 0
                        && !b.querySelector('#wrap')) return true;
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
        # 스크린샷 촬영
        screenshot_path = os.path.join(tempfile.gettempdir(), f"captcha_{attempt}.png")
        page.screenshot(path=screenshot_path)
        log.info(f"스크린샷 촬영 완료: {screenshot_path}")

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
    """blockUI 팝업 + dim 레이어 전체 제거 (매일 다른 팝업도 대응)"""
    page.evaluate("try { $('.blockUI').remove(); } catch(e) {}")
    page.evaluate("document.querySelectorAll('.dim').forEach(el => el.remove())")
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


def scrape_outbound(page, days=90, progress=None):
    """재고수불부 (I500) — 상품별 일자별 (출고+배송) 수량 수집
    컬럼 매핑 (검증 완료):
      grid1_product_id = 상품코드
      grid1_crdate = 일자
      grid1_stockout = 출고 (로켓배송 직송)
      grid1_trans = 배송 (일반 배송)
    판매량 = 출고 + 배송
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
    max_pages = 50

    for pg in range(max_pages):
        page_data = page.evaluate(
            """
            (() => {
                const tbl = document.getElementById('grid1') || document.querySelector('.ui-jqgrid-btable');
                if (!tbl) return [];
                const rows = [...tbl.querySelectorAll('tr')];
                const data = [];
                rows.forEach(tr => {
                    const codeCell = tr.querySelector('td[aria-describedby="grid1_product_id"]');
                    const nameCell = tr.querySelector('td[aria-describedby="grid1_name"]');
                    const dateCell = tr.querySelector('td[aria-describedby="grid1_crdate"]');
                    const outCell = tr.querySelector('td[aria-describedby="grid1_stockout"]');
                    const shipCell = tr.querySelector('td[aria-describedby="grid1_trans"]');
                    if (!codeCell || !dateCell) return;
                    const code = codeCell.textContent.trim();
                    const name = nameCell ? nameCell.textContent.trim() : '';
                    const d = dateCell.textContent.trim().substring(0, 10);
                    const outQty = outCell ? (parseInt(outCell.textContent.trim().replace(/,/g, '')) || 0) : 0;
                    const shipQty = shipCell ? (parseInt(shipCell.textContent.trim().replace(/,/g, '')) || 0) : 0;
                    const totalQty = outQty + shipQty;
                    if (code && code.length > 2 && d.length === 10 && totalQty > 0) {
                        data.push({code, name, date: d, qty: totalQty, out: outQty, ship: shipQty});
                    }
                });
                return data;
            })()
            """
        )

        if not page_data:
            if pg == 0:
                log.warning("I500 첫 페이지 데이터 없음 — 날짜 설정 실패 가능성")
            break

        all_data.extend(page_data)

        if pg == 0:
            for item in page_data[:3]:
                log.info(f"  샘플: {item['code']} {item['date']} 출고={item['out']} 배송={item['ship']} 합계={item['qty']}")

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

    return result


def scrape_sales(page, target_date=None, progress=None):
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
    """
    if progress:
        progress("scraping_sales")
    if target_date is None:
        target_date = (date.today() - timedelta(days=1)).isoformat()
    log.info(f"확장주문검색2 페이지 이동 (DS00) — 날짜: {target_date}")
    page.goto(f"{BASE}/template35.htm?template=DS00", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    clear_popups(page)

    # 날짜 설정 (start_date, end_date만 — start_date2/end_date2는 보조 필터)
    page.evaluate(
        f"""
        (() => {{
            const s = document.getElementById('start_date');
            const e = document.getElementById('end_date');
            if (s) s.value = '{target_date}';
            if (e) e.value = '{target_date}';
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
                            shop, date: dt, code, name, nameOpt,
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


def fetch_all_data(progress=None, sales_target_date=None):
    """전체 데이터 수집 오케스트레이션
    
    Args:
        progress: 진행 상황 콜백 함수
        sales_target_date: 매출 수집 타겟 날짜 (YYYY-MM-DD)
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
            orders = scrape_outbound(page, days=90, progress=progress)
            sales = scrape_sales(page, target_date=sales_target_date, progress=progress)

            if progress:
                progress("done")

            return {
                "inventory": inventory,
                "orders": orders,
                "sales": sales,
            }
        except Exception as e:
            log.error(f"데이터 수집 오류: {e}")
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
