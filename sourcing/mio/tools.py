"""
미오 커스텀 툴 — Playwright 기반 알리바바 자동화
Managed Agent가 호출 → 로컬에서 실행 → 결과 반환
"""

import sys
import os
import re
import json
import time
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from playwright.sync_api import sync_playwright
from alibaba_search import (
    _find_storefront_url,
    _send_alibaba_inquiry,
    CHROME_PORT,
)

CDP_URL = f"http://localhost:{CHROME_PORT}"


@contextmanager
def _cdp_page():
    """실제 Chrome CDP에 붙어서 새 탭 열기 → 봇 감지 우회"""
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        pw_page = ctx.new_page()
        try:
            yield pw_page
        finally:
            pw_page.close()


# ── 툴 1: 알리바바 키워드 검색 ─────────────────────────────────
def alibaba_search(keyword: str, page: int = 1, max_moq: int = None,
                   min_price: float = None, max_price: float = None) -> dict:
    """
    알리바바에서 키워드 검색 후 상품 목록 반환
    미오가 키워드/페이지/필터를 직접 결정
    """
    results = []
    with _cdp_page() as pw_page:
        try:
            url = f"https://www.alibaba.com/trade/search?SearchText={keyword}&page={page}"
            pw_page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)

            # product-detail 링크를 가진 카드 컨테이너 탐색
            cards = pw_page.query_selector_all('a[href*="product-detail"]')
            if not cards:
                cards = pw_page.query_selector_all('.list-no-v2-outter, [class*="offer-list"] > li, div[data-aplus-ae]')

            # product-detail 링크 방식: 각 카드가 이미 링크
            seen_urls = set()
            for card in cards[:40]:
                try:
                    href = card.get_attribute('href') or ''
                    if not href:
                        continue
                    if not href.startswith('http'):
                        href = 'https:' + href
                    # 중복 URL 제거
                    base_url = href.split('?')[0]
                    if base_url in seen_urls:
                        continue
                    seen_urls.add(base_url)

                    # 카드 텍스트는 부모 컨테이너에서
                    parent = card.evaluate_handle('el => el.closest("li, article, [class*=card], [class*=item], [class*=offer]") || el.parentElement')
                    text = parent.as_element().inner_text() if parent.as_element() else card.inner_text()

                    # 가격 파싱
                    price_match = re.search(
                        r'(?:US\s*)?\$\s*([\d,]+\.?\d*)\s*[-–]\s*(?:US\s*)?\$?\s*([\d,]+\.?\d*)'
                        r'|(?:US\s*)?\$\s*([\d,]+\.?\d+)',
                        text, re.IGNORECASE
                    )
                    price_min = price_max = None
                    if price_match:
                        if price_match.group(1):
                            price_min = float(price_match.group(1).replace(',', ''))
                            price_max = float(price_match.group(2).replace(',', ''))
                        elif price_match.group(3):
                            price_min = price_max = float(price_match.group(3).replace(',', ''))

                    # MOQ 파싱
                    moq_val = None
                    moq_match = re.search(r'(\d[\d,]*)\s*(?:pieces|pcs|sets|pairs|units)', text, re.IGNORECASE)
                    if moq_match:
                        moq_val = int(moq_match.group(1).replace(',', ''))

                    # 필터 적용
                    if max_moq and moq_val and moq_val > max_moq:
                        continue
                    if min_price and price_min and price_min < min_price:
                        continue
                    if max_price and price_max and price_max > max_price:
                        continue

                    # 제목 파싱
                    title = ''
                    for line in text.split('\n'):
                        line = line.strip()
                        if len(line) > 15 and '$' not in line and '₩' not in line:
                            title = line
                            break

                    # Gold Supplier 여부
                    is_gold = 'gold supplier' in text.lower() or 'verified' in text.lower()

                    results.append({
                        'title': title[:100],
                        'url': href,
                        'price_min': price_min,
                        'price_max': price_max,
                        'moq': moq_val,
                        'is_gold_supplier': is_gold,
                    })
                except Exception:
                    continue

        except Exception as e:
            return {'error': str(e), 'results': []}

    return {
        'keyword': keyword,
        'page': page,
        'total_found': len(results),
        'results': results
    }


# ── 툴 2: 상품 상세페이지 파싱 ─────────────────────────────────
def alibaba_get_detail(product_url: str) -> dict:
    """
    상품 상세페이지 HTML 전체를 Claude가 자연어로 파싱
    소재, MOQ, 인증, 중국어 스펙 모두 처리
    """
    with _cdp_page() as pw_page:
        try:
            pw_page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)

            sections = {}
            title_el = pw_page.query_selector('h1')
            sections['title'] = title_el.inner_text() if title_el else ''

            price_el = pw_page.query_selector('[class*="price"], [class*="Price"]')
            sections['price'] = price_el.inner_text() if price_el else ''

            spec_texts = []
            for el in pw_page.query_selector_all('table, [class*="detail"], [class*="spec"], [class*="attribute"]'):
                t = el.inner_text().strip()
                if t and len(t) > 10:
                    spec_texts.append(t[:500])
            sections['specs'] = '\n'.join(spec_texts[:5])

            supplier_el = pw_page.query_selector('[class*="supplier"], [class*="company"]')
            sections['supplier'] = supplier_el.inner_text()[:300] if supplier_el else ''

            body_text = pw_page.inner_text('body')
            sections['full_text'] = body_text[:3000]

            return {'url': product_url, 'data': sections}

        except Exception as e:
            return {'error': str(e), 'url': product_url}


# ── 툴 3: 공급업체 문의 발송 ───────────────────────────────────
def alibaba_send_inquiry(product_url: str, company: str, message: str) -> dict:
    """
    공급업체에 문의 메시지 발송
    미오가 메시지 내용 직접 작성
    """
    with _cdp_page() as pw_page:
        try:
            pw_page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)

            storefront_url = _find_storefront_url(pw_page, company, product_url)
            if not storefront_url:
                return {'success': False, 'error': 'storefront URL을 찾을 수 없음', 'company': company}

            success = _send_alibaba_inquiry(pw_page, company, storefront_url, message)
            return {
                'success': success,
                'company': company,
                'storefront_url': storefront_url,
            }

        except Exception as e:
            return {'success': False, 'error': str(e), 'company': company}


# ── 툴 디스패처 ────────────────────────────────────────────────
def dispatch_tool(tool_name: str, tool_input: dict) -> str:
    """미오의 custom_tool_use 이벤트를 받아 실행"""
    print(f"\n🔧 미오 툴 호출: {tool_name}")
    print(f"   입력: {json.dumps(tool_input, ensure_ascii=False)[:200]}")

    try:
        if tool_name == 'alibaba_search':
            result = alibaba_search(**tool_input)
        elif tool_name == 'alibaba_get_detail':
            result = alibaba_get_detail(**tool_input)
        elif tool_name == 'alibaba_send_inquiry':
            result = alibaba_send_inquiry(**tool_input)
        else:
            result = {'error': f'알 수 없는 툴: {tool_name}'}

        print(f"   결과: {str(result)[:200]}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        error = {'error': str(e)}
        print(f"   오류: {e}")
        return json.dumps(error, ensure_ascii=False)
