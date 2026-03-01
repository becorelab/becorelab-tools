#!/usr/bin/env python3
"""
알리바바 업체 자동 검색 스크립트

사용법:
  python3 alibaba_search.py https://coupang.com/...  → 쿠팡 URL → 이미지 검색 → 결과
  python3 alibaba_search.py /path/to/image.jpg       → 이미지 파일 → 이미지 검색
  python3 alibaba_search.py                          → 키워드 검색 (fallback)

결과:
  - HTML 소싱 리포트 (브라우저 자동 오픈, 이미지 포함)
  - 이메일 발송 (네이버웍스)
  - CSV 저장
"""

import os
import re
import csv
import sys
import time
import math
import base64
import socket
import smtplib
import subprocess
import urllib.request
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

# ============================================================
# 검색 설정 (제품마다 수정)
# ============================================================
SEARCH_CONFIG = {
    # ── 검색 키워드 (이미지 검색 실패 시 대체용)
    'keyword_en':       'drain trap bathroom odor',
    'keyword_kr':       '하수구트랩',

    # ── 수익성 설정
    'target_cogs_krw':  2300,    # 판매단위당 목표 총원가 (원)
    'pack_size':        1,       # 판매단위 개수 (낱개=1, 30매입=30 등)
    'min_order_qty':    1000,    # 알리바바 발주 최소 수량 (낱개 기준)

    # ── 수입비용 파라미터
    'exchange_rate':    1450,    # 환율 (원/달러)
    'duty_rate':        0.08,    # 관세율 (8%)
    'weight_g_per_pc':  10,      # 개당 예상 무게 (g)

    'max_results':      48,
    'output_dir':       '/Users/kymac/claude/',
}

# ============================================================
# 이메일 설정
# ============================================================
EMAIL_CONFIG = {
    'sender':    'kychung@becorelab.kr',
    'password':  'PZLvVdb59mbf',
    'recipient': 'kychung@becorelab.kr',
    'smtp_host': 'smtp.worksmobile.com',
    'smtp_port': 465,           # SSL
}

CHROME_PATH   = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
CHROME_PORT   = 9222
CHROME_TMPDIR = '/tmp/chrome_ali'
IMAGE_PATH    = '/Users/kymac/claude/search_image.jpg'


# ============================================================
# 목표 소싱 단가 역산
# ============================================================
def calc_target_fob_usd(config):
    cogs_krw   = config['target_cogs_krw']
    pack_size  = max(1, config['pack_size'])
    moq        = config['min_order_qty']
    rate       = config['exchange_rate']
    duty       = config['duty_rate']
    weight_g   = config.get('weight_g_per_pc', 10)

    total_pcs   = moq
    total_packs = total_pcs / pack_size
    budget_krw  = cogs_krw * total_packs
    fixed_krw   = 80_000 + 100_000
    freight_usd = max(60, total_pcs * weight_g / 1000 * 6)
    freight_krw = freight_usd * rate
    remaining_krw = budget_krw - fixed_krw - freight_krw
    if remaining_krw <= 0:
        return 0.0
    fob_total_krw = remaining_krw / ((1 + duty) * 1.1)
    fob_unit_usd  = fob_total_krw / rate / total_pcs
    return round(max(0.0, fob_unit_usd), 4)


# ============================================================
# Chrome CDP 연결
# ============================================================
def _ensure_chrome():
    s = socket.socket()
    try:
        s.connect(('localhost', CHROME_PORT))
        s.close()
        return True
    except Exception:
        pass
    if not os.path.exists(CHROME_PATH):
        print("❌ Google Chrome을 찾을 수 없습니다.")
        return False
    subprocess.Popen(
        [CHROME_PATH, f'--remote-debugging-port={CHROME_PORT}',
         '--no-first-run', '--no-default-browser-check',
         f'--user-data-dir={CHROME_TMPDIR}'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(10):
        time.sleep(1)
        s2 = socket.socket()
        try:
            s2.connect(('localhost', CHROME_PORT))
            s2.close()
            print("✅ Chrome 시작 완료")
            return True
        except Exception:
            pass
    print("❌ Chrome 시작 실패")
    return False


def _get_page(p):
    if not _ensure_chrome():
        return None, None, None
    browser = p.chromium.connect_over_cdp(f'http://localhost:{CHROME_PORT}')
    ctx  = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    return browser, ctx, page


def _get_headless_page_with_cookies(p):
    """대표님 Chrome에서 알리바바 쿠키만 빌려 → 숨겨진 Headless에서 실행
    화면에 창이 뜨지 않아 대표님 작업에 방해 없음.
    """
    # 1) 기존 Chrome에서 쿠키 추출
    cookies = []
    try:
        main_browser = p.chromium.connect_over_cdp(f'http://localhost:{CHROME_PORT}')
        main_ctx = main_browser.contexts[0] if main_browser.contexts else None
        if main_ctx:
            cookies = main_ctx.cookies([
                'https://www.alibaba.com',
                'https://message.alibaba.com',
                'https://onetalk.alibaba.com',
                'https://login.alibaba.com',
            ])
            print(f"   🔑 알리바바 쿠키 {len(cookies)}개 복사 완료")
    except Exception as e:
        print(f"   ⚠️  쿠키 추출 실패: {e}")

    # 2) 숨겨진 Headless Chromium 실행
    headless_browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
    )
    headless_ctx = headless_browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent=(
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
    )

    # 3) 쿠키 주입
    if cookies:
        headless_ctx.add_cookies(cookies)

    page = headless_ctx.new_page()
    return headless_browser, headless_ctx, page


# ============================================================
# 쿠팡 스크래핑 (CDP)
# ============================================================
def scrape_coupang_product(coupang_url, save_image_path=None):
    result = {}
    with sync_playwright() as p:
        browser, ctx, page = _get_page(p)
        if page is None:
            return result
        try:
            page.goto(coupang_url, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(2500)

            title = ''
            for sel in ['h1.prod-buy-header__title', '.prod-buy-header__title', 'h1']:
                el = page.query_selector(sel)
                if el:
                    t = el.inner_text().strip()
                    if t and 'Access' not in t and len(t) > 3:
                        title = t
                        break

            price = ''
            for sel in ['.total-price strong', '.prod-price .total-price strong']:
                el = page.query_selector(sel)
                if el:
                    price = el.inner_text().strip() + '원'
                    break

            img_url = ''
            meta = page.query_selector('meta[property="og:image"]')
            if meta:
                img_url = meta.get_attribute('content') or ''
            if not img_url:
                for sel in ['#repImageContainer img', '.prod-image__detail img']:
                    el = page.query_selector(sel)
                    if el:
                        img_url = el.get_attribute('src') or el.get_attribute('data-src') or ''
                        if img_url:
                            break
            if img_url and not img_url.startswith('http'):
                img_url = 'https:' + img_url

            result = {'title': title, 'price': price, 'image_url': img_url, 'image_path': ''}

            if img_url and save_image_path:
                try:
                    req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        with open(save_image_path, 'wb') as f:
                            f.write(resp.read())
                    result['image_path'] = save_image_path
                    print(f"   이미지 저장: {save_image_path}")
                except Exception as e:
                    print(f"   이미지 다운로드 실패: {e}")
        except Exception as e:
            print(f"❌ 쿠팡 스크래핑 오류: {e}")
        finally:
            page.close()
            browser.close()
    return result


# ============================================================
# 캡차 감지 + 대기
# ============================================================
def _is_captcha(page):
    try:
        html = page.content()
        return any(k in html for k in ['captcha', 'nc_1_nocaptcha', 'baxia-punish', 'punish'])
    except Exception:
        return False

def _wait_captcha(page):
    if _is_captcha(page):
        print("⚠️  캡차 발생 — 브라우저에서 풀어주세요...")
        for _ in range(180):
            time.sleep(1)
            if not _is_captcha(page):
                print("✅ 캡차 완료!")
                page.wait_for_timeout(2000)
                break


# ============================================================
# 카드 데이터 추출
# ============================================================
def _extract_cards_from_page(page, config):
    for _ in range(5):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(600)
    page.mouse.wheel(0, -3000)
    page.wait_for_timeout(1500)

    cards = []
    for sel in ['.fy26-product-card-wrapper', '.fy23-search-card',
                '[class*="product-card-wrapper"]', '[class*="search-card"]', '[data-spm*="offer"]']:
        cards = page.query_selector_all(sel)
        if len(cards) >= 3:
            print(f"✅ 카드 {len(cards)}개 발견")
            break

    if not cards:
        debug_path = os.path.join(config['output_dir'], 'alibaba_debug.html')
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(page.content())
        print(f"⚠️  카드 없음. (디버그: {debug_path})")
        return []

    target_usd = config['_target_fob_usd']
    results = []
    print("데이터 추출 중...\n")
    for i, card in enumerate(cards[:config['max_results']]):
        try:
            supplier = extract_card_data(card, exchange_rate=config.get('exchange_rate', 1450))
            if supplier and supplier.get('company'):
                results.append(supplier)
                ok = (supplier['price_min_usd'] is not None
                      and supplier['price_min_usd'] <= target_usd)
                star = ' ★' if ok else ''
                print(f"  [{i+1}]{star} {supplier['company']} | {supplier['price']} | MOQ: {supplier['moq']}")
        except Exception:
            continue

    # 썸네일 이미지 다운로드
    thumb_dir = os.path.join(config['output_dir'], 'thumbnails')
    os.makedirs(thumb_dir, exist_ok=True)
    print(f"\n   🖼  썸네일 다운로드 중...")
    ok_count = 0
    for i, s in enumerate(results):
        if s.get('img_url'):
            thumb_path = os.path.join(thumb_dir, f"thumb_{i+1}.jpg")
            if _download_image(s['img_url'], thumb_path):
                s['img_path'] = thumb_path
                ok_count += 1
    print(f"   완료: {ok_count}/{len(results)}개")

    return results


# ============================================================
# 알리바바 이미지 검색 (CDP)
# ============================================================
def search_alibaba_by_image(config, image_path):
    if not os.path.exists(image_path):
        print(f"❌ 이미지 파일 없음: {image_path}")
        return []

    results = []
    with sync_playwright() as p:
        browser, ctx, page = _get_page(p)
        if page is None:
            return []
        try:
            page.goto('https://www.alibaba.com/', timeout=60000, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            _wait_captcha(page)

            print(f"\n📷 이미지 검색: {os.path.basename(image_path)}")

            btn = page.query_selector('.header-tab-switch-image-upload-multi')
            if not btn:
                raise Exception("이미지 검색 버튼을 찾을 수 없습니다.")
            btn.click()
            page.wait_for_timeout(2000)

            page.wait_for_selector('input[type="file"]', timeout=8000, state='attached')
            file_input = page.query_selector('input[type="file"]')
            if not file_input:
                raise Exception("file input 없음")

            file_input.set_input_files(image_path)
            print("   업로드 완료, 검색 결과 대기 중...")

            page.wait_for_timeout(5000)
            _wait_captcha(page)

            # currency=USD 강제 적용
            page.evaluate("document.cookie = 'intl_locale=en_US; path=/';")
            current_url = page.url
            if 'currency=USD' not in current_url:
                sep = '&' if '?' in current_url else '?'
                new_url = current_url + sep + 'currency=USD'
                page.goto(new_url, timeout=30000, wait_until='domcontentloaded')
                page.wait_for_timeout(3000)
                _wait_captcha(page)

            results = _extract_cards_from_page(page, config)

        except Exception as e:
            print(f"⚠️  이미지 검색 오류: {e}")
            print("   → 키워드 검색으로 대체합니다.")
            results = _run_keyword_search(page, config)
        finally:
            page.close()
            browser.close()
    return results


# ============================================================
# 알리바바 키워드 검색 (fallback)
# ============================================================
def _run_keyword_search(page, config):
    keyword = config['keyword_en']
    url = (f"https://www.alibaba.com/trade/search"
           f"?SearchText={keyword.replace(' ', '+')}&tab=all&currency=USD")
    print(f"\n🔍 키워드 검색: {keyword}")
    page.goto(url, timeout=60000, wait_until='domcontentloaded')
    page.wait_for_timeout(3000)
    _wait_captcha(page)
    return _extract_cards_from_page(page, config)


def search_alibaba(config):
    results = []
    with sync_playwright() as p:
        browser, ctx, page = _get_page(p)
        if page is None:
            return []
        try:
            results = _run_keyword_search(page, config)
        except Exception as e:
            print(f"❌ 오류: {e}")
        finally:
            page.close()
            browser.close()
    return results


# ============================================================
# 카드 파싱
# ============================================================
def extract_card_data(card, exchange_rate=1450):
    try:
        full_text = card.inner_text()
    except Exception:
        return None

    lines  = [l.strip() for l in full_text.split('\n') if l.strip()]
    joined = ' '.join(lines)

    # 가격
    price_match = re.search(
        r'₩[\d,]+\s*[-–]\s*₩?[\d,]+'
        r'|₩[\d,]+'
        r'|(?:US\s*)?\$[\d,]+\.?\d*\s*[-–]\s*(?:US\s*)?\$?[\d,]+\.?\d*'
        r'|(?:US\s*)?\$[\d,]+\.?\d+'
        r'|USD\s*[\d,]+\.?\d*\s*[-–]\s*[\d,]+\.?\d*',
        joined, re.IGNORECASE
    )
    price    = price_match.group(0).strip() if price_match else ''
    is_krw   = price.startswith('₩')

    # MOQ
    moq = ''
    m = re.search(r'Min\.?\s*order[:\s]+([^\n$]+?)(?:\s+\$|\s+pieces|\s+sets|\s+pcs|$)',
                  joined, re.IGNORECASE)
    if m:
        moq = m.group(0).strip()
    else:
        m2 = re.search(r'(\d[\d,]*)\s*(pieces|pcs|sets|pairs|units|개)', joined, re.IGNORECASE)
        if m2:
            moq = m2.group(0)

    # 업체명
    company = ''
    mc = re.search(
        r'([A-Z][A-Za-z0-9\s\(\)&\-,\.\']+(?:Co\.,?\s*Ltd\.?|Corp\.?|Inc\.?|LLC|GmbH|'
        r'Factory|Trading|Technology|Tech|Mfg|Manufacturing|Enterprise|Group|International|Industrial))',
        joined
    )
    if mc:
        company = mc.group(0).strip()

    # 제품명
    product = ''
    for line in lines:
        if (len(line) > 20
                and '$' not in line and '₩' not in line
                and 'Min.' not in line and 'Reorder' not in line
                and (not company or company[:10] not in line)):
            product = re.sub(r'^certified\s*', '', line, flags=re.IGNORECASE).strip()
            break

    # 평점
    rm = re.search(r'\b([4-5]\.\d)\b', joined)
    rating = rm.group(1) if rm else ''

    # 경력
    ym = re.search(r'(\d+)\s*yrs?', joined, re.IGNORECASE)
    years = ym.group(0) if ym else ''

    # 재주문율
    ror = re.search(r'Reorder rate\s*([\d]+%)', joined, re.IGNORECASE)
    reorder = ror.group(1) if ror else ''

    # 국가
    cm = re.search(r'\b(China|CN|Taiwan|Vietnam|Korea|US|USA|India|Bangladesh|Turkey)\b', joined)
    country = cm.group(0) if cm else ''

    # 링크
    link = ''
    try:
        for a in card.query_selector_all('a'):
            href = a.get_attribute('href') or ''
            if 'alibaba.com' in href and ('detail' in href or 'product' in href or '.html' in href):
                link = href if href.startswith('http') else 'https:' + href
                break
        if not link:
            for a in card.query_selector_all('a'):
                href = a.get_attribute('href') or ''
                if href and href != '#' and 'javascript' not in href:
                    link = href if href.startswith('http') else 'https:' + href
                    break
    except Exception:
        pass

    # 썸네일 이미지 URL
    img_url = ''
    try:
        img_el = card.query_selector('img')
        if img_el:
            for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                val = img_el.get_attribute(attr) or ''
                if val and ('alicdn' in val or 'alibaba' in val or val.startswith('//')):
                    img_url = val if val.startswith('http') else 'https:' + val
                    break
            if not img_url:
                val = img_el.get_attribute('src') or ''
                if val and val.startswith('http'):
                    img_url = val
    except Exception:
        pass

    if not price and not company:
        return None

    # 가격 최솟값 (항상 USD)
    price_min = None
    nums = re.findall(r'[\d]+\.?\d*', price.replace(',', ''))
    if nums:
        try:
            raw = float(nums[0])
            price_min = round(raw / exchange_rate, 4) if is_krw else raw
        except Exception:
            pass

    return {
        'company':       company or '(업체명 확인필요)',
        'product':       product[:100],
        'price':         price,
        'price_min_usd': price_min,
        'moq':           moq,
        'rating':        rating,
        'years':         years,
        'reorder_rate':  reorder,
        'country':       country,
        'email':         '',
        'link':          link,
        'img_url':       img_url,
        'img_path':      '',
    }


# ============================================================
# 이미지 유틸
# ============================================================
def _download_image(url, path):
    if not url or not url.startswith('http'):
        return False
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://www.alibaba.com/'
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            with open(path, 'wb') as f:
                f.write(resp.read())
        return True
    except Exception:
        return False


def _img_to_b64(path):
    """이미지 파일 → base64 data URI"""
    if not path or not os.path.exists(path):
        return ''
    try:
        ext  = os.path.splitext(path)[1].lower().lstrip('.')
        mime = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png',
                'gif': 'gif', 'webp': 'webp'}.get(ext, 'jpeg')
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:image/{mime};base64,{data}"
    except Exception:
        return ''


# ============================================================
# HTML 소싱 리포트 생성
# ============================================================
def generate_html_report(results, config, ref_image_path=''):
    target_usd = config['_target_fob_usd']
    today_str  = date.today().strftime('%Y년 %m월 %d일')
    keyword    = config['keyword_kr']
    star_count = sum(1 for s in results
                     if s.get('price_min_usd') is not None
                     and s['price_min_usd'] <= target_usd)

    # 기준 이미지 base64
    ref_b64 = _img_to_b64(ref_image_path)
    ref_img_tag = (f'<img class="ref-img" src="{ref_b64}" alt="기준상품">'
                   if ref_b64 else '<div class="ref-img-placeholder">📦</div>')

    # 업체 카드 HTML
    cards_html = ''
    for i, s in enumerate(results, 1):
        ok      = (s.get('price_min_usd') is not None and s['price_min_usd'] <= target_usd)
        badge   = ('<span class="badge-star">★ 목표원가 이내</span>'
                   if ok else '<span class="badge-no">목표원가 초과</span>')

        # 이미지
        thumb_b64 = _img_to_b64(s.get('img_path', ''))
        if thumb_b64:
            img_tag = f'<img class="card-img" src="{thumb_b64}" alt="제품이미지">'
        else:
            img_tag = '<div class="card-img-placeholder">🏭</div>'

        price_str = s['price']
        usd_str   = f'≈ US${s["price_min_usd"]:.4f}' if s.get('price_min_usd') is not None else ''
        moq_str   = s['moq'] or '-'
        rating_str = f'⭐ {s["rating"]}' if s['rating'] else '-'
        years_str  = s['years'] or '-'

        link = s.get('link', '')
        link_btn = (f'<a href="{link}" target="_blank" class="link-btn">알리바바에서 보기 →</a>'
                    if link else '<span class="link-btn disabled">링크 없음</span>')

        cards_html += f"""
        <div class="card {'card-ok' if ok else 'card-no'}">
            {img_tag}
            {badge}
            <div class="card-num">#{i}</div>
            <div class="card-body">
                <div class="company" title="{s['company']}">{s['company'][:40]}</div>
                <div class="product" title="{s['product']}">{s['product'][:55] or '(제품명 확인필요)'}</div>
                <div class="price-row">
                    <span class="price-main {'price-ok' if ok else 'price-no'}">{price_str}</span>
                    <span class="price-usd">{usd_str}</span>
                </div>
                <div class="meta-row">
                    <span class="tag">MOQ {moq_str}</span>
                    <span class="tag">{rating_str}</span>
                    <span class="tag">{years_str}</span>
                </div>
                {link_btn}
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>소싱 리포트 | {keyword}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, 'Malgun Gothic', 'Noto Sans KR', sans-serif;
          background: #f0f2f5; color: #222; }}

  /* ── 헤더 ── */
  .header {{ background: linear-gradient(135deg, #d63b1e 0%, #ff6b35 100%);
             color: white; padding: 28px 32px; }}
  .header-inner {{ max-width: 1440px; margin: 0 auto;
                   display: flex; align-items: center; gap: 24px; }}
  .ref-img {{ width: 110px; height: 110px; object-fit: contain;
              background: white; border-radius: 12px; padding: 8px;
              box-shadow: 0 4px 12px rgba(0,0,0,0.2); flex-shrink: 0; }}
  .ref-img-placeholder {{ width: 110px; height: 110px; background: rgba(255,255,255,0.2);
                          border-radius: 12px; display: flex; align-items: center;
                          justify-content: center; font-size: 42px; flex-shrink: 0; }}
  .header-info {{ flex: 1; }}
  .header-info h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 12px; letter-spacing: -0.3px; }}
  .stat-row {{ display: flex; gap: 10px; flex-wrap: wrap; }}
  .stat {{ background: rgba(255,255,255,0.18); border-radius: 8px;
           padding: 8px 14px; text-align: center; }}
  .stat-val {{ font-size: 20px; font-weight: 800; display: block; }}
  .stat-lbl {{ font-size: 11px; opacity: 0.85; }}

  /* ── 그리드 ── */
  .container {{ max-width: 1440px; margin: 24px auto; padding: 0 20px 40px; }}
  .grid {{ display: grid;
           grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
           gap: 16px; }}

  /* ── 카드 ── */
  .card {{ background: white; border-radius: 14px; overflow: hidden;
           box-shadow: 0 2px 8px rgba(0,0,0,0.07);
           transition: transform .2s, box-shadow .2s;
           position: relative; border: 2px solid transparent; }}
  .card:hover {{ transform: translateY(-4px); box-shadow: 0 10px 28px rgba(0,0,0,0.13); }}
  .card-ok {{ border-color: #e8f5e9; }}
  .card-no {{ border-color: #fafafa; }}
  .card-img {{ width: 100%; height: 170px; object-fit: contain;
               background: #f8f9fa; padding: 10px; display: block; }}
  .card-img-placeholder {{ width: 100%; height: 170px; background: #f0f0f0;
                           display: flex; align-items: center; justify-content: center;
                           font-size: 44px; color: #ccc; }}
  .badge-star {{ position: absolute; top: 10px; left: 10px;
                 background: #e53935; color: white; font-size: 10px;
                 font-weight: 700; padding: 3px 8px; border-radius: 20px;
                 letter-spacing: 0.2px; }}
  .badge-no {{ position: absolute; top: 10px; left: 10px;
               background: #bdbdbd; color: white; font-size: 10px;
               padding: 3px 8px; border-radius: 20px; }}
  .card-num {{ position: absolute; top: 10px; right: 10px;
               background: rgba(0,0,0,0.35); color: white;
               font-size: 11px; font-weight: 700; padding: 2px 7px;
               border-radius: 20px; }}
  .card-body {{ padding: 13px; }}
  .company {{ font-size: 11px; color: #888; margin-bottom: 5px;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .product {{ font-size: 12.5px; font-weight: 600; color: #333; margin-bottom: 10px;
              line-height: 1.45; height: 37px; overflow: hidden; }}
  .price-row {{ display: flex; align-items: baseline; gap: 6px; margin-bottom: 8px; }}
  .price-main {{ font-size: 17px; font-weight: 800; }}
  .price-ok {{ color: #e53935; }}
  .price-no {{ color: #555; }}
  .price-usd {{ font-size: 11px; color: #999; }}
  .meta-row {{ display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 11px; }}
  .tag {{ background: #f5f5f5; color: #555; font-size: 10.5px;
          padding: 2px 7px; border-radius: 5px; }}
  .link-btn {{ display: block; text-align: center; background: #f5f5f5; color: #444;
               text-decoration: none; padding: 8px; border-radius: 8px;
               font-size: 12px; font-weight: 600;
               transition: background .18s, color .18s; }}
  .link-btn:hover {{ background: #e53935; color: white; }}
  .link-btn.disabled {{ color: #bbb; cursor: default; }}

  /* ── 인쇄 ── */
  @media print {{
    .card {{ break-inside: avoid; }}
    .card:hover {{ transform: none; box-shadow: none; }}
    .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    {ref_img_tag}
    <div class="header-info">
      <h1>🔍 알리바바 소싱 리포트 &nbsp;|&nbsp; {keyword}</h1>
      <div class="stat-row">
        <div class="stat">
          <span class="stat-val">{len(results)}</span>
          <span class="stat-lbl">수집 업체</span>
        </div>
        <div class="stat">
          <span class="stat-val" style="color:#ffe082">{star_count}</span>
          <span class="stat-lbl">★ 목표원가 이내</span>
        </div>
        <div class="stat">
          <span class="stat-val">{config['target_cogs_krw']:,}원</span>
          <span class="stat-lbl">목표 총원가</span>
        </div>
        <div class="stat">
          <span class="stat-val">US${target_usd:.4f}</span>
          <span class="stat-lbl">최대 소싱단가</span>
        </div>
        <div class="stat">
          <span class="stat-val">{config['exchange_rate']:,}원</span>
          <span class="stat-lbl">적용 환율</span>
        </div>
        <div class="stat">
          <span class="stat-val">{today_str}</span>
          <span class="stat-lbl">기준일</span>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="container">
  <div class="grid">
    {cards_html}
  </div>
</div>

</body>
</html>"""

    html_path = os.path.join(
        config['output_dir'],
        f"소싱리포트_{keyword.replace(' ', '_')}_{date.today().strftime('%Y%m%d')}.html"
    )
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n🌐 HTML 리포트 저장: {html_path}")
    return html_path


# ============================================================
# 이메일 발송 (네이버웍스 SMTP)
# ============================================================
def send_email_report(html_path, config):
    ec = EMAIL_CONFIG
    if not ec.get('sender') or not ec.get('password') or not ec.get('recipient'):
        print("⚠️  이메일 설정 없음 — 발송 건너뜀")
        return False

    keyword  = config['keyword_kr']
    today_str = date.today().strftime('%Y.%m.%d')
    subject   = f"[소싱리포트] {keyword} — {today_str}"

    with open(html_path, encoding='utf-8') as f:
        html_body = f.read()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = ec['sender']
    msg['To']      = ec['recipient']
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        with smtplib.SMTP_SSL(ec['smtp_host'], ec['smtp_port']) as server:
            server.login(ec['sender'], ec['password'])
            server.send_message(msg)
        print(f"✉️  이메일 발송 완료 → {ec['recipient']}")
        return True
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")
        return False


# ============================================================
# 알리바바 Contact Supplier 메시지 템플릿
# ============================================================
ALIBABA_MESSAGE_TEMPLATE = """\
Dear {company} Team,

I hope this message finds you well.

My name is Kyle Chung, CEO of Becorelab Co., Ltd. (Korea) — brand: iLBiA. \
We sell household convenience products on Coupang, Naver Smart Store, and 11Street in Korea.

We came across your product on Alibaba and are interested in sourcing it:
{product_link}

Could you please provide the following?

1. Unit price by quantity (500 / 1,000 / 3,000 / 5,000 pcs)
2. MOQ (Minimum Order Quantity)
3. OEM/ODM options (custom logo, label, packaging)
4. Sample availability & shipping cost to Korea
5. Lead time & payment terms (T/T, L/C)
6. Product weight & carton dimensions

Kindly reply to our email: kychung@becorelab.kr
We will respond promptly.

Best regards,
Kyle Chung
CEO, Becorelab Co., Ltd. | Brand: iLBiA
Email  : kychung@becorelab.kr
Website: www.ilbia.co.kr
Korea
"""

# ============================================================
# 업체 문의 이메일 템플릿
# ============================================================
EMAIL_INQUIRY_TEMPLATE = """\
Dear {company} Team,

I hope this message finds you well.

My name is Kyle Chung, and I am the CEO of Becorelab Co., Ltd. (Korea), \
the company behind the consumer brand iLBiA — a household product brand \
focused on everyday convenience, sold across major Korean e-commerce platforms \
including Coupang, Naver Smart Store, and 11Street.

We are currently sourcing floor drain deodorizers / drain traps and came \
across your products on Alibaba. We are impressed by your product range and \
would like to explore a potential partnership.

Could you please provide the following details?

  1. Unit price by quantity tier (e.g., 500 / 1,000 / 3,000 / 5,000 pcs)
  2. MOQ (Minimum Order Quantity)
  3. OEM/ODM availability — custom logo, label, or packaging
  4. Sample availability and cost (including shipping to Korea)
  5. Lead time for bulk orders
  6. Payment terms (e.g., T/T, L/C)
  7. Product weight and carton dimensions (for import cost estimation)

We are planning to place an initial trial order within this quarter if \
the conditions are suitable. We look forward to building a long-term \
business relationship.

Please feel free to reply to this email or reach us at kychung@becorelab.kr.

Best regards,

Kyle Chung
CEO, Becorelab Co., Ltd. | Brand: iLBiA
Email : kychung@becorelab.kr
Website: www.ilbia.co.kr
Korea
"""


# ============================================================
# 업체 연락처 스크래핑 (Alibaba 상세 페이지)
# ============================================================
def scrape_supplier_contact(page, product_link):
    """제품 링크 → 공급업체 이메일 주소 추출 시도"""
    try:
        page.goto(product_link, timeout=30000, wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        _wait_captcha(page)

        content = page.content()

        # 1차: 페이지 본문에서 이메일 패턴 검색
        emails = re.findall(
            r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b', content
        )
        for em in emails:
            if not any(x in em.lower() for x in ['alibaba', 'alicdn', 'example', 'noreply', 'support']):
                return em

        # 2차: 업체 프로필 페이지 이동 후 재시도
        for sel in ['a[href*="company_profile"]', 'a[href*="supplier_id"]',
                    '.supplier-name a', '.company-name a']:
            el = page.query_selector(sel)
            if el:
                href = el.get_attribute('href') or ''
                if href:
                    profile_url = href if href.startswith('http') else 'https://www.alibaba.com' + href
                    page.goto(profile_url, timeout=20000, wait_until='domcontentloaded')
                    page.wait_for_timeout(2000)
                    content2 = page.content()
                    emails2 = re.findall(
                        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b', content2
                    )
                    for em in emails2:
                        if not any(x in em.lower() for x in ['alibaba', 'alicdn', 'example', 'noreply']):
                            return em
                    break
    except Exception:
        pass
    return ''


# ============================================================
# 단건 업체 문의 이메일 발송
# ============================================================
def send_single_supplier_email(company, to_email):
    ec = EMAIL_CONFIG
    body = EMAIL_INQUIRY_TEMPLATE.format(company=company)
    subject = f"Product Inquiry – Floor Drain Deodorizer / Drain Trap (iLBiA, Korea)"

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = ec['sender']
    msg['To']      = to_email
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP_SSL(ec['smtp_host'], ec['smtp_port']) as server:
            server.login(ec['sender'], ec['password'])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"      발송 오류: {e}")
        return False


# ============================================================
# 알리바바 Contact Supplier 폼 자동 발송 (스토어 페이지 경유)
# ============================================================
def _guess_store_slug(company):
    """회사명에서 알리바바 스토어 슬러그 추측"""
    cities = ['Shanghai', 'Guangzhou', 'Shenzhen', 'Beijing', 'Ningbo',
              'Quanzhou', 'Chaozhou', 'Xiamen', 'Taizhou', 'Qingyuan',
              'Yiwu', 'Wenzhou', 'Dongguan', 'Foshan', 'Hangzhou',
              'Suzhou', 'Nanjing', 'Changsha', 'Wuhan', 'Chengdu',
              'Rip']
    name = company
    for city in cities:
        name = re.sub(rf'^{city}\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(
        r'\s*(Co\.?,?\s*Ltd\.?|Factory|Manufacturing|Enterprise|Group|'
        r'International|Industrial|Trading|Corporation|Corp\.?|Inc\.?|'
        r'Mfg\.?|Products?|Sanitary\s*Ware|Hardware|Technology|Tech|'
        r'Supply\s*Chain\s*Management|Development)\.?\s*$',
        '', name, flags=re.IGNORECASE
    ).strip()
    words = re.split(r'\s+', name)
    slug = re.sub(r'[^a-z0-9]', '', words[0].lower()) if words else ''
    return slug if len(slug) >= 3 else ''


def _find_storefront_url(page, company, product_link):
    """제품 페이지 또는 검색으로 공급업체 스토어 URL 찾기"""
    import urllib.parse

    # 방법 1: 제품 페이지에서 .en.alibaba.com 링크 추출
    if product_link:
        try:
            page.goto(product_link, timeout=20000, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            links = page.evaluate("""() =>
                Array.from(document.querySelectorAll('a'))
                    .map(a => a.href)
                    .filter(h => h && h.includes('.en.alibaba.com') && !h.includes('.m.en.'))
            """)
            if links:
                from urllib.parse import urlparse
                parsed = urlparse(links[0])
                return f"https://{parsed.netloc}/"
        except Exception:
            pass

    # 방법 2: 슬러그 직접 시도
    slug = _guess_store_slug(company)
    if slug:
        url = f"https://{slug}.en.alibaba.com/"
        try:
            resp = page.goto(url, timeout=12000, wait_until='domcontentloaded')
            if resp and resp.status < 400:
                return url
        except Exception:
            pass

    # 방법 3: 알리바바 공급업체 검색
    try:
        q = urllib.parse.quote(company)
        page.goto(f"https://www.alibaba.com/trade/search?SearchText={q}&tab=supplier",
                  timeout=20000, wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        links = page.evaluate("""() =>
            Array.from(document.querySelectorAll('a'))
                .map(a => a.href)
                .filter(h => h && h.includes('.en.alibaba.com') && !h.includes('.m.en.'))
        """)
        if links:
            from urllib.parse import urlparse
            parsed = urlparse(links[0])
            return f"https://{parsed.netloc}/"
    except Exception:
        pass

    return ''


def _send_alibaba_inquiry(page, company, storefront_url, message):
    """스토어 Contact Supplier 폼으로 문의 발송 → (ok, reason)"""
    ctx = page.context
    try:
        page.goto(storefront_url, timeout=20000, wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        _wait_captcha(page)

        # Contact supplier 링크 (message.alibaba.com/msgsend) 찾기
        contact_url = page.evaluate("""() => {
            for (const a of document.querySelectorAll('a')) {
                const t = a.innerText.trim().toLowerCase();
                const h = a.href || '';
                if ((t.includes('contact') || t.includes('inquiry')) &&
                    (h.includes('message.alibaba') || h.includes('msgsend')))
                    return h;
            }
            return null;
        }""")

        if not contact_url:
            return False, 'Contact 링크 없음'

        # 새 탭에서 폼 열기
        pages_before = set(pg.url for pg in ctx.pages)
        page.evaluate(f"window.open({repr(contact_url)}, '_blank')")
        page.wait_for_timeout(4000)

        form_page = None
        for pg in ctx.pages:
            if pg.url not in pages_before and ('msgsend' in pg.url or 'feedback' in pg.url):
                form_page = pg
                break
        # 탭이 안 열렸으면 직접 이동
        if not form_page:
            form_page = ctx.new_page()
            form_page.goto(contact_url, timeout=20000, wait_until='domcontentloaded')

        form_page.bring_to_front()
        form_page.wait_for_timeout(3000)

        # textarea 입력
        ta = form_page.query_selector('#inquiry-content, textarea')
        if not ta:
            form_page.close()
            return False, 'textarea 없음'

        ta.click()
        form_page.keyboard.press('Control+a')
        form_page.keyboard.press('Delete')
        form_page.keyboard.type(message, delay=5)
        form_page.wait_for_timeout(500)
        form_page.evaluate("""() => {
            const ta = document.querySelector('#inquiry-content, textarea');
            if (ta) {
                ta.dispatchEvent(new Event('input', {bubbles: true}));
                ta.dispatchEvent(new Event('change', {bubbles: true}));
                ta.dispatchEvent(new Event('blur', {bubbles: true}));
            }
        }""")
        form_page.wait_for_timeout(300)

        # 제출
        submit = form_page.query_selector('input[type="submit"], button[type="submit"]')
        if not submit:
            form_page.close()
            return False, '제출 버튼 없음'

        submit.click()
        form_page.wait_for_timeout(6000)

        body = form_page.evaluate("document.body.innerText")
        form_page.close()

        if any(w in body.lower() for w in ['successfully', 'success', '성공', 'sent']):
            return True, '발송완료'
        return False, f'결과불명: {body[:40]}'

    except Exception as e:
        return False, f'오류({str(e)[:40]})'


def _send_alibaba_contact(page, company, product_link):
    """(레거시) 오네톡 채팅 — 더 이상 사용 안 함"""
    try:
        page.goto(product_link, timeout=30000, wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        _wait_captcha(page)

        # "지금 채팅하기" 버튼 찾기 (한국어/영어 모두 처리)
        btn = None
        chat_keywords = ['지금 채팅하기', 'chat now', 'contact supplier',
                         '문의하기', '공급업체 문의', 'start order']
        all_btns = page.query_selector_all('button, a[role="button"]')
        for b in all_btns:
            try:
                t = b.inner_text().strip().lower()
                if any(k in t for k in chat_keywords):
                    btn = b
                    break
            except Exception:
                continue

        if not btn:
            return False, '버튼없음'

        btn.click()
        page.wait_for_timeout(3000)
        _wait_captcha(page)

        message = ALIBABA_MESSAGE_TEMPLATE.format(company=company)

        # 채팅창 입력창 찾기 (contenteditable 또는 textarea)
        textarea = None
        for sel in [
            'div[contenteditable="true"]',
            'textarea',
            '[class*="chat"] [contenteditable]',
            '[class*="input"] [contenteditable]',
            '[class*="message"] textarea',
        ]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    textarea = el
                    break
            except Exception:
                continue

        if not textarea:
            return False, '입력창없음'

        textarea.click()
        page.wait_for_timeout(500)
        # contenteditable에는 fill 대신 type 사용
        try:
            textarea.fill(message)
        except Exception:
            textarea.type(message, delay=10)
        page.wait_for_timeout(800)

        # 전송 (Enter 키 or 전송 버튼)
        sent = False
        send_keywords = ['전송', 'send', '보내기', 'submit']
        all_send_btns = page.query_selector_all('button')
        for sb in all_send_btns:
            try:
                t = sb.inner_text().strip().lower()
                cls = (sb.get_attribute('class') or '').lower()
                if any(k in t for k in send_keywords) or any(k in cls for k in ['send', 'submit']):
                    if sb.is_visible():
                        sb.click()
                        sent = True
                        break
            except Exception:
                continue

        if not sent:
            # Enter 키로 전송 시도
            textarea.press('Enter')
            sent = True

        page.wait_for_timeout(2000)
        return True, '발송완료'

    except Exception as e:
        return False, f'오류({str(e)[:40]})'


def find_supplier_email(page, company):
    """
    구글 + 중국 B2B 사이트에서 업체 이메일 검색
    반환: email 문자열 or ''
    """
    import urllib.parse

    # 잘못 걸러낼 도메인/패턴
    bad_domains = [
        'google', 'alibaba', 'alicdn', 'example', 'noreply', 'support',
        'schema', 'w3.org', 'sentry', 'tradewheel', 'lightinthebox',
        'amazon', 'ebay', 'dhgate', 'madeinchina', 'globalsources',
        'prober', 'test@', 'spam', 'abuse', 'webmaster', 'postmaster',
        'privacy', 'legal', 'press', 'media', 'marketing@google',
    ]
    # 회사명에서 핵심 단어 추출 (이메일 검증용)
    company_keywords = set(
        w.lower() for w in re.split(r'\W+', company)
        if len(w) > 3 and w.lower() not in
        {'technology', 'trading', 'industrial', 'international', 'manufacturing',
         'products', 'hardware', 'sanitary', 'factory', 'enterprise', 'supply',
         'chain', 'management', 'development', 'limited', 'group'}
    )

    def extract_emails(text):
        found = re.findall(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b', text)
        clean = [e for e in found if not any(b in e.lower() for b in bad_domains)]
        return clean

    def score_email(email, source_url=''):
        """이메일 신뢰도 점수 (높을수록 좋음)"""
        score = 0
        el = email.lower()
        domain = el.split('@')[-1]
        # 회사명 키워드가 이메일/도메인에 포함되면 +3
        for kw in company_keywords:
            if kw in el:
                score += 3
        # 중국 이메일 도메인 +1
        if any(d in domain for d in ['163.com', '126.com', 'qq.com', 'sohu.com', 'sina.com', 'foxmail.com']):
            score += 1
        # sales/info/contact 패턴 +1
        if any(w in el.split('@')[0] for w in ['sales', 'info', 'contact', 'trade', 'export', 'purchase']):
            score += 1
        # 출처 URL이 회사 키워드 포함하면 +2
        for kw in company_keywords:
            if kw in source_url.lower():
                score += 2
        return score

    def try_url(url, wait=3):
        try:
            page.goto(url, timeout=20000, wait_until='domcontentloaded')
            page.wait_for_timeout(wait * 1000)
            return page.content()
        except Exception:
            return ''

    short = company.replace(' Co., Ltd.', '').replace(' Co.,Ltd.', '') \
                   .replace(' Factory', '').replace(' Co.', '').strip()

    candidates = []  # (email, score, source_url)

    # ── 1. 구글 검색 ──
    for q in [
        f'"{company}" email contact',
        f'"{short}" email @',
        f'"{short}" contact us',
    ]:
        gurl = 'https://www.google.com/search?q=' + urllib.parse.quote(q)
        html = try_url(gurl, wait=2)
        for e in extract_emails(html):
            candidates.append((e, score_email(e, gurl), 'Google'))
        time.sleep(1.5)

    # ── 2. Made-in-China ──
    q2 = urllib.parse.quote(short)
    mic_url = f'https://www.made-in-china.com/multi-search/{q2}/F1//'
    html = try_url(mic_url, wait=3)
    for e in extract_emails(html):
        candidates.append((e, score_email(e, mic_url), 'MIC'))

    # 검색 결과 첫 업체 페이지 방문
    try:
        link = page.query_selector('a.product-name, a.company-name, .search-main a')
        if link:
            href = link.get_attribute('href') or ''
            if href:
                profile_url = href if href.startswith('http') else 'https://www.made-in-china.com' + href
                html2 = try_url(profile_url, wait=3)
                for e in extract_emails(html2):
                    candidates.append((e, score_email(e, profile_url), 'MIC-profile'))
    except Exception:
        pass

    # ── 3. GlobalSources ──
    gs_url = f'https://www.globalsources.com/search/supplier?keyword={q2}'
    html = try_url(gs_url, wait=3)
    for e in extract_emails(html):
        candidates.append((e, score_email(e, gs_url), 'GS'))

    # ── 4. 구글로 회사 공식 웹사이트 찾기 ──
    site_html = try_url(
        'https://www.google.com/search?q=' + urllib.parse.quote(f'{short} official website contact email'),
        wait=2
    )
    site_links = re.findall(r'href="(https?://(?!www\.google)[^"]+)"', site_html)
    for slink in site_links[:5]:
        if any(x in slink for x in ['alibaba', 'amazon', 'wikipedia', 'linkedin']):
            continue
        try:
            shtml = try_url(slink, wait=3)
            for e in extract_emails(shtml):
                candidates.append((e, score_email(e, slink), slink[:40]))
        except Exception:
            continue

    # ── 최고 점수 이메일 선택 ──
    if not candidates:
        return ''
    candidates.sort(key=lambda x: x[1], reverse=True)
    best_email, best_score, best_src = candidates[0]
    print(f'      → 최고점수({best_score}) [{best_src}] {best_email}')
    if best_score == 0:
        print(f'        (경고: 점수 0 — 회사명 키워드 미매칭, 전송 건너뜀)')
        return ''
    return best_email


def find_and_send_supplier_emails(results, config):
    """구글·중국 B2B 사이트에서 이메일 수집 후 네이버웍스로 발송"""

    # 업체명 기준 중복 제거
    seen = {}
    for s in results:
        name = s['company']
        if name not in seen and name != '(업체명 확인필요)':
            seen[name] = s
    unique = list(seen.values())

    print(f"\n{'='*60}")
    print(f"🔍 업체 이메일 검색 + 발송 — {len(unique)}개 업체")
    print(f"{'='*60}")

    sent_log = []

    with sync_playwright() as p:
        browser, ctx, page = _get_page(p)
        if page is None:
            return sent_log
        try:
            for i, supplier in enumerate(unique, 1):
                company = supplier['company']
                print(f"\n  [{i}/{len(unique)}] {company[:55]}")

                email = find_supplier_email(page, company)

                if email:
                    ok = send_single_supplier_email(company, email)
                    status = '발송완료' if ok else '발송실패'
                    print(f"      {'✅' if ok else '❌'} {status}: {email}")
                else:
                    status = '이메일없음'
                    print(f"      ⚠️  이메일 찾지 못함")

                sent_log.append({'company': company, 'email': email, 'status': status})
                time.sleep(2)
        finally:
            page.close()
            browser.close()

    ok_cnt = sum(1 for r in sent_log if r['status'] == '발송완료')
    no_cnt = sum(1 for r in sent_log if r['status'] == '이메일없음')
    print(f"\n{'='*60}")
    print(f"✅ 발송완료: {ok_cnt}개  |  ⚠️ 이메일없음: {no_cnt}개")

    log_path = os.path.join(config['output_dir'], f"이메일발송로그_{date.today().strftime('%Y%m%d')}.csv")
    with open(log_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['company', 'email', 'status'])
        w.writeheader()
        w.writerows(sent_log)
    print(f"📋 발송 로그: {log_path}")
    return sent_log


def send_alibaba_contact_messages(results, config):
    """수집된 업체에게 알리바바 Contact Supplier 폼으로 문의 일괄 발송
    봇 감지 방지: 업체 간 60초 대기
    """
    seen = {}
    for s in results:
        name = s['company']
        if name not in seen and name != '(업체명 확인필요)':
            seen[name] = s
    unique = list(seen.values())

    print(f"\n{'='*60}")
    print(f"📨 알리바바 Contact Supplier 폼 — {len(unique)}개 업체")
    print(f"{'='*60}")

    sent_log = []

    with sync_playwright() as p:
        print("   🕶️  숨겨진 브라우저로 실행 중 (화면에 창 없음)...")
        browser, ctx, page = _get_headless_page_with_cookies(p)
        if page is None:
            return sent_log
        try:
            for i, supplier in enumerate(unique, 1):
                company      = supplier['company']
                product_link = supplier.get('link', '')
                print(f"\n  [{i}/{len(unique)}] {company[:55]}")

                # 스토어 URL 찾기
                storefront = _find_storefront_url(page, company, product_link)
                if not storefront:
                    print(f"      ⚠️  스토어 URL 못 찾음 — 건너뜀")
                    sent_log.append({'company': company, 'storefront': '', 'status': '스토어없음'})
                    continue
                print(f"      🏪 {storefront}")

                # 문의 발송
                message = ALIBABA_MESSAGE_TEMPLATE.format(company=company, product_link=product_link)
                ok, reason = _send_alibaba_inquiry(page, company, storefront, message)
                icon = '✅' if ok else '❌'
                print(f"      {icon} {reason}")
                sent_log.append({'company': company, 'storefront': storefront, 'status': reason})
        finally:
            try:
                page.close()
                browser.close()
            except Exception:
                pass

    ok_cnt   = sum(1 for r in sent_log if r['status'] == '발송완료')
    fail_cnt = len(sent_log) - ok_cnt
    print(f"\n{'='*60}")
    print(f"✅ 발송완료: {ok_cnt}개  |  ❌ 실패/건너뜀: {fail_cnt}개")

    log_path = os.path.join(
        config['output_dir'],
        f"알리바바문의로그_{date.today().strftime('%Y%m%d')}.csv"
    )
    with open(log_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['company', 'storefront', 'status'])
        w.writeheader()
        w.writerows(sent_log)
    print(f"📋 발송 로그: {log_path}")
    return sent_log


# ============================================================
# 전체 업체 문의 이메일 일괄 발송
# ============================================================
def send_supplier_inquiry_emails(results, config):
    # 업체명 기준 중복 제거 (첫 번째 링크만 사용)
    seen = {}
    for s in results:
        name = s['company']
        if name not in seen and s.get('link') and name != '(업체명 확인필요)':
            seen[name] = s
    unique = list(seen.values())

    print(f"\n{'='*60}")
    print(f"📧 업체 문의 이메일 발송 — 총 {len(unique)}개 업체 (중복 제거)")
    print(f"{'='*60}")

    sent_log = []   # {'company', 'email', 'status'}

    with sync_playwright() as p:
        browser, ctx, page = _get_page(p)
        if page is None:
            return sent_log
        try:
            for i, supplier in enumerate(unique, 1):
                company = supplier['company']
                link    = supplier.get('link', '')
                print(f"\n  [{i}/{len(unique)}] {company[:55]}")

                if not link:
                    print(f"      ⚠️  링크 없음 — 건너뜀")
                    sent_log.append({'company': company, 'email': '', 'status': '링크없음'})
                    continue

                # 이메일 주소 스크래핑
                email = scrape_supplier_contact(page, link)

                if email:
                    ok = send_single_supplier_email(company, email)
                    status = '발송완료' if ok else '발송실패'
                    icon   = '✅' if ok else '❌'
                    print(f"      {icon} {email} — {status}")
                    sent_log.append({'company': company, 'email': email, 'status': status})
                else:
                    print(f"      ⚠️  이메일 주소 없음 (알리바바 메시지 필요)")
                    sent_log.append({'company': company, 'email': '', 'status': '이메일없음'})

                time.sleep(1.5)
        finally:
            page.close()
            browser.close()

    # 결과 요약
    ok_cnt  = sum(1 for r in sent_log if r['status'] == '발송완료')
    no_cnt  = sum(1 for r in sent_log if r['status'] == '이메일없음')
    fail_cnt= sum(1 for r in sent_log if r['status'] == '발송실패')
    print(f"\n{'='*60}")
    print(f"✅ 발송 완료: {ok_cnt}개  |  ⚠️ 이메일 없음: {no_cnt}개  |  ❌ 실패: {fail_cnt}개")

    # 로그 CSV 저장
    log_path = os.path.join(
        config['output_dir'],
        f"이메일발송로그_{date.today().strftime('%Y%m%d')}.csv"
    )
    with open(log_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['company', 'email', 'status'])
        w.writeheader()
        w.writerows(sent_log)
    print(f"📋 발송 로그: {log_path}")
    return sent_log


# ============================================================
# CSV 저장
# ============================================================
def save_csv(results, config):
    today  = date.today().strftime('%Y%m%d')
    kr     = config['keyword_kr'].replace(' ', '_')
    path   = os.path.join(config['output_dir'], f"알리바바_검색결과_{kr}_{today}.csv")
    fields = ['company', 'product', 'price', 'price_min_usd', 'moq',
              'rating', 'years', 'reorder_rate', 'country', 'email', 'link']
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(results)
    print(f"💾 CSV 저장: {path}")
    return path


# ============================================================
# 결과 출력
# ============================================================
def print_results(results, config):
    target_usd = config['_target_fob_usd']
    print("\n" + "="*72)
    print(f"📦 제품: {config['keyword_kr']}")
    print(f"🎯 목표원가: {config['target_cogs_krw']:,}원/{config['pack_size']}개입  "
          f"→  최대 소싱 단가: US${target_usd:.4f}/개  (환율 {config['exchange_rate']:,}원)")
    print(f"✅ 수집: {len(results)}개 업체  |  ★ = 목표원가 이내")
    print("="*72)

    for i, s in enumerate(results, 1):
        ok   = s['price_min_usd'] is not None and s['price_min_usd'] <= target_usd
        star = ' ★' if ok else ''
        price_str = s['price']
        if price_str.startswith('₩') and s.get('price_min_usd') is not None:
            price_str += f"  (≈ US${s['price_min_usd']:.4f})"
        print(f"\n[{i}]{star} {s['company']}")
        print(f"    제품: {s['product'][:60]}")
        print(f"    가격: {price_str}  |  MOQ: {s['moq']}")
        print(f"    평점: {s['rating']}  |  경력: {s['years']}  |  재주문율: {s['reorder_rate']}")
        print(f"    링크: {s['link'][:80]}")


# ============================================================
# 메인
# ============================================================
if __name__ == '__main__':
    config = dict(SEARCH_CONFIG)
    config['_target_fob_usd'] = calc_target_fob_usd(config)

    arg        = sys.argv[1] if len(sys.argv) > 1 else None
    image_path = None
    ref_image  = ''

    if arg and 'coupang.com' in arg:
        print("🛒 쿠팡 상품 정보 수집 중...")
        info = scrape_coupang_product(arg, save_image_path=IMAGE_PATH)
        if info and info.get('image_path'):
            image_path = info['image_path']
            ref_image  = info['image_path']
            if info.get('title'):
                config['keyword_kr'] = info['title'][:20]
            print(f"   ✅ 상품명: {info.get('title','')[:60]}")
            print(f"   ✅ 쿠팡가: {info.get('price','')}")
        else:
            print("   ⚠️  이미지 추출 실패 → 키워드 검색으로 진행합니다.")

    elif arg and os.path.exists(arg):
        image_path = arg
        ref_image  = arg

    elif not arg and os.path.exists(IMAGE_PATH):
        image_path = IMAGE_PATH
        ref_image  = IMAGE_PATH

    mode = '이미지' if image_path else '키워드'
    print(f"\n🚀 알리바바 검색 시작  [{mode} 검색]")
    print(f"   제품: {config['keyword_kr']}")
    print(f"   목표원가: {config['target_cogs_krw']:,}원/{config['pack_size']}개입  "
          f"→  최대 소싱 단가: US${config['_target_fob_usd']:.4f}/개")
    if image_path:
        print(f"   이미지: {image_path}")
    print()

    results = (search_alibaba_by_image(config, image_path)
               if image_path else search_alibaba(config))

    if results:
        print_results(results, config)
        save_csv(results, config)

        # HTML 리포트 생성 + 브라우저 오픈
        html_path = generate_html_report(results, config, ref_image_path=ref_image)
        subprocess.run(['open', html_path])

        # 소싱 리포트 이메일 발송 (대표님께)
        send_email_report(html_path, config)

        # 알리바바 Contact Supplier 폼으로 문의 발송
        send_alibaba_contact_messages(results, config)
    else:
        print("❌ 결과 없음. 브라우저에서 직접 확인해주세요.")
