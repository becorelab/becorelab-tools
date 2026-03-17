"""
헬프스토어 + 확장 프로그램 자동화 (Sync Playwright)
1. Playwright에 헬프스토어 확장 로드
2. 쿠팡윙 로그인 (확장이 윙 API 호출하려면 필요)
3. 헬프스토어 로그인
4. 쿠팡 분석 페이지에서 키워드 검색 → DOM 파싱
"""

import os
import logging
import threading
import queue
import glob

logger = logging.getLogger(__name__)

WING_BASE = 'https://wing.coupang.com'
WING_ID = 'becorelab'
WING_PW = 'becolab@2026'
HELPSTORE_BASE = 'https://helpstore.shop'
HELPSTORE_ID = 'becorelab'
HELPSTORE_PW = 'qlzhdjfoq2023!!'
COUPANG_PAGE = f'{HELPSTORE_BASE}/keyword/keyword_analyze_coupang/'

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.wing_profile')

# 헬프스토어 확장 프로그램 경로 찾기
def _find_extension():
    ext_base = os.path.join(
        os.environ.get('LOCALAPPDATA', ''),
        'Google', 'Chrome', 'User Data', 'Default', 'Extensions',
        'nfbjgieajobfohijlkaaplipbiofblef'
    )
    if os.path.isdir(ext_base):
        versions = sorted(os.listdir(ext_base), reverse=True)
        for v in versions:
            p = os.path.join(ext_base, v)
            if os.path.isdir(p) and os.path.exists(os.path.join(p, 'manifest.json')):
                return p
    return ''


# ─── 워커 스레드 ───
_task_queue = queue.Queue()
_worker = None
_pw = None
_ctx = None
_page = None
_logged_in = False
_wing_ok = False


def _worker_loop():
    global _pw, _ctx, _page, _logged_in, _wing_ok
    while True:
        task = _task_queue.get()
        if task is None:
            break
        action, args, event, holder = task
        try:
            if action == 'login':
                holder['result'] = _do_full_login()
            elif action == 'search':
                holder['result'] = _do_search(args['keyword'])
            elif action == 'status':
                holder['result'] = {'logged_in': _logged_in, 'wing_ok': _wing_ok, 'has_browser': _ctx is not None}
            elif action == 'debug_html':
                holder['result'] = _debug_first_li()
            elif action == 'goldbox_crawl':
                print(f'[WORKER] goldbox_crawl 시작')
                holder['result'] = _do_goldbox_crawl(args.get('url', ''))
                print(f'[WORKER] goldbox_crawl 완료: {len(holder["result"])}개')
            elif action == 'collect_reviews':
                holder['result'] = _do_collect_reviews(args.get('product_url', ''), args.get('max_reviews', 30))
            elif action == 'coupang_keywords':
                holder['result'] = _do_coupang_keywords(args.get('keyword', ''))
        except Exception as e:
            import traceback
            print(f'[WORKER] 에러: {action} — {e}')
            traceback.print_exc()
            holder['error'] = str(e)
        finally:
            event.set()


def _ensure_worker():
    global _worker
    if _worker and _worker.is_alive():
        return
    _worker = threading.Thread(target=_worker_loop, daemon=True)
    _worker.start()


def _send(action, args=None, timeout=600):
    _ensure_worker()
    event = threading.Event()
    holder = {}
    _task_queue.put((action, args or {}, event, holder))
    completed = event.wait(timeout=timeout)
    if not completed:
        print(f'[WING] 타임아웃: {action} ({timeout}초)')
        raise Exception(f'{action} 타임아웃 ({timeout}초)')
    if 'error' in holder:
        raise Exception(holder['error'])
    return holder.get('result')


# ─── 브라우저 작업 (워커 스레드에서만) ───
def _start_browser():
    global _pw, _ctx, _page
    if _ctx:
        return

    from playwright.sync_api import sync_playwright
    os.makedirs(STATE_DIR, exist_ok=True)

    ext_path = _find_extension()
    logger.info(f'확장 프로그램: {ext_path or "없음"}')

    launch_args = ['--disable-blink-features=AutomationControlled']
    if ext_path:
        launch_args.extend([
            f'--load-extension={ext_path}',
            f'--disable-extensions-except={ext_path}',
        ])

    # Docker/서버 환경에서는 headless 모드 사용
    is_server = os.environ.get('DOCKER_ENV') == '1' or not os.environ.get('DISPLAY', os.name == 'nt' and 'yes' or '')
    use_headless = is_server and not ext_path

    _pw = sync_playwright().start()
    _ctx = _pw.chromium.launch_persistent_context(
        user_data_dir=STATE_DIR,
        headless=use_headless,
        viewport={'width': 1200, 'height': 800},
        args=launch_args,
    )
    _page = _ctx.pages[0] if _ctx.pages else _ctx.new_page()
    logger.info('브라우저 시작 완료')


def _do_full_login():
    """윙 로그인 → 헬프스토어 로그인 → 준비 완료"""
    global _logged_in, _wing_ok

    _start_browser()

    # 1) 쿠팡윙 로그인
    logger.info('쿠팡윙 로그인 시도...')
    _page.goto(WING_BASE, wait_until='domcontentloaded', timeout=20000)
    _page.wait_for_timeout(3000)

    url = _page.url
    if '/login' in url or 'xauth' in url or 'login.coupang.com' in url:
        try:
            _page.locator('input[name="username"], input[name="email"], input[type="text"]').first.fill(WING_ID)
            _page.wait_for_timeout(300)
            _page.locator('input[name="password"], input[type="password"]').first.fill(WING_PW)
            _page.wait_for_timeout(300)
            _page.locator('button[type="submit"], input[type="submit"], #kc-login').first.click()
            _page.wait_for_url('**/wing.coupang.com/**', timeout=30000)
            _page.wait_for_timeout(2000)
            _wing_ok = True
            logger.info('쿠팡윙 로그인 성공!')
        except Exception as e:
            logger.warning(f'윙 자동 로그인 실패: {e}')
            # 수동 대기
            for i in range(120):
                _page.wait_for_timeout(1000)
                if 'wing.coupang.com' in _page.url and '/login' not in _page.url:
                    _wing_ok = True
                    break
    else:
        _wing_ok = True
        logger.info('쿠팡윙 이미 로그인됨')

    if not _wing_ok:
        return {'success': False, 'message': '쿠팡윙 로그인 실패'}

    # 2) 헬프스토어 로그인
    logger.info('헬프스토어 로그인 시도...')
    _page.goto(f'{HELPSTORE_BASE}/login', wait_until='domcontentloaded', timeout=15000)
    _page.wait_for_timeout(2000)

    url = _page.url
    if '/login' in url:
        try:
            _page.locator('#loginId').fill(HELPSTORE_ID)
            _page.wait_for_timeout(300)
            _page.locator('#loginPw').fill(HELPSTORE_PW)
            _page.wait_for_timeout(300)
            _page.locator('#btnLogin').click()
            _page.wait_for_timeout(3000)
            logger.info('헬프스토어 로그인 성공!')
        except Exception as e:
            logger.warning(f'헬프스토어 로그인 실패: {e}')

    # 3) 쿠팡 분석 페이지로 이동
    _page.goto(COUPANG_PAGE, wait_until='domcontentloaded', timeout=15000)
    _page.wait_for_timeout(2000)

    _logged_in = True
    # 브라우저 최소화
    _page.evaluate('window.resizeTo(1,1); window.moveTo(-2000,-2000)')

    return {'success': True, 'message': '로그인 완료! (윙 + 헬프스토어)'}


def _do_search(keyword):
    """헬프스토어 쿠팡 분석 페이지에서 검색 → DOM 파싱"""
    global _logged_in
    from analyzer.helpstore import CoupangProduct

    if not _ctx:
        _start_browser()
    if not _logged_in:
        # 자동 로그인 시도
        result = _do_full_login()
        if not result.get('success'):
            raise Exception('WING_LOGIN_REQUIRED')

    # 쿠팡 분석 페이지 확인
    if 'keyword_analyze_coupang' not in _page.url:
        _page.goto(COUPANG_PAGE, wait_until='domcontentloaded', timeout=15000)
        _page.wait_for_timeout(2000)

    # extension/page로 리다이렉트 되면 확장 미감지
    if '/extension/page' in _page.url:
        raise Exception('헬프스토어 확장 프로그램이 감지되지 않습니다')

    # 키워드 입력 + 검색
    search_input = _page.locator('#keyword')
    search_input.fill('')
    search_input.type(keyword, delay=30)
    _page.wait_for_timeout(300)
    _page.locator('#btnSearch').click()

    # 결과 로딩 대기 (확장이 윙 API 호출 → DOM 렌더)
    try:
        _page.wait_for_selector(
            '.keyword_analyze_coupang .listProducts li',
            timeout=45000
        )
        logger.info(f'상품 리스트 로딩 완료: {keyword}')
    except:
        # 상품이 없을 수 있음 — 페이지 상태 확인
        logger.warning(f'상품 로딩 타임아웃: {keyword}')
        # extension/page 리다이렉트 확인
        if '/extension/page' in _page.url:
            raise Exception('확장 프로그램 또는 쿠팡윙 로그인 문제')
        return []

    # 윙 데이터(판매량/매출) 로딩 대기 — dl.type2 안에 판매량 데이터가 채워질 때까지
    try:
        _page.wait_for_selector(
            '.keyword_analyze_coupang .listProducts li dl.type2 dd',
            timeout=30000
        )
        logger.info('판매량 데이터 로딩 감지')
    except:
        logger.warning('판매량 데이터 로딩 타임아웃 — 기본 데이터만 사용')

    _page.wait_for_timeout(5000)  # 모든 상품 데이터 안정화 대기

    # DOM에서 상품 데이터 파싱
    # type1: 가격, 리뷰(점수)
    # type2: 노출증가, 클릭수, 클릭율, 광고비중
    products_data = _page.evaluate('''() => {
        function parseNum(s) {
            if (!s) return 0;
            // "4,147(4.5)" → 4147, "500~1,000(100.0%)" → 500, "9,900원" → 9900
            const m = s.replace(/,/g, '').match(/^([0-9]+)/);
            return m ? parseInt(m[1]) : 0;
        }
        function parseFloat2(s) {
            if (!s) return 0;
            const m = s.match(/([0-9.]+)/);
            return m ? parseFloat(m[1]) : 0;
        }

        const products = [];
        document.querySelectorAll('.keyword_analyze_coupang .listProducts li').forEach((li, i) => {
            const p = { ranking: i + 1, price: 0, reviews: 0, clicks: 0, sales: 0, cvr: 0, revenue: 0, adWeight: 0, ctr: 0 };

            // 상품명 + URL
            const a = li.querySelector('strong a');
            if (a) { p.name = a.innerText.trim(); p.url = a.href || ''; }

            // 카테고리
            const sp = li.querySelector(':scope > span');
            if (sp) p.category = sp.innerText.trim();

            // type1: 가격, 리뷰
            const dl1 = li.querySelector('dl.type1');
            if (dl1) {
                let dt = '';
                for (const c of dl1.children) {
                    if (c.tagName === 'DT') dt = c.innerText.trim();
                    else if (c.tagName === 'DD') {
                        const raw = c.innerText.trim();
                        if (dt === '가격') p.price = parseNum(raw);
                        else if (dt === '리뷰') p.reviews = parseNum(raw);
                        else if (dt === '브랜드') p.brand = raw;
                        else if (dt === '제조사') p.manufacturer = raw;
                        else if (dt === '판매량') p.sales = parseNum(raw);
                        else if (dt.includes('판매금액')) p.revenue = parseNum(raw);
                        else if (dt === '클릭수') p.clicks = parseNum(raw);
                        else if (dt === '전환율') p.cvr = parseFloat2(raw);
                        dt = '';
                    }
                }
            }

            // type2: 노출증가, 클릭수, 클릭율, 광고비중
            const dl2 = li.querySelector('dl.type2');
            if (dl2) {
                let dt = '';
                for (const c of dl2.children) {
                    if (c.tagName === 'DT') dt = c.innerText.trim();
                    else if (c.tagName === 'DD') {
                        const raw = c.innerText.trim();
                        if (dt === '클릭수') p.clicks = parseNum(raw);
                        else if (dt === '클릭율') p.ctr = parseFloat2(raw);
                        else if (dt === '광고비중') p.adWeight = parseFloat2(raw);
                        else if (dt === '판매량') p.sales = parseNum(raw);
                        else if (dt.includes('판매금액')) p.revenue = parseNum(raw);
                        else if (dt === '전환율') p.cvr = parseFloat2(raw);
                        else if (dt === '리뷰') p.reviews = parseNum(raw);
                        dt = '';
                    }
                }
            }

            // 카테고리 코드
            const kwBtn = li.querySelector('.btnShowKeyword');
            if (kwBtn) p.categoryCode = kwBtn.getAttribute('data-category-id') || '';

            products.push(p);
        });
        return products;
    }''')

    # CoupangProduct 변환 — 판매량 데이터가 있는 상품만 (랭킹순 40개)
    # 상위 노출 상품 (노출증가/광고비중만 있는 것)은 제외
    products = []
    rank = 0
    for rp in products_data:
        # 판매량 또는 매출 데이터가 없으면 상위 노출 상품 → 스킵
        if rp.get('sales', 0) == 0 and rp.get('revenue', 0) == 0:
            continue
        rank += 1
        sales = rp.get('sales', 0)
        price = rp.get('price', 0)
        revenue = rp.get('revenue', 0)
        if revenue == 0 and sales > 0 and price > 0:
            revenue = sales * price

        products.append(CoupangProduct(
            ranking=rank,
            product_name=rp.get('name', ''),
            brand=rp.get('brand', ''),
            manufacturer=rp.get('manufacturer', ''),
            price=price, sales_monthly=sales, revenue_monthly=revenue,
            review_count=rp.get('reviews', 0),
            click_count=rp.get('clicks', 0),
            conversion_rate=rp.get('cvr', 0),
            page_views=rp.get('clicks', 0),
            category=rp.get('category', ''),
            category_code=rp.get('categoryCode', ''),
            product_url=rp.get('url', ''),
        ))

    logger.info(f'헬프스토어 파싱 완료: {keyword} → {len(products)}개')
    return products


def _do_collect_reviews(product_url: str, max_reviews: int = 30) -> list:
    """쿠팡 상품 리뷰 수집 — 새 페이지에서 상품 접속 후 API 호출"""
    import re as _re
    if not _ctx:
        _start_browser()

    pid_match = _re.search(r'products/(\d+)', product_url)
    if not pid_match:
        return []
    pid = pid_match.group(1)

    # 새 페이지에서 상품 상세로 접속 (쿠팡이 신뢰하는 컨텍스트)
    review_page = _ctx.new_page()
    reviews = []
    try:
        review_page.goto(product_url, wait_until='domcontentloaded', timeout=15000)
        review_page.wait_for_timeout(3000)

        page_size = 20
        pages = min((max_reviews // page_size) + 1, 15)

        for p in range(1, pages + 1):
            try:
                result = review_page.evaluate(f'''() => {{
                    return new Promise(resolve => {{
                        fetch('/next-api/review?productId={pid}&page={p}&size={page_size}&sortBy=DATE_DESC&ratingSummary=true', {{
                            credentials: 'include',
                            headers: {{ 'accept': 'application/json' }}
                        }})
                        .then(r => r.json())
                        .then(d => resolve(d))
                        .catch(e => resolve({{error: e.toString()}}));
                    }});
                }}''')

                if result.get('error'):
                    break

                data = result.get('data', {})
                review_list = data.get('reviews', [])

                for r in review_list:
                    reviews.append({
                        'rating': r.get('rating', 0),
                        'headline': r.get('headline', ''),
                        'content': r.get('content', ''),
                        'created': r.get('createdAt', ''),
                        'helpful_count': r.get('helpfulCount', 0),
                    })

                if len(review_list) < page_size:
                    break

                review_page.wait_for_timeout(500)
            except Exception as e:
                logger.error(f'리뷰 수집 에러: {e}')
                break
    finally:
        review_page.close()

    logger.info(f'리뷰 {len(reviews)}개 수집 (pid={pid})')
    return reviews


def _do_goldbox_crawl(url):
    """골드박스 페이지 크롤링 → 상품 목록 추출"""
    global _logged_in
    if not _ctx:
        _start_browser()
    # 골드박스는 로그인 불필요 (공개 페이지) — 하지만 브라우저가 필요

    page = _ctx.new_page()
    try:
        print(f'[GOLDBOX-CRAWL] 페이지 로딩: {url[:60]}')
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(5000)

        # 스크롤 — 새 상품이 안 나올 때까지 반복
        prev_count = 0
        no_change = 0
        for i in range(200):  # 최대 200회
            page.evaluate('window.scrollBy(0, 600)')
            page.wait_for_timeout(400)

            # 10회마다 상품 수 체크
            if i % 10 == 9:
                curr_count = page.evaluate(
                    """document.querySelectorAll('a[href*="/vp/products/"], a[href*="/pb/products/"]').length"""
                )
                if curr_count == prev_count:
                    no_change += 1
                    if no_change >= 3:  # 30회 스크롤해도 변화 없으면 종료
                        break
                else:
                    no_change = 0
                prev_count = curr_count

        page.wait_for_timeout(2000)

        # 상품 추출 — 쿠팡 상품 링크 기반
        products = page.evaluate('''() => {
            const items = [];
            const seen = new Set();

            // 방법1: 상품 링크 (coupang.com/vp/products/) 찾기
            document.querySelectorAll('a[href*="/vp/products/"], a[href*="/pb/products/"]').forEach(a => {
                const href = a.href || '';
                // 중복 URL 제거
                const pid = href.match(/products\/(\d+)/);
                if (pid && seen.has(pid[1])) return;
                if (pid) seen.add(pid[1]);

                // 상품명: 링크 안의 이미지 alt 또는 텍스트
                let name = '';
                const img = a.querySelector('img');
                if (img && img.alt && img.alt.length > 3) {
                    name = img.alt.trim();
                } else {
                    // 부모 or 형제에서 텍스트 찾기
                    const parent = a.closest('[class*="product"], [class*="item"], [class*="deal"], li, div');
                    if (parent) {
                        // 이름 후보: 가장 긴 텍스트 노드
                        const texts = [];
                        parent.querySelectorAll('span, p, div, strong, em').forEach(el => {
                            const t = el.innerText?.trim();
                            if (t && t.length > 5 && t.length < 100 && /[가-힣]/.test(t)) {
                                texts.push(t);
                            }
                        });
                        if (texts.length > 0) {
                            name = texts.sort((a,b) => b.length - a.length)[0];
                        }
                    }
                    if (!name) {
                        name = a.innerText?.trim().substring(0, 80);
                    }
                }

                // 필터: 진짜 상품인지 확인
                if (!name || name.length < 4) return;
                if (!/[가-힣]/.test(name)) return;  // 한글 없으면 제외
                if (/전체|삭제|검색|필터|더보기|로그인|장바구니|카테고리/.test(name)) return;

                // 가격 찾기
                let price = 0;
                let discount = '';
                const parent = a.closest('[class*="product"], [class*="item"], [class*="deal"], li, div');
                if (parent) {
                    const priceTexts = parent.innerText.match(/[\d,]+원/g);
                    if (priceTexts) {
                        price = parseInt(priceTexts[0].replace(/[^0-9]/g, '')) || 0;
                    }
                    const discMatch = parent.innerText.match(/(\d+)%/);
                    if (discMatch) discount = discMatch[0];
                }

                items.push({ name, price, discount, url: href });
            });

            return items;
        }''')

        # 추가 필터: 너무 짧거나 중복 이름 제거
        seen_names = set()
        filtered = []
        for p in products:
            name = p.get('name', '').strip()
            if len(name) < 5:
                continue
            # 이름 앞 20자로 중복 체크
            key = name[:20]
            if key in seen_names:
                continue
            seen_names.add(key)
            filtered.append(p)

        logger.info(f'골드박스 {len(filtered)}개 상품 수집 (원본 {len(products)}개)')
        return filtered
    finally:
        page.close()


def _do_coupang_keywords(keyword: str) -> dict:
    """쿠팡 자동완성 + 연관 키워드 수집"""
    if not _ctx:
        _start_browser()

    # 쿠팡 도메인에서 API 호출해야 CORS 통과
    page = _ctx.new_page()
    try:
        page.goto('https://www.coupang.com', wait_until='domcontentloaded', timeout=15000)
        page.wait_for_timeout(2000)

        # 1) 자동완성 API
        autocomplete = page.evaluate('''(keyword) => {
            return new Promise(resolve => {
                fetch('https://www.coupang.com/api/v2/search/autocomplete?keyword=' + encodeURIComponent(keyword), {
                    credentials: 'include',
                    headers: { 'accept': 'application/json' }
                })
                .then(r => r.json())
                .then(d => resolve(d))
                .catch(e => resolve({error: e.toString()}));
            });
        }''', keyword)

        autocomplete_keywords = []
        if not autocomplete.get('error'):
            # 자동완성 결과 파싱 — 구조는 다양할 수 있음
            items = autocomplete.get('keywords', [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, str):
                        autocomplete_keywords.append(item)
                    elif isinstance(item, dict):
                        kw = item.get('keyword') or item.get('name') or item.get('text', '')
                        if kw:
                            autocomplete_keywords.append(kw)

        # 2) 연관 검색어 — 검색 결과 페이지의 연관 키워드
        related_keywords = []
        try:
            page.goto(f'https://www.coupang.com/np/search?component=&q={keyword}',
                       wait_until='domcontentloaded', timeout=15000)
            page.wait_for_timeout(3000)

            related_keywords = page.evaluate('''() => {
                const keywords = [];
                // 연관 검색어 영역
                document.querySelectorAll('.search-related-keyword a, .related-search a, [class*="relatedKeyword"] a, [class*="related-keyword"] a').forEach(a => {
                    const text = a.innerText?.trim();
                    if (text && text.length > 1 && text.length < 30) {
                        keywords.push(text);
                    }
                });
                // 추천 검색어도 시도
                if (keywords.length === 0) {
                    document.querySelectorAll('[class*="recommend"] a, [class*="suggest"] a').forEach(a => {
                        const text = a.innerText?.trim();
                        if (text && text.length > 1 && text.length < 30 && /[가-힣]/.test(text)) {
                            keywords.push(text);
                        }
                    });
                }
                return keywords;
            }''')
        except Exception as e:
            logger.warning(f'연관 키워드 수집 실패: {e}')

        logger.info(f'쿠팡 키워드 수집: {keyword} → 자동완성 {len(autocomplete_keywords)}개, 연관 {len(related_keywords)}개')
        return {
            'autocomplete': autocomplete_keywords,
            'related': related_keywords
        }
    finally:
        page.close()


def _debug_first_li():
    """디버그: 페이지의 모든 listProducts 섹션 확인"""
    if not _page:
        return 'no page'
    if 'keyword_analyze_coupang' not in _page.url:
        _page.goto(COUPANG_PAGE, wait_until='domcontentloaded', timeout=15000)
        _page.wait_for_timeout(2000)

    _page.locator('#keyword').fill('')
    _page.locator('#keyword').type('남자 깔창', delay=30)
    _page.locator('#btnSearch').click()
    try:
        _page.wait_for_selector('.listProducts li', timeout=45000)
    except:
        pass
    _page.wait_for_timeout(10000)

    return _page.evaluate('''() => {
        const result = [];
        // 모든 .listProducts 찾기
        document.querySelectorAll('.listProducts').forEach((list, idx) => {
            const parent = list.parentElement;
            const parentId = parent ? (parent.id || parent.className || parent.tagName) : 'unknown';
            const lis = list.querySelectorAll('li');
            const firstLi = lis[0];
            let sample = firstLi ? firstLi.outerHTML.substring(0, 800) : 'empty';
            result.push(`\\n=== LIST #${idx} (parent: ${parentId}, items: ${lis.length}) ===\\n${sample}`);
        });
        return result.join('\\n');
    }''')


# ─── 외부 API ───
def wing_ensure_login():
    return _send('login', timeout=600)

def wing_search(keyword):
    return _send('search', {'keyword': keyword}, timeout=120)

def get_wing_status():
    try:
        return _send('status', timeout=5)
    except:
        return {'logged_in': False, 'wing_ok': False, 'has_browser': False}


def wing_coupang_keywords(keyword):
    return _send('coupang_keywords', {'keyword': keyword}, timeout=60)
