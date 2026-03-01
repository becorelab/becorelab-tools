#!/usr/bin/env python3
"""
이지어드민 데이터 자동 수집 스크래퍼
- 로그인 + 보안코드 대기 + 재고현황/주문내역 수집
"""
import logging
import time
import os
import tempfile
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
    # 남은 팝업 닫기
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
    """검색(F2) 버튼 클릭 — span.flip 또는 텍스트 매칭"""
    page.evaluate(
        """
        (() => {
            // EzAdmin 검색 버튼은 span.flip
            const spans = document.querySelectorAll('span.flip');
            for (const s of spans) {
                if (s.textContent.trim() === '검색') { s.click(); return; }
            }
            // fallback
            const all = document.querySelectorAll('button, input[type="button"], input[type="submit"], a, span');
            for (const b of all) {
                const t = (b.textContent || b.value || '').trim();
                if (t.startsWith('검색') && b.offsetWidth > 0) { b.click(); return; }
            }
        })()
        """
    )


def scrape_inventory(page, progress=None):
    """재고현황 (I100) 페이지에서 상품코드 + 정상재고 수집"""
    if progress:
        progress("scraping_inventory")
    log.info("재고현황 페이지 이동 (I100)...")
    page.goto(f"{BASE}/template35.htm?template=I100", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    clear_popups(page)

    # 검색 실행
    click_search(page)
    page.wait_for_timeout(6000)
    clear_popups(page)

    # jqGrid 페이지 사이즈를 최대로
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
    page.wait_for_timeout(3000)

    # jqGrid — aria-describedby 기반 데이터 추출
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
    result = {}
    for item in inventory:
        result[item["code"]] = {"stock": item["stock"], "updated": today_str}
    return result


def scrape_orders(page, days=90, progress=None):
    """주문내역 (DS00) 페이지에서 발주일 + 상품코드 + 상품수량 수집"""
    if progress:
        progress("scraping_orders")
    log.info("주문내역 페이지 이동 (DS00)...")
    page.goto(f"{BASE}/template35.htm?template=DS00", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    clear_popups(page)

    # 검색 기간 설정: N일 전 ~ 오늘
    start_date = (date.today() - timedelta(days=days)).isoformat()
    end_date = date.today().isoformat()
    page.evaluate(
        f"""
        (() => {{
            const sd = document.getElementById('start_date') || document.querySelector('input[name="start_date"]');
            const ed = document.getElementById('end_date') || document.querySelector('input[name="end_date"]');
            if (sd) sd.value = '{start_date}';
            if (ed) ed.value = '{end_date}';
        }})()
        """
    )
    page.wait_for_timeout(500)

    # 검색 실행
    click_search(page)
    page.wait_for_timeout(8000)
    clear_popups(page)

    # jqGrid 페이지 사이즈 최대로
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
    page.wait_for_timeout(5000)

    # jqGrid — aria-describedby 기반 데이터 수집
    all_orders = []
    max_pages = 50

    for pg in range(max_pages):
        orders_page = page.evaluate(
            """
            (() => {
                const tbl = document.getElementById('grid1') || document.querySelector('.ui-jqgrid-btable');
                if (!tbl) return {error: 'no_grid'};
                const rows = [...tbl.querySelectorAll('tr')];
                const data = [];
                rows.forEach(tr => {
                    // aria-describedby 패턴으로 셀 찾기
                    const dateCell = tr.querySelector('td[aria-describedby$="_order_date"], td[aria-describedby$="_po_date"]');
                    const codeCell = tr.querySelector('td[aria-describedby$="_key"], td[aria-describedby$="_product_id"]');
                    const qtyCell = tr.querySelector('td[aria-describedby$="_product_qty"], td[aria-describedby$="_qty"]');
                    if (!dateCell || !qtyCell) return;
                    const rawDate = dateCell.textContent.trim();
                    const dateText = rawDate.substring(0, 10);
                    const code = codeCell ? codeCell.textContent.trim() : '';
                    const qty = parseInt(qtyCell.textContent.trim().replace(/,/g, '')) || 0;
                    if (dateText && dateText.length === 10 && qty > 0) {
                        data.push({date: dateText, code, qty});
                    }
                });
                return {data, total: rows.length};
            })()
            """
        )

        if isinstance(orders_page, dict) and orders_page.get("error"):
            log.warning(f"주문 테이블 파싱 실패 (page {pg+1}): {orders_page}")
            break

        if isinstance(orders_page, dict) and "data" in orders_page:
            all_orders.extend(orders_page["data"])
            if orders_page.get("total", 0) < 100:
                break
        else:
            break

        # jqGrid 다음 페이지
        has_next = page.evaluate(
            """
            (() => {
                const nextBtn = document.querySelector('.ui-pg-button [class*="end-e"]');
                if (!nextBtn) return false;
                const parent = nextBtn.closest('.ui-pg-button, td');
                if (parent) { parent.click(); return true; }
                return false;
            })()
            """
        )
        if not has_next:
            break
        page.wait_for_timeout(4000)
        clear_popups(page)

    log.info(f"주문 데이터 {len(all_orders)}건 수집")
    return all_orders


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
            orders = scrape_orders(page, days=90, progress=progress)

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
