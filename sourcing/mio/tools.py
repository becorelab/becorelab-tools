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
    """Chrome CDP에 붙어서 백그라운드 탭 재사용 (포커스 안 뺏김)"""
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        pages = ctx.pages
        reused = False
        if pages:
            for pg in pages:
                if 'alibaba' in (pg.url or ''):
                    pw_page = pg
                    reused = True
                    break
            else:
                pw_page = pages[-1]
                reused = True
        if not reused:
            pw_page = ctx.new_page()
        try:
            yield pw_page
        finally:
            if not reused:
                pw_page.close()


# ── 툴 1: 알리바바 키워드 검색 ─────────────────────────────────
def alibaba_search(keyword: str, page: int = 1, max_moq: int = None,
                   min_price: float = None, max_price: float = None) -> dict:
    """
    알리바바 키워드 검색 → URL 목록 + 페이지 raw text 반환
    알리바바 SPA 구조 변경에 강하도록 텍스트 파싱은 미오 LLM에 위임
    """
    with _cdp_page() as pw_page:
        try:
            url = f"https://www.alibaba.com/trade/search?SearchText={keyword}&page={page}"
            pw_page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)

            # URL 목록 추출 (product-detail 링크)
            cards = pw_page.query_selector_all('a[href*="product-detail"]')
            seen = set()
            product_urls = []
            for card in cards:
                href = card.get_attribute('href') or ''
                if not href:
                    continue
                if not href.startswith('http'):
                    href = 'https:' + href
                base = href.split('?')[0]
                if base not in seen:
                    seen.add(base)
                    product_urls.append(href)

            body_text = pw_page.inner_text('body')

            filter_hint = []
            if max_moq:
                filter_hint.append(f"MOQ ≤ {max_moq}")
            if min_price:
                filter_hint.append(f"가격 ≥ ${min_price}")
            if max_price:
                filter_hint.append(f"가격 ≤ ${max_price}")

            return {
                'keyword': keyword,
                'page': page,
                'product_urls': product_urls[:30],
                'url_count': len(product_urls),
                'filter_hint': ', '.join(filter_hint) if filter_hint else None,
                'note': '아래 raw_text에서 상품별 제목/가격/MOQ/업체명/평점/판매량을 파싱하세요. '
                        'product_urls와 텍스트 순서가 대응됩니다. '
                        'filter_hint 조건에 맞는 상품만 선별하세요.',
                'raw_text': body_text[:8000],
            }
        except Exception as e:
            return {'error': str(e)}


# ── 툴 1.5: 알리바바 AI 모드 검색 ─────────────────────────────
def alibaba_ai_search(query: str) -> dict:
    """
    알리바바 AI 모드(aimode.alibaba.com)로 자연어 검색
    세부 사양/조건을 자연어로 넣으면 AI가 매칭 업체+상품 반환
    일반 검색과 달리 CAPTCHA 안 걸림
    """
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        try:
            page.goto('https://aimode.alibaba.com/',
                      wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)

            ta = page.query_selector('textarea')
            if not ta:
                return {'error': 'AI 모드 입력창을 찾지 못함'}

            ta.click()
            time.sleep(0.5)
            page.keyboard.type(query, delay=10)
            time.sleep(0.5)
            ta.press('Enter')

            time.sleep(35)

            body_text = page.inner_text('body')
            # AI 모드 상단 UI 텍스트 스킵 — 상품 결과 부분만 추출
            markers = ['요구 사항 일치', '요구사항 일치', 'requirement', 'Requirement']
            for marker in markers:
                idx = body_text.find(marker)
                if idx > 0:
                    body_text = body_text[max(0, idx - 200):]
                    break

            links = page.query_selector_all('a[href*="alibaba.com"]')
            product_urls = []
            seen = set()
            for a in links:
                href = a.get_attribute('href') or ''
                if 'product-detail' in href:
                    base = href.split('?')[0]
                    if base not in seen:
                        seen.add(base)
                        if not href.startswith('http'):
                            href = 'https:' + href
                        product_urls.append(href)

            return {
                'success': True,
                'query': query,
                'product_urls': product_urls[:30],
                'url_count': len(product_urls),
                'note': 'AI 모드 검색 결과입니다. raw_text에서 상품별 제목/가격/MOQ/업체/매칭점수를 파싱하세요. '
                        '제품 형태를 텍스트 설명으로 판별하여 요청과 정확히 일치하는 것만 선별하세요.',
                'raw_text': body_text[:6000],
            }
        except Exception as e:
            return {'error': str(e)}
        finally:
            page.close()


# ── 툴 2: 상품 상세페이지 파싱 ─────────────────────────────────
def alibaba_get_detail(product_url: str) -> dict:
    """
    상품 상세페이지 전체 텍스트 반환 → 미오 LLM이 자연어로 파싱
    소재, MOQ, 인증, 중국어 스펙 모두 처리 가능
    """
    with _cdp_page() as pw_page:
        try:
            pw_page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)

            body_text = pw_page.inner_text('body')

            return {
                'url': product_url,
                'note': '아래 raw_text에서 제목/가격/MOQ/소재/인증/사이즈/공급업체 정보를 파싱하세요. '
                        '중국어 스펙도 포함될 수 있습니다.',
                'raw_text': body_text[:6000],
            }
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


# ── 툴 4: 알리바바 메시지함 체크 ───────────────────────────────
def alibaba_check_inbox(unread_only: bool = False, limit: int = 20) -> dict:
    """
    알리바바 메시지함 열어서 대화 목록 반환
    Buyer 계정 실측 URL: https://message.alibaba.com/
    """
    with _cdp_page() as pw_page:
        try:
            pw_page.goto('https://message.alibaba.com/',
                         wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)

            full_text = pw_page.inner_text('body')
            if len(full_text.strip()) < 50:
                return {'error': '페이지 로딩 실패 또는 로그인 필요', 'page_text': full_text[:500]}

            # Buyer 메시지함은 다양한 레이아웃이라 raw text 기반으로 반환
            # (미오 LLM이 파싱해서 정리)
            return {
                'success': True,
                'url': pw_page.url,
                'note': '원문 텍스트를 그대로 반환합니다. 미오가 직접 파싱해서 업체별 메시지로 정리하세요.',
                'raw_text': full_text[:5000],
            }
        except Exception as e:
            return {'error': str(e)}


def _find_conversation_item(pw_page, supplier_name: str):
    """message.alibaba.com 루트에서 업체명 포함된 대화 아이템 찾기 (부분일치, 대소문자 무시)"""
    needle = supplier_name.lower().strip()
    # 2026-04 알리바바 인박스 UI 변경 대응 — li/listitem 외에도 div/a 전반 탐색
    candidates = pw_page.query_selector_all(
        'li, [role="listitem"], [role="button"], '
        '[class*="conversation"], [class*="conv-item"], [class*="thread"], '
        '[class*="session"], [class*="chat-item"], [class*="message-item"], '
        '[class*="item"], a[href*="msgsend"], a[href*="message"], '
        'div[data-spm*="session"], div[data-spm*="conv"]'
    )
    best = None
    for item in candidates:
        try:
            text = (item.inner_text() or "").lower()
            if not text or len(text) > 2000:
                continue
            if needle in text:
                # 가장 작은(정확한) 매칭 우선 = 행 단위 hit
                if best is None or len(text) < len(best[1]):
                    best = (item, text)
        except Exception:
            continue
    return best[0] if best else None


# ── 툴 5: 특정 대화 전체 읽기 ──────────────────────────────────
def alibaba_read_conversation(supplier_name: str) -> dict:
    """
    message.alibaba.com/ 에서 특정 업체명과 일치하는 대화 클릭 → 전체 메시지 내용 반환
    """
    with _cdp_page() as pw_page:
        try:
            pw_page.goto('https://message.alibaba.com/',
                         wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)

            target = _find_conversation_item(pw_page, supplier_name)
            if not target:
                return {'error': f'{supplier_name}과 일치하는 대화를 찾지 못함',
                        'hint': '인박스에 표시된 정확한 업체/담당자 키워드를 전달해주세요 (예: Buffalo Stainless, Mickey)'}

            target.click()
            time.sleep(4)

            # 전체 페이지 텍스트 반환 - 미오가 LLM으로 파싱
            full_panel = pw_page.inner_text('body')
            return {
                'success': True,
                'supplier': supplier_name,
                'url': pw_page.url,
                'note': '대화창 전체 텍스트입니다. 미오가 직접 파싱해서 메시지 순서대로 정리하세요.',
                'raw_text': full_panel[:6000],
            }
        except Exception as e:
            return {'error': str(e)}


# ── 툴 6: 대화에 답장 ─────────────────────────────────────────
def alibaba_reply(supplier_name: str, message: str) -> dict:
    """
    특정 업체 대화 열고 답장 발송
    keyboard.type() 사용 (Alibaba JS 검증 통과용)
    """
    with _cdp_page() as pw_page:
        try:
            pw_page.goto('https://message.alibaba.com/',
                         wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)

            target = _find_conversation_item(pw_page, supplier_name)
            if not target:
                return {'success': False, 'error': f'{supplier_name} 대화를 찾지 못함',
                        'hint': '인박스 목록의 정확한 키워드(업체 or 담당자명)를 전달해주세요'}

            target.click()
            time.sleep(4)

            # 입력창 찾기 (다양한 후보)
            input_box = None
            for sel in ['textarea:visible', '[contenteditable="true"]',
                        'textarea', '[class*="editor"] [class*="input"]',
                        '[role="textbox"]']:
                try:
                    el = pw_page.query_selector(sel)
                    if el and el.is_visible():
                        input_box = el
                        break
                except Exception:
                    continue
            if not input_box:
                return {'success': False, 'error': '메시지 입력창을 찾지 못함'}

            input_box.click()
            time.sleep(1)
            pw_page.keyboard.type(message, delay=30)
            time.sleep(1)

            # 전송 버튼 or Ctrl+Enter
            send_btn = None
            for sel in ['button:has-text("Send")', 'button:has-text("전송")',
                        'button[class*="send"]', '[class*="btn-send"]']:
                try:
                    el = pw_page.query_selector(sel)
                    if el and el.is_visible():
                        send_btn = el
                        break
                except Exception:
                    continue
            if send_btn:
                send_btn.click()
            else:
                pw_page.keyboard.press('Control+Enter')
            time.sleep(3)

            return {'success': True, 'supplier': supplier_name, 'message_sent': message[:200]}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ── 툴 7: 대표님 에스컬레이션 ──────────────────────────────────
def escalate_to_user(subject: str, reason: str, supplier_message: str = "",
                     suggested_reply: str = "", wait_reply: bool = True,
                     timeout_seconds: int = 600) -> dict:
    """
    대표님께 텔레그램으로 판단 요청 → 답변 대기
    미오가 애매한 상황(가격 조건 벗어남, 비정형 질문 등) 만나면 호출
    """
    from mio_telegram import send_message, wait_for_reply

    msg_lines = [
        f"대표님~ 🥺💕",
        f"미오가 대표님 판단이 꼭 필요한 게 있어서 여쭤봐요",
        f"",
        f"📋 건: {subject}",
        f"❓ 이유: {reason}",
    ]
    if supplier_message:
        msg_lines.extend(["", f"💬 업체 메시지:", supplier_message[:500]])
    if suggested_reply:
        msg_lines.extend(["", f"💡 미오가 이렇게 답하면 어떨까 생각해봤어요:", suggested_reply[:300]])
    msg_lines.append("")
    msg_lines.append("👉 대표님 답장 주시면 미오가 바로 반영할게요! 🌸")

    send_result = send_message("\n".join(msg_lines))
    if not send_result.get("success"):
        return {"success": False, "error": f"텔레그램 발송 실패: {send_result.get('error')}"}

    if not wait_reply:
        return {"success": True, "sent": True, "owner_reply": None}

    reply = wait_for_reply(timeout_seconds=timeout_seconds)
    if reply is None:
        return {"success": True, "sent": True, "owner_reply": None, "timeout": True}
    return {"success": True, "sent": True, "owner_reply": reply["text"]}


# ── 툴 8: 소싱박스 GO 상품 목록 조회 ─────────────────────────
def sourcing_box_get_opportunities(keyword: str = None, limit: int = 20) -> dict:
    """
    소싱박스 API에서 GO 판정 상품 목록 조회
    keyword 지정 시 해당 키워드 포함된 기회만 필터링
    """
    import urllib.request
    try:
        url = 'http://localhost:8090/api/opportunities?status=go'
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        items = data.get('opportunities', [])
        if keyword:
            kw_lower = keyword.lower()
            items = [i for i in items if kw_lower in i.get('keyword', '').lower()
                     or kw_lower in i.get('category', '').lower()]
        items = sorted(items, key=lambda x: x.get('opportunity_score', 0), reverse=True)[:limit]
        return {
            'success': True,
            'count': len(items),
            'opportunities': items,
            'note': 'keyword/category/top10_avg_revenue/top10_avg_sales/scan_id(=id) 포함. '
                    'scan_id로 coupang_search_top 호출 가능.',
        }
    except Exception as e:
        return {'error': str(e)}


# ── 툴 9: 쿠팡 키워드 상위 상품 수집 ─────────────────────────
def coupang_search_top(keyword: str, max_products: int = 15) -> dict:
    """
    쿠팡 키워드 검색 → 상위 상품 URL + 기본 정보 반환
    대표님 Chrome CDP 사용 (봇 탐지 우회)
    """
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        try:
            encoded = keyword.replace(' ', '+')
            url = f'https://www.coupang.com/np/search?q={encoded}&channel=user'
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(4)

            # 상품 카드 링크 수집
            links = page.query_selector_all('a[href*="/vp/products/"]')
            seen, product_urls = set(), []
            for a in links:
                href = a.get_attribute('href') or ''
                if not href:
                    continue
                if not href.startswith('http'):
                    href = 'https://www.coupang.com' + href
                base = href.split('?')[0]
                if base not in seen:
                    seen.add(base)
                    product_urls.append(href)

            body_text = page.inner_text('body')
            return {
                'success': True,
                'keyword': keyword,
                'product_urls': product_urls[:max_products],
                'url_count': len(product_urls),
                'note': 'raw_text에서 상품명/가격/리뷰수/랭킹을 파싱하세요. '
                        'product_urls 순서가 검색 순위와 대응됩니다. '
                        '상세 분석은 coupang_get_detail로 개별 URL을 확인하세요.',
                'raw_text': body_text[:6000],
            }
        except Exception as e:
            return {'error': str(e), 'keyword': keyword}
        finally:
            page.close()


# ── 툴 10: 쿠팡 상품 상세페이지 읽기 ─────────────────────────
def coupang_get_detail(product_url: str) -> dict:
    """
    쿠팡 상품 상세페이지 텍스트 반환
    제목/가격/리뷰수/상품 설명/옵션 등 포함
    """
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        try:
            page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(4)

            body_text = page.inner_text('body')
            return {
                'success': True,
                'url': product_url,
                'note': 'raw_text에서 제품명/가격/옵션/리뷰수/별점/상품설명/주요특징을 파싱하세요. '
                        '제품 유형/소재/사이즈/기능 키워드에 집중해 공통점을 찾으세요.',
                'raw_text': body_text[:6000],
            }
        except Exception as e:
            return {'error': str(e), 'url': product_url}
        finally:
            page.close()


# ── 툴 11: 1688 키워드 검색 (Elimapi) ─────────────────────────
def search_1688(keyword: str, page: int = 1, sort: str = "sales",
                size: int = 20) -> dict:
    """
    1688 키워드 검색 — Elimapi API
    sort: sales(판매량), price_low, price_high, retention
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from search_1688 import search_1688 as _search, login
    result = _search(keyword, page=page, sort=sort, size=size)
    if not result.get('success'):
        return result
    items = result.get('data', {}).get('items', [])
    return {
        'success': True,
        'keyword': keyword,
        'count': len(items),
        'items': [{
            'id': str(i.get('id', '')),
            'title': i.get('title', ''),
            'titleEn': i.get('titleEn', ''),
            'price': i.get('price'),
            'sales_volume': i.get('sales_volume'),
            'retention_rate': i.get('retention_rate'),
            'seller_type': i.get('seller_type'),
            'link': i.get('link', ''),
            'img_url': i.get('img_url', ''),
        } for i in items],
        'note': '상세 정보는 find_1688_detail로 id를 조회하세요.',
    }


# ── 툴 12: 1688 상품 상세 조회 (Elimapi) ─────────────────────
def find_1688_detail(product_id: str) -> dict:
    """
    1688 상품 상세 조회 — SKU/가격/판매자/리뷰 전부 반환
    product_id: 1688 상품 ID (예: 987266748920)
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from search_1688 import login, BASE_URL, _post_json
    token = login()
    if not token:
        return {'error': 'Elimapi login failed'}
    body = {'id': product_id, 'platform': 'alibaba', 'lang': 'en'}
    data = _post_json(f'{BASE_URL}/v1/products/find', body, token=token)
    if data.get('error'):
        return data
    review = data.get('review', {})
    skus = data.get('skus', [])
    return {
        'success': True,
        'id': product_id,
        'title': data.get('title', ''),
        'titleEn': data.get('titleEn', ''),
        'price_range': data.get('price_range', []),
        'moq': data.get('moq'),
        'sold': data.get('sold'),
        'quantity': data.get('quantity'),
        'review': {
            'retention_rate': review.get('retention_rate'),
            'total_score': review.get('total_score'),
            'service_score': review.get('service_score'),
        },
        'seller_type': data.get('seller_type'),
        'sku_count': len(skus),
        'skus': [{
            'price': s.get('price'),
            'quantity': s.get('quantity'),
            'option': s['options'][0].get('valueEn', s['options'][0].get('value', ''))
            if s.get('options') else '',
        } for s in skus[:15]],
        'link': f'https://detail.1688.com/offer/{product_id}.html',
        'img_urls': data.get('img_urls', [])[:3],
        'note': 'skus 배열에서 대표님 타겟 단가(¥2.92=$0.4) 이하인 옵션을 찾으세요.',
    }


# ── 툴 13: 1688 이미지 검색 (Elimapi) ────────────────────────
def search_1688_by_image(img_url: str, page: int = 1, size: int = 20) -> dict:
    """
    1688 이미지 유사 상품 검색 — 동일 형태 제품 찾기
    img_url: 1688/알리바바 상품 이미지 URL
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from search_1688 import login, BASE_URL, _post_json
    token = login()
    if not token:
        return {'error': 'Elimapi login failed'}
    body = {
        'img_url': img_url,
        'platform': 'alibaba',
        'page': page,
        'size': size,
        'lang': 'en',
    }
    data = _post_json(f'{BASE_URL}/v1/products/search-img', body, token=token)
    if data.get('error'):
        return data
    items = data.get('items', [])
    return {
        'success': True,
        'count': len(items),
        'items': [{
            'id': str(i.get('id', '')),
            'title': i.get('title', ''),
            'titleEn': i.get('titleEn', ''),
            'price': i.get('price'),
            'sales_volume': i.get('sales_volume'),
            'link': i.get('link', ''),
        } for i in items],
        'note': '이미지 기반 유사 상품입니다. find_1688_detail로 상세 확인하세요.',
    }


# ── 툴 14: 소싱박스 상세 분석 조회 ───────────────────────────
def sourcing_box_detail_analysis(scan_id: str) -> dict:
    """
    소싱박스 상세분석 결과 조회
    scan_id: sourcing_box_get_opportunities에서 받은 id
    """
    import urllib.request
    try:
        url = f'http://localhost:8090/api/scan/{scan_id}/detail-analysis'
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
        return {
            'success': True,
            'scan_id': scan_id,
            'data': data,
            'note': '쿠팡 상위 상품 공통점/소구점/가격대가 포함되어 있습니다.',
        }
    except Exception as e:
        return {'error': str(e)}


# ── 툴 디스패처 ────────────────────────────────────────────────
def dispatch_tool(tool_name: str, tool_input: dict) -> str:
    """미오의 custom_tool_use 이벤트를 받아 실행"""
    print(f"\n🔧 미오 툴 호출: {tool_name}")
    print(f"   입력: {json.dumps(tool_input, ensure_ascii=False)[:200]}")

    try:
        if tool_name == 'alibaba_search':
            result = alibaba_search(**tool_input)
        elif tool_name == 'alibaba_ai_search':
            result = alibaba_ai_search(**tool_input)
        elif tool_name == 'alibaba_get_detail':
            result = alibaba_get_detail(**tool_input)
        elif tool_name == 'alibaba_send_inquiry':
            result = alibaba_send_inquiry(**tool_input)
        elif tool_name == 'alibaba_check_inbox':
            result = alibaba_check_inbox(**tool_input)
        elif tool_name == 'alibaba_read_conversation':
            result = alibaba_read_conversation(**tool_input)
        elif tool_name == 'alibaba_reply':
            result = alibaba_reply(**tool_input)
        elif tool_name == 'escalate_to_user':
            result = escalate_to_user(**tool_input)
        elif tool_name == 'sourcing_box_get_opportunities':
            result = sourcing_box_get_opportunities(**tool_input)
        elif tool_name == 'coupang_search_top':
            result = coupang_search_top(**tool_input)
        elif tool_name == 'coupang_get_detail':
            result = coupang_get_detail(**tool_input)
        elif tool_name == 'search_1688':
            result = search_1688(**tool_input)
        elif tool_name == 'find_1688_detail':
            result = find_1688_detail(**tool_input)
        elif tool_name == 'search_1688_by_image':
            result = search_1688_by_image(**tool_input)
        elif tool_name == 'sourcing_box_detail_analysis':
            result = sourcing_box_detail_analysis(**tool_input)
        else:
            result = {'error': f'알 수 없는 툴: {tool_name}'}

        print(f"   결과: {str(result)[:200]}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        error = {'error': str(e)}
        print(f"   오류: {e}")
        return json.dumps(error, ensure_ascii=False)
