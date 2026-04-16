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
        elif tool_name == 'alibaba_check_inbox':
            result = alibaba_check_inbox(**tool_input)
        elif tool_name == 'alibaba_read_conversation':
            result = alibaba_read_conversation(**tool_input)
        elif tool_name == 'alibaba_reply':
            result = alibaba_reply(**tool_input)
        elif tool_name == 'escalate_to_user':
            result = escalate_to_user(**tool_input)
        else:
            result = {'error': f'알 수 없는 툴: {tool_name}'}

        print(f"   결과: {str(result)[:200]}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        error = {'error': str(e)}
        print(f"   오류: {e}")
        return json.dumps(error, ensure_ascii=False)
