#!/usr/bin/env python3
"""
이지어드민 데이터 자동 수집 스크래퍼
- 로그인 + 보안코드 대기 + 재고현황(I100) + 재고수불부(I500) 출고량 수집
"""
import logging
import time
import os
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
    """로그인 + 보안코드 대기"""
    log.info("이지어드민 로그인 중...")
    page.goto(EZADMIN["url"], timeout=30000)
    page.wait_for_timeout(3000)
    page.evaluate(
        f"document.getElementById('login-domain').value = '{EZADMIN['domain']}'"
    )
    page.evaluate(f"document.getElementById('login-id').value = '{EZADMIN['id']}'")
    page.evaluate(f"document.getElementById('login-pwd').value = '{EZADMIN['pw']}'")
    page.evaluate('document.querySelector(\'input[type="button"]\').click()')
    page.wait_for_timeout(6000)
    log.info("로그인 전송 완료 — 보안코드 대기...")
    return True


def wait_for_captcha(page, progress=None, timeout_sec=120):
    """보안코드 팝업이 사라질 때까지 대기 (사용자가 수동 입력)"""
    if progress:
        progress("captcha_wait")
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
    log.warning("보안코드 대기 시간 초과")
    return False


def clear_popups(page):
    """dim + 팝업 제거"""
    page.evaluate("document.querySelectorAll('.dim').forEach(el => el.remove())")
    page.wait_for_timeout(500)
    for _ in range(5):
        closed = page.evaluate(
            """
            (() => {
                const blocks = document.querySelectorAll('.blockUI.blockMsg');
                let closed = 0;
                blocks.forEach(b => {
                    if (b.offsetWidth > 0 && b.querySelector('#wrap') === null) {
                        const btn = b.querySelector('.close_btn, [class*="close"], button');
                        if (btn) { btn.click(); closed++; }
                    }
                });
                document.querySelectorAll('.dim').forEach(el => el.remove());
                return closed;
            })()
            """
        )
        if closed == 0:
            break
        page.wait_for_timeout(800)


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
                    const dateCell = tr.querySelector('td[aria-describedby="grid1_crdate"]');
                    const outCell = tr.querySelector('td[aria-describedby="grid1_stockout"]');
                    const shipCell = tr.querySelector('td[aria-describedby="grid1_trans"]');
                    if (!codeCell || !dateCell) return;
                    const code = codeCell.textContent.trim();
                    const d = dateCell.textContent.trim().substring(0, 10);
                    const outQty = outCell ? (parseInt(outCell.textContent.trim().replace(/,/g, '')) || 0) : 0;
                    const shipQty = shipCell ? (parseInt(shipCell.textContent.trim().replace(/,/g, '')) || 0) : 0;
                    const totalQty = outQty + shipQty;
                    if (code && code.length > 2 && d.length === 10 && totalQty > 0) {
                        data.push({code, date: d, qty: totalQty, out: outQty, ship: shipQty});
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

    # 상위 상품 요약
    product_totals = {}
    for r in result:
        product_totals[r["code"]] = product_totals.get(r["code"], 0) + r["qty"]
    top5 = sorted(product_totals.items(), key=lambda x: -x[1])[:5]
    for code, total in top5:
        log.info(f"  {code}: 총 {total}개 ({total/max(days,1):.1f}개/일)")

    return result


def fetch_all_data(progress=None):
    """전체 데이터 수집 오케스트레이션"""
    if progress:
        progress("starting")

    with sync_playwright() as p:
        browser, context, page = get_browser(p)
        try:
            if progress:
                progress("logging_in")
            ezadmin_login(page)
            wait_for_captcha(page, progress=progress, timeout_sec=120)
            clear_popups(page)

            inventory = scrape_inventory(page, progress=progress)
            orders = scrape_outbound(page, days=90, progress=progress)

            if progress:
                progress("done")

            return {
                "inventory": inventory,
                "orders": orders,
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
