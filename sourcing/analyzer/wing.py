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


def _load_env(path=os.path.join(os.path.dirname(__file__), ".env")):
    if os.path.exists(path):
        for _l in open(path, encoding="utf-8"):
            _l = _l.strip()
            if "=" in _l and not _l.startswith("#"):
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())


_load_env()

logger = logging.getLogger(__name__)

# 통합 장애 알림 (automation/alert) — 스크래퍼가 조용히 깨질 때 두리 텔레그램으로
import sys as _sys, time as _time
_sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
try:
    from alert import alert as _alert
except Exception:
    def _alert(*a, **k):
        return False

_last_scraper_alert = {}  # {키: 마지막알림시각} — 동일 알림 1시간 1회(폭주 방지)


def _scraper_alert(key, message, level="warn"):
    """취약 스크래퍼 알림 — 같은 종류 알림은 1시간 1회만 전송(폭주 방지)."""
    now = _time.time()
    if now - _last_scraper_alert.get(key, 0) > 3600:
        _last_scraper_alert[key] = now
        try:
            _alert("소싱 스크래퍼", message, level)
        except Exception:
            pass


WING_BASE = 'https://wing.coupang.com'
WING_ID = os.environ.get("WING_ID", "")
WING_PW = os.environ.get("WING_PW", "")
HELPSTORE_BASE = 'https://helpstore.shop'
HELPSTORE_ID = os.environ.get("HELPSTORE_ID", "")
HELPSTORE_PW = os.environ.get("HELPSTORE_PW", "")
COUPANG_PAGE = f'{HELPSTORE_BASE}/keyword/keyword_analyze_coupang/'

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.wing_profile')

# 헬프스토어 확장 프로그램 경로 찾기
def _find_extension():
    import sys
    ext_id = 'nfbjgieajobfohijlkaaplipbiofblef'
    candidates = []
    if sys.platform == 'darwin':
        candidates.append(os.path.join(
            os.path.expanduser('~'), 'Library', 'Application Support',
            'Google', 'Chrome', 'Default', 'Extensions', ext_id
        ))
    candidates.append(os.path.join(
        os.environ.get('LOCALAPPDATA', ''),
        'Google', 'Chrome', 'User Data', 'Default', 'Extensions', ext_id
    ))
    for ext_base in candidates:
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
            elif action == 'collect_all_reviews':
                holder['result'] = _do_collect_all_reviews(args.get('product_url', ''), args.get('max_reviews', 9999))
            elif action == 'fetch_product_detail':
                holder['result'] = _do_fetch_product_detail(args.get('product_url', ''))
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
def _is_context_alive():
    try:
        if not _ctx or not _page:
            return False
        _ = _page.url
        _ = _ctx.pages   # 컨텍스트 실제 생존 검증 (죽으면 예외→False). _page.url은 캐시값 반환해 죽은 ctx를 못 잡음
        return True
    except:
        return False


def _reset_browser():
    global _pw, _ctx, _page, _logged_in, _wing_ok
    try:
        if _ctx:
            _ctx.close()
    except:
        pass
    try:
        if _pw:
            _pw.stop()
    except:
        pass
    _pw = _ctx = _page = None
    _logged_in = False
    _wing_ok = False
    logger.info('브라우저 리셋 완료')


def _start_browser():
    global _pw, _ctx, _page
    if _ctx and _is_context_alive():
        return
    if _ctx:
        _reset_browser()

    from playwright.sync_api import sync_playwright
    os.makedirs(STATE_DIR, exist_ok=True)

    ext_path = _find_extension()
    logger.info(f'확장 프로그램: {ext_path or "없음"}')

    launch_args = ['--disable-blink-features=AutomationControlled',
                    '--window-position=-32000,-32000', '--window-size=1,1',
                    '--no-focus-on-launch']
    if ext_path:
        launch_args.extend([
            f'--load-extension={ext_path}',
            f'--disable-extensions-except={ext_path}',
        ])

    # Docker/서버: headless, 로컬 GUI(macOS/Windows): headed
    import sys
    is_server = os.environ.get('DOCKER_ENV') == '1' or (
        sys.platform == 'linux' and not os.environ.get('DISPLAY')
    )
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

    # TargetClosedError 방지: 컨텍스트 죽어있으면 완전 리셋 후 재시작
    if not _is_context_alive():
        logger.info('컨텍스트 비정상 — 브라우저 강제 리셋 후 재시작')
        _reset_browser()
    _start_browser()

    # 1) 쿠팡윙 로그인
    logger.info('쿠팡윙 로그인 시도...')
    try:
        _page.goto(WING_BASE, wait_until='domcontentloaded', timeout=20000)
    except Exception as goto_err:
        # goto 자체가 TargetClosedError면 브라우저를 완전 재시작
        logger.warning(f'goto 실패 ({goto_err}) — 브라우저 완전 재시작')
        _reset_browser()
        _start_browser()
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
            # 실패 원인 확정용 증거 수집 (2026-07-02): xauth authenticate에 머무는 이유가
            # 2FA/캡차/크리덴셜 오류 중 뭔지 로그만으론 판별 불가했음 → URL+본문+스크린샷 기록
            try:
                fail_url = _page.url
                body_txt = ' '.join(_page.inner_text('body').split())[:400]
                shot = f'/Users/macmini_ky/ClaudeAITeam/logs/wing_login_fail_{_time.strftime("%Y%m%d_%H%M%S")}.png'
                _page.screenshot(path=shot)
                logger.warning(f'윙 로그인 실패 진단 — url={fail_url}')
                logger.warning(f'윙 로그인 실패 진단 — body[:400]={body_txt}')
                logger.warning(f'윙 로그인 실패 진단 — screenshot={shot}')
            except Exception as diag_err:
                logger.warning(f'윙 로그인 진단 수집 실패: {diag_err}')
            # 수동 대기 (최대 10초만 — 서버환경에서 사람이 로그인 불가)
            for i in range(10):
                _page.wait_for_timeout(1000)
                if 'wing.coupang.com' in _page.url and '/login' not in _page.url:
                    _wing_ok = True
                    break
    else:
        _wing_ok = True
        logger.info('쿠팡윙 이미 로그인됨')

    if not _wing_ok:
        logger.warning('쿠팡윙 로그인 실패 — 헬프스토어 전용 모드로 계속 진행')

    # 2) 헬프스토어 로그인
    logger.info('헬프스토어 로그인 시도...')
    try:
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
    except Exception as e:
        logger.warning(f'헬프스토어 페이지 이동 실패: {e}')

    # 3) 쿠팡 분석 페이지로 이동
    try:
        _page.goto(COUPANG_PAGE, wait_until='domcontentloaded', timeout=15000)
        _page.wait_for_timeout(2000)
    except Exception as e:
        logger.warning(f'쿠팡 분석 페이지 이동 실패: {e}')
        return {'success': False, 'message': f'쿠팡 분석 페이지 접근 불가: {e}'}

    _logged_in = True
    # 브라우저 최소화
    try:
        _page.evaluate('window.resizeTo(1,1); window.moveTo(-2000,-2000)')
    except:
        pass

    if _wing_ok:
        return {'success': True, 'message': '로그인 완료! (윙 + 헬프스토어)'}
    else:
        return {'success': True, 'message': '헬프스토어 로그인 완료 (윙 세션 없음 — 헬프스토어 전용)'}


def _do_search(keyword):
    """헬프스토어 쿠팡 분석 페이지에서 검색 → DOM 파싱"""
    global _logged_in
    from analyzer.helpstore import CoupangProduct

    if not _is_context_alive():
        logger.warning('브라우저 컨텍스트 죽어있음 — 재시작')
        _reset_browser()

    if not _ctx:
        _start_browser()
    if not _logged_in:
        # 자동 로그인 시도
        result = _do_full_login()
        if not result.get('success'):
            raise Exception('WING_LOGIN_REQUIRED')

    try:
        _page.goto(COUPANG_PAGE, wait_until='domcontentloaded', timeout=15000)
    except Exception as e:
        logger.warning(f'페이지 이동 실패 ({e}) — 브라우저 재시작')
        _reset_browser()
        _start_browser()
        result = _do_full_login()
        if not result.get('success'):
            raise Exception('WING_LOGIN_REQUIRED')
        _page.goto(COUPANG_PAGE, wait_until='domcontentloaded', timeout=15000)
    _page.wait_for_timeout(3000)

    # extension/page로 리다이렉트 되면 확장 미감지
    if '/extension/page' in _page.url:
        _scraper_alert(
            "wing_ext",
            "소싱 윙 스크래퍼가 헬프스토어 확장을 못 찾고 있어요 😢 "
            "크롬에서 확장이 꺼졌거나 윙 로그인이 풀린 것 같아요. 확인 부탁드려요!",
            "critical",
        )
        raise Exception('헬프스토어 확장 프로그램이 감지되지 않습니다')

    # 키워드 입력 + 검색
    search_input = _page.locator('#keyword')
    search_input.fill('')
    search_input.type(keyword, delay=30)
    _page.wait_for_timeout(300)

    # ★ fallback 오염 방지: 검색 클릭 전에 이전 검색 결과 li를 DOM에서 제거.
    #   이전엔 주석만 있고 제거 코드가 없어, wait_for_selector가 잔존 li를
    #   즉시 잡아 엉뚱한 이전 상품을 반환했음(예: 섬유향수→헤어집게핀).
    #   비워두면 아래 wait_for_selector가 '새로 생성된' 결과만 기다린다.
    try:
        _page.evaluate(
            "() => document.querySelectorAll("
            "'.listProducts li').forEach(el => el.remove())"
        )
    except Exception:
        pass
    _page.locator('#btnSearch').click()

    # 결과 로딩 대기 (위에서 DOM을 비웠으므로 새 결과가 나타날 때까지 정확히 대기)
    try:
        _page.wait_for_selector(
            '.listProducts li',
            timeout=45000
        )
        logger.info(f'상품 리스트 로딩 완료: {keyword}')
    except:
        # 상품이 없을 수 있음 — 페이지 상태 확인
        logger.warning(f'상품 로딩 타임아웃: {keyword}')
        # extension/page 리다이렉트 확인
        if '/extension/page' in _page.url:
            _scraper_alert(
                "wing_ext",
                "소싱 윙 스크래퍼가 헬프스토어 확장/윙 로그인 문제로 멈췄어요 😢 "
                "확장 상태랑 윙 로그인 확인 부탁드려요!",
                "critical",
            )
            raise Exception('확장 프로그램 또는 쿠팡윙 로그인 문제')
        return []

    # 1차 리스트(상위 노출 20개) 로딩 대기
    try:
        _page.wait_for_selector(
            '.listProducts li dl dd',
            timeout=30000
        )
        logger.info('1차 상품 리스트 로딩 감지')
    except:
        logger.warning('1차 리스트 로딩 타임아웃')

    # ★ 헬프스토어 레이아웃 변경(2026-06) 대응:
    #   판매량·판매금액이 채워진 2번째 리스트(상위 40개 판매순)는 페이지를
    #   끝까지 스크롤해야 lazy-load 된다. 스크롤 안 하면 1번째 리스트만 보이고
    #   판매량이 '조회하기' 버튼 상태라 전 상품이 스킵 → 빈 결과가 된다.
    for _ in range(10):
        _page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        _page.wait_for_timeout(1200)
    # 판매량이 '숫자'로 채워진 li가 나타날 때까지 대기 (조회하기 버튼 아닌 실제 데이터)
    try:
        _page.wait_for_function(
            '''() => {
                const lis = document.querySelectorAll('.listProducts li');
                for (const li of lis) {
                    const dts = li.querySelectorAll('dt');
                    const dds = li.querySelectorAll('dd');
                    for (let k = 0; k < dts.length; k++) {
                        if (dts[k].innerText.trim() === '판매량') {
                            const v = dds[k] ? dds[k].innerText.trim() : '';
                            if (/^[0-9][0-9,]*$/.test(v)) return true;
                        }
                    }
                }
                return false;
            }''',
            timeout=30000
        )
        logger.info('판매량 데이터(2차 리스트) 로딩 완료')
    except:
        logger.warning('판매량 데이터 로딩 타임아웃 — 스크롤 후에도 미확인')

    _page.evaluate('window.scrollTo(0, 0)')
    _page.wait_for_timeout(2000)  # 안정화

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
        // 헬프스토어 2026-06 레이아웃: 판매량/판매금액이 채워진 리스트와
        // '조회하기' 버튼만 있는 리스트가 공존한다. 두 리스트를 모두 순회하되
        // dl 클래스(type1/type2)에 의존하지 않고 li 안의 모든 dt/dd를 라벨로 매칭.
        // (판매량이 0인 항목은 호출부에서 스킵되므로 '조회하기' 리스트는 자동 제외)
        document.querySelectorAll('.listProducts li').forEach((li) => {
            const p = { price: 0, reviews: 0, clicks: 0, sales: 0, cvr: 0, revenue: 0, adWeight: 0, ctr: 0 };

            // 상품명 + URL
            const a = li.querySelector('strong a');
            if (a) { p.name = a.innerText.trim(); p.url = a.href || ''; }

            // 카테고리
            const sp = li.querySelector(':scope > span');
            if (sp) p.category = sp.innerText.trim();

            // li 안의 모든 dt/dd를 순서대로 매칭 (dl 구조 무관)
            const dts = li.querySelectorAll('dt');
            const dds = li.querySelectorAll('dd');
            for (let k = 0; k < dts.length; k++) {
                const dt = dts[k].innerText.trim();
                const raw = dds[k] ? dds[k].innerText.trim() : '';
                if (dt === '가격') p.price = parseNum(raw);
                else if (dt === '리뷰') p.reviews = parseNum(raw);
                else if (dt === '브랜드') p.brand = raw;
                else if (dt === '제조사') p.manufacturer = raw;
                else if (dt === '판매량' || dt === '6개월판매량') p.sales = parseNum(raw);
                else if (dt.includes('판매금액')) p.revenue = parseNum(raw);
                else if (dt === '클릭수') p.clicks = parseNum(raw);
                else if (dt === '전환율') p.cvr = parseFloat2(raw);
                else if (dt === '클릭율') p.ctr = parseFloat2(raw);
                else if (dt === '광고비중') p.adWeight = parseFloat2(raw);
            }

            // 카테고리 코드
            const kwBtn = li.querySelector('.btnShowKeyword');
            if (kwBtn) p.categoryCode = kwBtn.getAttribute('data-category-id') || kwBtn.getAttribute('data-id') || '';

            products.push(p);
        });
        return products;
    }''')

    # CoupangProduct 변환 — 판매량 데이터가 있는 상품만 (랭킹순 40개)
    # 상위 노출 상품 (노출증가/광고비중만 있는 것 = '조회하기' 버튼 리스트)은 제외
    products = []
    rank = 0
    seen = set()  # 두 리스트를 함께 순회하므로 같은 상품 중복 방지
    for rp in products_data:
        # 판매량 또는 매출 데이터가 없으면 상위 노출 상품 → 스킵
        if rp.get('sales', 0) == 0 and rp.get('revenue', 0) == 0:
            continue
        dedup_key = rp.get('url', '') or rp.get('name', '')
        if dedup_key and dedup_key in seen:
            continue
        seen.add(dedup_key)
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
    # 로그인 세션이 없으면 쿠팡 Akamai가 차단(Access Denied)하므로 로그인 보장
    if not _logged_in:
        _do_full_login()

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


def _do_collect_all_reviews(product_url: str, max_reviews: int = 9999) -> dict:
    """전체 리뷰 수집 — HTML 엔드포인트 + DOM 파싱 (크롬 확장과 동일 방식)"""
    import re as _re
    if not _ctx:
        _start_browser()
    # 로그인 세션이 없으면 쿠팡 Akamai가 차단(Access Denied)하므로 로그인 보장
    if not _logged_in:
        _do_full_login()

    pid_match = _re.search(r'products/(\d+)', product_url)
    if not pid_match:
        return {'error': 'invalid_url'}
    pid = pid_match.group(1)

    review_page = _ctx.new_page()
    reviews = []
    product_title = ''
    total_count = 0
    rating_summary = {}

    FETCH_REVIEWS_JS = """(url) => {
        return new Promise(resolve => {
            fetch(url, {
                method: 'GET',
                headers: {
                    'accept': '*/*',
                    'accept-language': 'ko-KR,ko;q=0.9',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                },
                credentials: 'include',
            })
            .then(r => r.text())
            .then(html => {
                if (html.includes('301 Moved') || html.includes('Access Denied')) {
                    resolve({error: 'blocked'});
                    return;
                }
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const totalEl = doc.querySelector('.js_reviewArticleTotalCountHiddenValue');
                const total = totalEl ? parseInt(totalEl.dataset.totalCount || '0', 10) : 0;

                const countEls = doc.querySelectorAll('.js_reviewArticleHiddenValue');
                const counts = {};
                countEls.forEach((el, i) => {
                    counts[5 - i] = parseInt(el.dataset.count || '0', 10);
                });

                const items = doc.querySelectorAll('.js_reviewArticleReviewList');
                const parsed = [];
                items.forEach(item => {
                    const ratingEl = item.querySelector('.js_reviewArticleRatingValue');
                    const r = ratingEl ? parseInt(ratingEl.dataset.rating || '0', 10) : 0;
                    const userEl = item.querySelector('.sdp-review__article__list__info__user');
                    let userName = '';
                    if (userEl) userName = userEl.textContent.trim();
                    const dateEl = item.querySelector('.sdp-review__article__list__info__product-info__reg-date');
                    const createdAt = dateEl ? dateEl.textContent.trim() : '';
                    const optionEl = item.querySelector('.sdp-review__article__list__info__product-info__name');
                    const option = optionEl ? optionEl.textContent.trim() : '';
                    const headlineEl = item.querySelector('.sdp-review__article__list__headline');
                    const headline = headlineEl ? headlineEl.textContent.trim() : '';
                    let content = '';
                    const contentEl = item.querySelector('.sdp-review__article__list__review__content');
                    if (contentEl) content = contentEl.textContent.trim();
                    else {
                        const contentEl2 = item.querySelector('.sdp-review__article__list__review');
                        if (contentEl2) content = contentEl2.textContent.trim();
                    }
                    const attachEl = item.querySelector('.sdp-review__article__list__attachment__list');
                    const photoCount = attachEl ? attachEl.querySelectorAll('li').length : 0;
                    let helpfulCount = 0;
                    const helpEl = item.querySelector('.js_reviewArticleHelpfulBtn, .sdp-review__article__list__help__count');
                    if (helpEl) { const hm = helpEl.textContent.match(/(\\d+)/); if (hm) helpfulCount = parseInt(hm[1], 10); }
                    let answer = '';
                    const answerEl = item.querySelector('.js_reviewArticleReplyArea, .sdp-review__article__list__seller-reply');
                    if (answerEl) answer = answerEl.textContent.trim();
                    parsed.push({ rating: r, headline, content, created_at: createdAt, helpful_count: helpfulCount, user_name: userName, option, photo_count: photoCount, answer });
                });
                resolve({ total, counts, reviews: parsed });
            })
            .catch(e => resolve({error: e.toString()}));
        });
    }"""

    try:
        review_page.goto(product_url, wait_until='domcontentloaded', timeout=20000)
        review_page.wait_for_timeout(3000)

        title_check = review_page.title()
        if 'Access Denied' in title_check:
            review_page.wait_for_timeout(2000)
            review_page.reload(wait_until='domcontentloaded', timeout=15000)
            review_page.wait_for_timeout(3000)

        product_title = review_page.evaluate("""() => {
            const selectors = ['h2.prod-buy-header__title', 'h1.prod-buy-header__title', '.prod-buy-header__title', 'h1', 'h2'];
            for (const s of selectors) {
                const el = document.querySelector(s);
                if (el && el.textContent.trim().length > 3) return el.textContent.trim();
            }
            return '';
        }""")

        page_size = 30
        info = review_page.evaluate(
            FETCH_REVIEWS_JS,
            f'https://www.coupang.com/vp/product/reviews?productId={pid}&page=1&size={page_size}&sortBy=ORDER_SCORE_ASC&ratingSummary=true&viRoleCode=2'
        )
        if not info or info.get('error'):
            logger.error(f'리뷰 첫 페이지 에러: {info}')
            review_page.close()
            return {'product_id': pid, 'product_title': product_title, 'total_count': 0, 'collected_count': 0, 'rating_summary': {}, 'reviews': []}

        total_count = info.get('total', 0)
        rating_counts = info.get('counts', {})
        sum_r = sum(int(r) * c for r, c in rating_counts.items())
        sum_c = sum(rating_counts.values())
        avg_rating = round(sum_r / sum_c, 1) if sum_c > 0 else 0
        rating_summary = {'averageRating': avg_rating, 'ratingCounts': rating_counts}

        seen = set()
        for r in info.get('reviews', []):
            key = f"{r.get('user_name','')}|{r.get('created_at','')}|{r.get('content','')[:50]}"
            if key not in seen:
                seen.add(key)
                reviews.append(r)

        for rating in range(1, 6):
            if len(reviews) >= max_reviews:
                break
            count = rating_counts.get(rating, rating_counts.get(str(rating), 0))
            if count == 0:
                continue

            page_num = 1
            while len(reviews) < max_reviews:
                url = f'https://www.coupang.com/vp/product/reviews?productId={pid}&page={page_num}&size={page_size}&sortBy=ORDER_SCORE_ASC&ratingSummary=true&viRoleCode=2&ratings={rating}'
                try:
                    res = review_page.evaluate(FETCH_REVIEWS_JS, url)
                except Exception as e:
                    logger.error(f'리뷰 수집 에러 ★{rating} p{page_num}: {e}')
                    break

                if not res or res.get('error') or not res.get('reviews'):
                    break

                for r in res['reviews']:
                    key = f"{r.get('user_name','')}|{r.get('created_at','')}|{r.get('content','')[:50]}"
                    if key not in seen:
                        seen.add(key)
                        reviews.append(r)

                if len(res['reviews']) < page_size:
                    break
                page_num += 1
                review_page.wait_for_timeout(300 + (400 * (page_num % 5 == 0)))

            review_page.wait_for_timeout(500)
    finally:
        review_page.close()

    logger.info(f'전체 리뷰 {len(reviews)}개 수집 (pid={pid}, title={product_title[:30]})')
    return {
        'product_id': pid,
        'product_title': product_title,
        'total_count': total_count,
        'collected_count': len(reviews),
        'rating_summary': rating_summary,
        'reviews': reviews,
    }


def _do_fetch_product_detail(product_url: str) -> dict:
    """쿠팡 상품 상세페이지 데이터 추출 (Playwright persistent context 사용, Akamai 우회)
    Returns: {'title': ..., 'price': ..., 'detail': ..., 'images': [...]}
    """
    if not _ctx:
        _start_browser()

    detail_page = _ctx.new_page()
    try:
        detail_page.goto(product_url, wait_until='domcontentloaded', timeout=20000)
        detail_page.wait_for_timeout(3000)

        # Access Denied 확인
        title_check = detail_page.title()
        if 'Access Denied' in title_check or 'denied' in title_check.lower():
            print(f'[WING_DETAIL] Access Denied — 재시도 중...')
            detail_page.wait_for_timeout(2000)
            detail_page.reload(wait_until='domcontentloaded', timeout=15000)
            detail_page.wait_for_timeout(3000)

        # lazy loading 트리거 — 페이지 끝까지 스크롤
        for _ in range(5):
            detail_page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            detail_page.wait_for_timeout(1000)
        detail_page.evaluate('window.scrollTo(0, 0)')
        detail_page.wait_for_timeout(1000)

        # JS로 상세 데이터 추출
        data = detail_page.evaluate(r"""() => {
            var title = '';
            var titleSelectors = ['h2.prod-buy-header__title','h1.prod-buy-header__title','.prod-buy-header__title','[class*="prod-title"]','h1','h2'];
            for (var ti=0; ti<titleSelectors.length; ti++) {
                var el = document.querySelector(titleSelectors[ti]);
                if (el && el.textContent.trim().length > 3) { title = el.textContent.trim(); break; }
            }

            var price = '';
            var priceSelectors = ['.total-price strong','[class*="total-price"] strong','.prod-coupon-price strong','[class*="prod-price"] strong','[class*="price"] strong'];
            for (var pi=0; pi<priceSelectors.length; pi++) {
                var pel = document.querySelector(priceSelectors[pi]);
                if (pel && pel.textContent.trim()) { price = pel.textContent.trim(); break; }
            }

            var detail = '';
            var detailSelectors = ['.product-detail-content-inside','.product-detail-content','#productDetail','.prod-description-detail','.prod-description','[class*="detail-content"]','[id*="productDetail"]'];
            for (var di=0; di<detailSelectors.length; di++) {
                var del_ = document.querySelector(detailSelectors[di]);
                if (del_ && del_.innerText && del_.innerText.trim().length > 50) {
                    detail = del_.innerText.trim().substring(0, 1500); break;
                }
            }
            if (!detail) {
                var allText = document.body.innerText || '';
                var lines = allText.split('\n').filter(function(l){ return l.trim().length > 10; });
                detail = lines.slice(0, 80).join('\n').substring(0, 2000);
            }

            var images = [];
            var imgSelectors = ['.product-detail-content-inside img','.product-detail-content img','#productDetail img','[class*="detail"] img'];
            for (var j=0; j<imgSelectors.length; j++) {
                var imgs = document.querySelectorAll(imgSelectors[j]);
                if (imgs.length > 0) {
                    for (var k=0; k<Math.min(imgs.length,15); k++) {
                        var src = imgs[k].src || imgs[k].getAttribute('data-src') || '';
                        if (src && src.indexOf('http') === 0) images.push(src);
                    }
                    if (images.length > 0) break;
                }
            }

            return {title: title, price: price, detail: detail, images: images};
        }""")

        return data or {}
    except Exception as e:
        print(f'[WING_DETAIL] 오류: {e}')
        return {}
    finally:
        try:
            detail_page.close()
        except Exception:
            pass


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
    """디버그: 검색 후 상품 리스트 컨테이너를 자동 탐지하고 첫 li 구조를 덤프.
    헬프스토어 레이아웃 변경 대응용 — 옛 .listProducts 클래스에 의존하지 않는다."""
    global _page
    if not _page:
        # 앱 재시작 등으로 페이지가 없으면 로그인부터 복구
        _do_full_login()
    if not _page:
        return 'no page (login failed)'
    if 'keyword_analyze_coupang' not in _page.url:
        _page.goto(COUPANG_PAGE, wait_until='domcontentloaded', timeout=15000)
        _page.wait_for_timeout(2000)

    _page.locator('#keyword').fill('')
    _page.locator('#keyword').type('남자 깔창', delay=30)
    _page.locator('#btnSearch').click()
    # 셀렉터에 의존하지 않고 충분히 대기 (확장 API + WebSocket 완료)
    _page.wait_for_timeout(18000)

    # 페이지 하단까지 스크롤 → lazy-load로 판매량/판매금액이 채워지는지 확인
    for _ in range(10):
        _page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        _page.wait_for_timeout(1500)
    _page.evaluate('window.scrollTo(0, 0)')
    _page.wait_for_timeout(1500)

    return _page.evaluate(r'''() => {
        const out = [];
        const alert = document.querySelector('#alertpopup');
        out.push('차단팝업: ' + (alert && getComputedStyle(alert).display !== 'none'
            ? ('보임 → ' + ((document.querySelector('#alertmsg') || {}).innerText || '')) : '없음'));
        const lists = document.querySelectorAll('.listProducts');
        out.push('listProducts 컨테이너 개수: ' + lists.length);
        lists.forEach((ul, idx) => {
            const lis = ul.querySelectorAll(':scope > li');
            const parent = ul.parentElement;
            const pcls = parent ? (parent.className || parent.id || parent.tagName) : '';
            out.push(`\n##### LIST #${idx} (부모:${pcls}) 직속li=${lis.length}`);
            const probe = [...new Set([0, Math.floor(lis.length / 2), lis.length - 1])].filter(i => i >= 0);
            probe.forEach(i => {
                const li = lis[i]; if (!li) return;
                const dts = [...li.querySelectorAll('dt')].map(d => d.innerText.trim());
                const dds = [...li.querySelectorAll('dd')].map(d => d.innerText.trim());
                const hasBtn = !!li.querySelector('.btnInquirySalesW');
                out.push(`  li[${i}] 조회버튼=${hasBtn}\n     dt=${JSON.stringify(dts)}\n     dd=${JSON.stringify(dds)}`);
            });
        });
        return out.join('\n');
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


def wing_fetch_product_detail(product_url: str) -> dict:
    """Playwright persistent context로 쿠팡 상품 상세페이지 데이터 추출
    CDP와 달리 로그인 세션과 anti-detection이 적용되어 Akamai 차단 우회"""
    return _send('fetch_product_detail', {'product_url': product_url}, timeout=30)
