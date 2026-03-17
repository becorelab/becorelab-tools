"""
비코어랩 쿠팡 마켓 파인더 — 메인 Flask 앱
포트: 8090 (기존 sourcing_app.py 8080과 분리)
"""

import os
import sys

# 프로젝트 루트를 path에 추가 (다른 import보다 먼저 실행)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
import threading
from datetime import datetime
from collections import Counter
from flask import Flask, render_template, request, jsonify
import analyzer.firestore_db as fdb

from analyzer.helpstore import (
    HelpstoreAPI, scan_keyword_api_only,
    CoupangProduct, InflowKeyword
)
from analyzer.scoring import calculate_opportunity, generate_keyword_variants, OpportunityScore
from analyzer.wing import wing_search, wing_ensure_login, get_wing_status
from analyzer.reviews import analyze_reviews_basic, analyze_reviews_claude

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    """크롬 확장프로그램에서의 요청 허용"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
    return response


# 전역 헬프스토어 API 인스턴스
helpstore_api = None

def get_helpstore():
    global helpstore_api
    if helpstore_api is None:
        helpstore_api = HelpstoreAPI()
    return helpstore_api
app.config['SECRET_KEY'] = 'becorelab-sourcing-analyzer-2026'


# ─────────────────────────────────────────────
# 라우트
# ─────────────────────────────────────────────
@app.route('/')
def index():
    is_server = os.environ.get('MARKET_FINDER_ENV', 'local') == 'server'
    return render_template('index.html', is_server=is_server)


# === 시장스캔 API ===
@app.route('/api/scan/manual', methods=['POST'])
def manual_scan():
    """직접 조사 — 키워드 입력하면 헬프스토어에서 데이터 수집"""
    data = request.json
    keyword = data.get('keyword', '').strip()
    use_cdp = data.get('use_cdp', False)  # CDP 모드 (쿠팡 실데이터)
    if not keyword:
        return jsonify({'success': False, 'error': '키워드를 입력해주세요'})

    # 스캔 기록 생성
    scan_id = fdb.create_scan(keyword, 'manual', 'scanning')

    # 백그라운드 스레드에서 수집 수행
    thread = threading.Thread(
        target=_run_scan_background,
        args=(scan_id, keyword, use_cdp)
    )
    thread.daemon = True
    thread.start()

    mode = 'CDP (쿠팡 실데이터)' if use_cdp else 'API (키워드 데이터)'
    return jsonify({
        'success': True,
        'scan_id': scan_id,
        'message': f'"{keyword}" 조사를 시작합니다 [{mode}]'
    })


def _run_scan_background(scan_id: int, keyword: str, use_cdp: bool = False):
    """백그라운드에서 헬프스토어 데이터 수집 + 분석"""
    with app.app_context():
        try:
            if use_cdp:
                try:
                    _run_scan_cdp(scan_id, keyword)
                except Exception as cdp_err:
                    # CDP 실패 시 API 모드로 자동 폴백
                    print(f'[SCAN-CDP] 실패 → API 모드로 전환: {cdp_err}')
                    _run_scan_api(scan_id, keyword)
            else:
                _run_scan_api(scan_id, keyword)
        except Exception as e:
            import traceback
            print(f'[SCAN] 에러: {keyword} — {e}')
            traceback.print_exc()
            fdb.update_scan(scan_id, status='failed')


def _run_scan_api(scan_id: int, keyword: str):
    """서버 API 전용 스캔 (기존 로직)"""
    # 1. 헬프스토어 서버 API로 키워드 데이터 수집
    api = get_helpstore()
    result = api.search_keyword(keyword)

    # 2. 연관 키워드를 inflow_keywords 테이블에 저장
    for kw in result.related_keywords:
        fdb.add_inflow_keyword(scan_id, {
            'keyword': kw.keyword,
            'search_volume': kw.total_search,
            'click_count': kw.pc_search + kw.mobile_search,
            'click_rate': (kw.pc_click_rate + kw.mobile_click_rate) / 2,
            'ad_weight': 0,
        })

    # 3. 띄어쓰기 변형 키워드 생성 및 저장
    _save_keyword_variants(scan_id, keyword, result.related_keywords)

    # 4. 기회점수 산출 (서버 API 데이터 기반)
    keyword_nospace = keyword.replace(' ', '')
    main_kw = None
    for kw in result.related_keywords:
        if kw.keyword == keyword or kw.keyword.replace(' ', '') == keyword_nospace:
            main_kw = kw
            break

    search_volume = main_kw.total_search if main_kw else result.total_search_volume
    product_count = main_kw.product_count if main_kw else result.product_count
    competition = main_kw.competition if main_kw else result.competition

    # 기회점수 산출
    import math
    supply_demand_score = 0
    if product_count > 0 and search_volume > 0:
        ratio = search_volume / product_count
        supply_demand_score = min(100, ratio * 15)

    market_score = 0
    if search_volume > 0:
        market_score = min(100, max(0,
            (math.log10(search_volume) - math.log10(500)) /
            (math.log10(100000) - math.log10(500)) * 100
        ))

    comp_score = 50
    if competition == '낮음':
        comp_score = 90
    elif competition == '보통':
        comp_score = 60
    elif competition == '높음':
        comp_score = 30

    simple_score = supply_demand_score * 0.4 + market_score * 0.35 + comp_score * 0.25

    recommended = ''
    best_ratio = 0
    for kw in result.related_keywords[:50]:
        if kw.product_count > 0 and kw.total_search >= 1000:
            r = kw.total_search / kw.product_count
            if r > best_ratio and not kw.is_brand:
                best_ratio = r
                recommended = kw.keyword

    # 5. 스캔 결과 업데이트
    fdb.update_scan(scan_id,
        status='scanned',
        category=result.main_category,
        opportunity_score=round(simple_score, 1),
        top10_avg_revenue=0,
        top10_avg_sales=0,
        top10_avg_price=0,
        revenue_equality=0,
        new_product_rate=0,
        ad_dependency=0,
        recommended_keyword=recommended,
    )
    print(f'[SCAN-API] 완료: {keyword} (점수: {simple_score:.1f}, 연관키워드: {len(result.related_keywords)}개)')


def _run_scan_cdp(scan_id: int, keyword: str):
    """
    CDP 전체 스캔 — 실제 쿠팡 데이터 (매출/판매량/클릭수/전환율)
    서버 API 데이터 + 브라우저 자동화 데이터 결합
    """
    print(f'[SCAN-CDP] 시작: {keyword} (Chrome CDP 연동)')

    # 전체 스캔 (서버 API + 브라우저 자동화)
    result = scan_keyword_full_sync(keyword)

    # ─── 상품 데이터 저장 ───
    for product in result.products:
        fdb.add_product(scan_id, {
            'ranking': product.ranking, 'product_name': product.product_name,
            'brand': product.brand, 'manufacturer': product.manufacturer,
            'price': product.price, 'sales_monthly': product.sales_monthly,
            'revenue_monthly': product.revenue_monthly, 'review_count': product.review_count,
            'click_count': product.click_count, 'conversion_rate': product.conversion_rate,
            'page_views': product.page_views, 'category': product.category,
            'category_code': product.category_code, 'product_url': product.product_url,
        })

    # ─── 유입 키워드 저장 ───
    for kw in result.inflow_keywords:
        fdb.add_inflow_keyword(scan_id, {
            'keyword': kw.keyword, 'search_volume': kw.search_volume,
            'click_count': kw.click_count, 'click_rate': kw.click_rate,
            'impression_increase': kw.impression_increase, 'ad_weight': kw.ad_weight,
        })

    # ─── 연관 키워드 저장 (API에서 가져온 것) ───
    for kw in result.related_keywords:
        fdb.add_inflow_keyword(scan_id, {
            'keyword': kw.keyword, 'search_volume': kw.total_search,
            'click_count': kw.pc_search + kw.mobile_search,
            'click_rate': (kw.pc_click_rate + kw.mobile_click_rate) / 2,
            'ad_weight': 0,
        })

    # ─── 띄어쓰기 변형 키워드 ───
    _save_keyword_variants(scan_id, keyword, result.related_keywords)

    # ─── 기회점수 산출 (실제 쿠팡 데이터 기반!) ───
    opp_score = calculate_opportunity(
        products=result.products,
        inflow_keywords=result.inflow_keywords,
        related_keywords=result.related_keywords,
        keyword=keyword
    )

    # ─── 스캔 결과 업데이트 ───
    fdb.update_scan(scan_id,
        status='scanned',
        category=result.main_category,
        opportunity_score=round(opp_score.total_score, 1),
        top10_avg_revenue=opp_score.top10_avg_revenue,
        top10_avg_sales=opp_score.top10_avg_sales,
        top10_avg_price=opp_score.top10_avg_price,
        revenue_concentration=round(opp_score.top1_share * 100, 1),
        revenue_equality=round(opp_score.revenue_equality * 100, 1),
        new_product_rate=round(opp_score.new_product_rate * 100, 1),
        ad_dependency=round(opp_score.ad_dependency, 1),
        recommended_keyword=opp_score.recommended_keyword,
    )

    print(
        f'[SCAN-CDP] 완료: {keyword}\n'
        f'  기회점수: {opp_score.total_score:.1f} ({opp_score.grade})\n'
        f'  상품: {len(result.products)}개 | 유입키워드: {len(result.inflow_keywords)}개\n'
        f'  상위10 평균매출: {opp_score.top10_avg_revenue:,}원\n'
        f'  1위점유율: {opp_score.top1_share*100:.1f}% | 매출균등도: {opp_score.revenue_equality*100:.1f}%\n'
        f'  신상품진입률: {opp_score.new_product_rate*100:.1f}% | 광고의존도: {opp_score.ad_dependency:.1f}%\n'
        f'  추천키워드: {opp_score.recommended_keyword}'
    )


def _save_keyword_variants(scan_id: int, keyword: str, related_keywords: list):
    """띄어쓰기 변형 키워드 생성 및 저장"""
    variants = generate_keyword_variants(keyword)
    for variant in variants:
        variant_search = 0
        variant_comp = ''
        for kw in related_keywords:
            if kw.keyword == variant:
                variant_search = kw.total_search
                variant_comp = kw.competition
                break
        fdb.add_keyword_variant(scan_id, {
            'original_keyword': keyword,
            'variant_keyword': variant,
            'search_volume': variant_search,
            'competition_level': variant_comp,
        })


# === 쿠팡윙 직접 스캔 ===
_wing_state = {'status': 'idle', 'message': ''}


@app.route('/api/wing/login', methods=['POST'])
def api_wing_login():
    """쿠팡윙 로그인 (백그라운드 — 브라우저 열고 로그인 대기)"""
    if _wing_state['status'] == 'logging_in':
        return jsonify({'success': True, 'message': '로그인 진행 중...'})

    _wing_state['status'] = 'logging_in'

    def _do():
        result = wing_ensure_login()
        _wing_state['status'] = 'logged_in' if result['success'] else 'failed'
        _wing_state['message'] = result['message']

    threading.Thread(target=_do, daemon=True).start()
    return jsonify({'success': True, 'message': '브라우저를 여는 중...'})


@app.route('/api/wing/login/poll')
def api_wing_login_poll():
    return jsonify({'success': True, 'status': _wing_state['status'], 'message': _wing_state['message']})


@app.route('/api/wing/debug')
def api_wing_debug():
    """디버그: 첫 상품 HTML 구조"""
    from analyzer.wing import _send
    try:
        html = _send('debug_html', timeout=120)
        return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        return str(e), 500


@app.route('/api/wing/status')
def api_wing_status():
    """쿠팡윙 로그인 상태 확인"""
    status = get_wing_status()
    return jsonify({'success': True, **status})


@app.route('/api/scan/wing', methods=['POST'])
def wing_scan():
    """쿠팡윙 직접 스캔 — 실제 판매 데이터 수집"""
    data = request.json
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'success': False, 'error': '키워드를 입력해주세요'})

    # 스캔 기록 생성
    scan_id = fdb.create_scan(keyword, 'wing', 'scanning')

    # 백그라운드 스레드에서 수집
    thread = threading.Thread(
        target=_run_scan_wing,
        args=(scan_id, keyword)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'success': True,
        'scan_id': scan_id,
        'message': f'"{keyword}" 쿠팡윙 스캔 시작!'
    })


def _run_scan_wing(scan_id: int, keyword: str):
    """쿠팡윙 API로 상품 데이터 수집 + 헬프스토어 키워드 데이터 결합"""
    with app.app_context():
        try:
            # 1. 쿠팡윙 상품 데이터 (서버에서는 크롬 확장 없어서 스킵)
            products = []
            is_server = os.environ.get('DOCKER_ENV') == '1'
            if is_server:
                print(f'[SCAN-WING] 서버 환경 — 윙 브라우저 스킵 (키워드 데이터만 수집)')
            else:
                try:
                    products = wing_search(keyword)
                    for p in products:
                        fdb.add_product(scan_id, {
                            'ranking': p.ranking, 'product_name': p.product_name,
                            'brand': p.brand, 'manufacturer': p.manufacturer,
                            'price': p.price, 'sales_monthly': p.sales_monthly,
                            'revenue_monthly': p.revenue_monthly, 'review_count': p.review_count,
                            'click_count': p.click_count, 'conversion_rate': p.conversion_rate,
                            'page_views': p.page_views, 'category': p.category,
                            'category_code': p.category_code, 'product_url': p.product_url,
                        })
                except Exception as wing_err:
                    print(f'[SCAN-WING] 윙 데이터 수집 실패 (키워드 데이터만 사용): {wing_err}')

            # 2. 헬프스토어 키워드 데이터 (연관키워드/검색량)
            api = get_helpstore()
            api_result = api.search_keyword(keyword)

            for kw in api_result.related_keywords:
                fdb.add_inflow_keyword(scan_id, {
                    'keyword': kw.keyword, 'search_volume': kw.total_search,
                    'click_count': kw.pc_search + kw.mobile_search,
                    'click_rate': (kw.pc_click_rate + kw.mobile_click_rate) / 2,
                    'ad_weight': 0,
                })

            # 3. 키워드 변형
            _save_keyword_variants(scan_id, keyword, api_result.related_keywords)

            # 4. 기회점수 산출
            opp_score = calculate_opportunity(
                products=products,
                inflow_keywords=[],
                related_keywords=api_result.related_keywords,
                keyword=keyword
            )

            # 5. DB 업데이트
            fdb.update_scan(scan_id,
                status='scanned',
                category=api_result.main_category,
                opportunity_score=round(opp_score.total_score, 1),
                top10_avg_revenue=opp_score.top4_10_avg_revenue,
                top10_avg_sales=opp_score.top4_10_avg_sales,
                top10_avg_price=opp_score.top4_10_avg_price,
                revenue_concentration=round(opp_score.top3_share * 100, 1),
                revenue_equality=round(opp_score.sellers_over_3m_rate * 100, 1),
                new_product_rate=round(opp_score.new_product_rate * 100, 1),
                ad_dependency=round(opp_score.avg_new_product_weight, 1),
                recommended_keyword=opp_score.recommended_keyword,
            )

            print(
                f'[SCAN-WING] 완료: {keyword}\n'
                f'  기회점수: {opp_score.total_score:.1f} ({opp_score.grade})\n'
                f'  매출분산: {opp_score.concentration_score:.0f} | 활성: {opp_score.activity_score:.0f}\n'
                f'  기대매출: {opp_score.entry_revenue_score:.0f} | 수요신호: {opp_score.demand_signal_score:.0f}\n'
                f'  상위3 점유율: {opp_score.top3_share*100:.1f}% | 300만+: {opp_score.sellers_over_3m}개\n'
                f'  4~10등 평균매출: {opp_score.top4_10_avg_revenue:,}원\n'
                f'  신상품 가중치: {opp_score.avg_new_product_weight:.1f}'
            )

        except Exception as e:
            import traceback
            error_msg = str(e)
            print(f'[SCAN-WING] 에러: {keyword} — {error_msg}')
            traceback.print_exc()

            status = 'login_required' if 'LOGIN_REQUIRED' in error_msg else 'failed'
            fdb.update_scan(scan_id, status=status)


# === 카테고리 탐색 ===
from analyzer.categories import CATEGORY_SEEDS, get_all_seeds, get_category_names, get_explorable_categories, SKIP_CATEGORIES


@app.route('/api/categories')
def api_categories():
    """카테고리 트리 (대 > 소)"""
    cats = []
    for name, keywords in CATEGORY_SEEDS.items():
        cats.append({
            'name': name,
            'children': keywords,
            'count': len(keywords),
        })
    return jsonify({'success': True, 'categories': cats})


@app.route('/api/autoscan/explore', methods=['POST'])
def api_explore_start():
    """카테고리 탐색 시작 — 선택한 카테고리의 시드로 자동 스캔"""
    if _auto_scan_state['running']:
        return jsonify({'success': False, 'error': '이미 스캔 진행 중입니다'})

    data = request.get_json(silent=True) or {}
    selected_cats = data.get('categories', [])  # 빈 배열이면 전체
    max_scan = data.get('max_scan', 30)
    min_search = data.get('min_search', 3000)

    # 시드 수집
    if selected_cats:
        seeds = []
        for cat in selected_cats:
            seeds.extend(CATEGORY_SEEDS.get(cat, []))
    else:
        seeds = [s['keyword'] for s in get_all_seeds()]

    if not seeds:
        return jsonify({'success': False, 'error': '카테고리를 선택해주세요'})

    _auto_scan_state.update({
        'running': True,
        'phase': 'expanding',
        'seed_keywords': seeds,
        'candidates': [],
        'scanned': 0,
        'total': 0,
        'current_keyword': '',
        'results': [],
        'errors': [],
    })

    thread = threading.Thread(
        target=_run_autoscan,
        args=(seeds, min_search, max_scan),
        daemon=True
    )
    thread.start()

    return jsonify({
        'success': True,
        'message': f'{len(seeds)}개 시드로 카테고리 탐색 시작!'
    })


# === 골드박스 ===
GOLDBOX_URL = 'https://pages.coupang.com/p/121237?sourceType=gm_crm_goldbox&subSourceType=gm_crm_gwsrtcut'

_goldbox_state = {
    'running': False,
    'phase': '',
    'products': [],
    'scanned': 0,
    'total': 0,
    'current': '',
}


@app.route('/api/goldbox/start', methods=['POST'])
def api_goldbox_start():
    """골드박스 수집 시작"""
    if _goldbox_state['running']:
        return jsonify({'success': False, 'error': '이미 진행 중'})

    _goldbox_state.update({
        'running': True, 'phase': 'crawling', 'products': [],
        'scanned': 0, 'total': 0, 'current': '',
    })

    thread = threading.Thread(target=_run_goldbox, daemon=True)
    thread.start()
    return jsonify({'success': True, 'message': '골드박스 수집 시작!'})


@app.route('/api/goldbox/status')
def api_goldbox_status():
    return jsonify({
        'success': True,
        'phase': _goldbox_state['phase'],
        'products': len(_goldbox_state['products']),
        'current': _goldbox_state['current'],
        'running': _goldbox_state['running'],
    })


@app.route('/api/goldbox/products')
def api_goldbox_products():
    return jsonify({'success': True, 'products': _goldbox_state['products']})


@app.route('/api/goldbox/history')
def api_goldbox_history():
    """골드박스 일별 기록"""
    dates = fdb.get_goldbox_dates()
    return jsonify({'success': True, 'dates': dates})


@app.route('/api/goldbox/history/<date>')
def api_goldbox_history_date(date):
    """특정 날짜의 골드박스 상품"""
    products = fdb.get_goldbox_by_date(date)
    return jsonify({'success': True, 'date': date, 'products': products})


def _run_goldbox():
    """골드박스 크롤링 → 상품 수집 (키워드 추출/스캔 없음)"""
    with app.app_context():
        try:
            _goldbox_state['phase'] = 'crawling'
            _goldbox_state['current'] = '골드박스 페이지 로딩...'

            products = _crawl_goldbox_direct(GOLDBOX_URL)
            _goldbox_state['products'] = products
            _goldbox_state['current'] = f'{len(products)}개 상품 수집 완료'

            # DB에 일별 저장
            import re
            today = datetime.now().strftime('%Y-%m-%d')
            goldbox_products = []
            for p in products:
                words = re.findall(r'[가-힣]{2,6}', p.get('name', ''))
                extracted = ' '.join(words[:3]) if words else ''
                goldbox_products.append({
                    'product_name': p.get('name', ''),
                    'price': p.get('price', 0),
                    'discount': p.get('discount', ''),
                    'product_url': p.get('url', ''),
                    'extracted_keyword': extracted,
                })
            fdb.add_goldbox_products(today, goldbox_products)
            print(f'[GOLDBOX] {today} — {len(products)}개 상품 저장')

            if not products:
                _goldbox_state['phase'] = 'error'
                _goldbox_state['current'] = '상품을 찾을 수 없습니다'
                return

            _goldbox_state['phase'] = 'done'

        except Exception as e:
            import traceback
            traceback.print_exc()
            _goldbox_state['phase'] = 'error'
            _goldbox_state['current'] = str(e)
        finally:
            _goldbox_state['running'] = False


def _crawl_goldbox_direct(url: str) -> list:
    """골드박스 크롤링 — 별도 Playwright (Wing 워커와 독립)"""
    from playwright.sync_api import sync_playwright
    import re

    print('[GOLDBOX] 크롤링 시작...')
    is_server = os.environ.get('DOCKER_ENV') == '1'
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=is_server,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()

    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(5000)

        page.evaluate(r'''() => {
            window.__goldbox_items = {};
            window.__goldbox_collect = () => {
                document.querySelectorAll('a[href*="/vp/products/"], a[href*="/pb/products/"]').forEach(a => {
                    const href = a.href || '';
                    const pid = href.match(/products\/(\d+)/);
                    if (!pid || window.__goldbox_items[pid[1]]) return;

                    let name = '';
                    const img = a.querySelector('img');
                    if (img && img.alt && img.alt.length > 3) {
                        name = img.alt.trim();
                    } else {
                        const parent = a.closest('[class*="product"], [class*="item"], [class*="deal"], li, div');
                        if (parent) {
                            const texts = [];
                            parent.querySelectorAll('span, p, div, strong, em').forEach(el => {
                                const t = el.innerText?.trim();
                                if (t && t.length > 5 && t.length < 100 && /[가-힣]/.test(t)) texts.push(t);
                            });
                            if (texts.length > 0) name = texts.sort((a,b) => b.length - a.length)[0];
                        }
                        if (!name) name = a.innerText?.trim().substring(0, 80);
                    }

                    if (!name || name.length < 4 || !/[가-힣]/.test(name)) return;
                    if (/전체|삭제|검색|필터|더보기|로그인|장바구니|카테고리/.test(name)) return;

                    let price = 0, discount = '';
                    const parent = a.closest('[class*="product"], [class*="item"], [class*="deal"], li, div');
                    if (parent) {
                        const m = parent.innerText.match(/[\d,]+원/g);
                        if (m) price = parseInt(m[0].replace(/[^0-9]/g, '')) || 0;
                        const d = parent.innerText.match(/(\d+)%/);
                        if (d) discount = d[0];
                    }

                    window.__goldbox_items[pid[1]] = { name, price, discount, url: href };
                });
            };
        }''')

        no_change = 0
        prev_total = 0
        for i in range(300):
            page.evaluate('window.scrollBy(0, 500)')
            page.wait_for_timeout(300)

            if i % 5 == 4:
                page.evaluate('window.__goldbox_collect()')
                total = page.evaluate('Object.keys(window.__goldbox_items).length')

                if i % 15 == 14:
                    print(f'[GOLDBOX] 스크롤 {i+1}회, 누적: {total}개')

                if total == prev_total:
                    no_change += 1
                    if no_change >= 6:
                        break
                else:
                    no_change = 0
                prev_total = total

        page.evaluate('window.__goldbox_collect()')
        products = page.evaluate('Object.values(window.__goldbox_items)')
        print(f'[GOLDBOX] 수집 완료: {len(products)}개')
        return products

    except Exception as e:
        print(f'[GOLDBOX] 크롤링 에러: {e}')
        import traceback
        traceback.print_exc()
        return []
    finally:
        browser.close()
        pw.stop()


# === 노이즈 키워드 필터 ===
def _is_noise_keyword(keyword: str) -> bool:
    """브랜드명, 제품명, 정보성 키워드 필터링"""
    kw = keyword.lower().replace(' ', '')

    # 정보성 키워드 패턴
    info_patterns = ['추천', '순위', '비교', '후기', '리뷰', '가격', '할인', '세일',
                     '감사제', '블프', '블랙프라이데이', '쿠폰', '최저가', '사용법',
                     '차이', '효과', '부작용', '성분', '만들기', '방법', 'vs']

    # 브랜드/스토어 패턴
    brand_patterns = ['다이소', '이케아', '무인양품', '유니클로', '코스트코', '올리브영',
                      '쿠팡', '네이버', '당근', '오늘의집', '마켓컬리']

    for p in info_patterns:
        if p in kw:
            return True

    for p in brand_patterns:
        if p in kw:
            return True

    # 너무 긴 키워드 (구체적 제품명일 가능성)
    if len(keyword.replace(' ', '')) > 15:
        return True

    # 영문만 있는 키워드 (브랜드명일 가능성)
    import re
    if re.match(r'^[a-zA-Z0-9\s]+$', keyword) and len(keyword) > 3:
        return True

    return False


# === 자동 스캔 ===
_auto_scan_state = {
    'running': False,
    'phase': '',           # expanding / filtering / scanning
    'seed_keywords': [],
    'candidates': [],      # 필터링된 후보 키워드
    'scanned': 0,
    'total': 0,
    'current_keyword': '',
    'results': [],         # 완료된 스캔 결과
    'errors': [],
}


@app.route('/api/autoscan/start', methods=['POST'])
def api_autoscan_start():
    """자동 스캔 시작"""
    if _auto_scan_state['running']:
        return jsonify({'success': False, 'error': '이미 스캔 진행 중입니다'})

    data = request.get_json(silent=True) or {}
    seeds = data.get('seeds', [])
    min_search = data.get('min_search', 3000)   # 최소 검색량
    max_scan = data.get('max_scan', 30)          # 최대 윙 스캔 수

    if not seeds:
        return jsonify({'success': False, 'error': '시드 키워드를 입력해주세요'})

    # 상태 초기화
    _auto_scan_state.update({
        'running': True,
        'phase': 'expanding',
        'seed_keywords': seeds,
        'candidates': [],
        'scanned': 0,
        'total': 0,
        'current_keyword': '',
        'results': [],
        'errors': [],
    })

    thread = threading.Thread(
        target=_run_autoscan,
        args=(seeds, min_search, max_scan),
        daemon=True
    )
    thread.start()

    return jsonify({
        'success': True,
        'message': f'시드 {len(seeds)}개로 자동 스캔 시작!'
    })


@app.route('/api/autoscan/status')
def api_autoscan_status():
    """자동 스캔 진행 상태"""
    return jsonify({
        'success': True,
        **{k: v for k, v in _auto_scan_state.items() if k != 'results'},
        'result_count': len(_auto_scan_state['results']),
    })


@app.route('/api/autoscan/results')
def api_autoscan_results():
    """자동 스캔 결과 (기회점수 순)"""
    results = sorted(
        _auto_scan_state['results'],
        key=lambda r: r.get('score', 0),
        reverse=True
    )
    return jsonify({'success': True, 'results': results})


@app.route('/api/autoscan/stop', methods=['POST'])
def api_autoscan_stop():
    """자동 스캔 중지"""
    _auto_scan_state['running'] = False
    return jsonify({'success': True, 'message': '스캔 중지됨'})


def _run_autoscan(seeds: list, min_search: int, max_scan: int):
    """자동 스캔 백그라운드 실행"""
    with app.app_context():
        try:
            # ── Phase 1: 연관키워드 확장 ──
            _auto_scan_state['phase'] = 'expanding'
            api = get_helpstore()

            all_keywords = {}  # keyword → {search, competition, product_count}

            # 시드 키워드 전처리: "속옷/잠옷" → ["속옷", "잠옷"]
            expanded_seeds = []
            for seed in seeds:
                parts = [p.strip() for p in seed.replace('/', ' ').replace('>', ' ').replace(',', ' ').split() if p.strip()]
                expanded_seeds.extend(parts)
            expanded_seeds = list(dict.fromkeys(expanded_seeds))  # 중복 제거

            for seed in expanded_seeds:
                if not _auto_scan_state['running']:
                    break
                _auto_scan_state['current_keyword'] = f'확장: {seed}'

                related = api.get_related_keywords(seed)
                for kw in related:
                    if kw.keyword not in all_keywords:
                        all_keywords[kw.keyword] = {
                            'keyword': kw.keyword,
                            'search': kw.total_search,
                            'competition': kw.competition,
                            'product_count': kw.product_count,
                            'is_brand': kw.is_brand,
                            'seed': seed,
                        }

                import time
                time.sleep(1)  # API 부하 방지

            if not _auto_scan_state['running']:
                return

            # ── Phase 2: 필터링 ──
            _auto_scan_state['phase'] = 'filtering'

            # 필터링: 브랜드/제품명/정보성 키워드 제외
            candidates = []
            for kw in all_keywords.values():
                if kw['search'] < min_search:
                    continue
                if kw.get('is_brand'):  # 헬프스토어 브랜드 플래그
                    continue
                if kw['product_count'] < 50:  # 상품수 너무 적으면 브랜드/제품명
                    continue
                if _is_noise_keyword(kw['keyword']):
                    continue
                candidates.append(kw)

            # 검색량/상품수 비율 높은 순 정렬 (수요>공급)
            for c in candidates:
                c['ratio'] = c['search'] / max(c['product_count'], 1)
            candidates.sort(key=lambda x: x['ratio'], reverse=True)

            # 상위 N개만 스캔
            candidates = candidates[:max_scan]
            _auto_scan_state['candidates'] = candidates
            _auto_scan_state['total'] = len(candidates)

            print(f'[AUTO-SCAN] 연관키워드 {len(all_keywords)}개 → 후보 {len(candidates)}개 선별')

            # ── Phase 3: 윙 스캔 ──
            _auto_scan_state['phase'] = 'scanning'

            for i, cand in enumerate(candidates):
                if not _auto_scan_state['running']:
                    break

                keyword = cand['keyword']
                _auto_scan_state['current_keyword'] = keyword
                _auto_scan_state['scanned'] = i

                try:
                    # 윙 스캔 실행
                    scan_id = fdb.create_scan(keyword, 'auto', 'scanning')

                    products = wing_search(keyword)

                    # 상품 저장
                    for p in products:
                        fdb.add_product(scan_id, {
                            'ranking': p.ranking, 'product_name': p.product_name,
                            'brand': p.brand, 'manufacturer': p.manufacturer,
                            'price': p.price, 'sales_monthly': p.sales_monthly,
                            'revenue_monthly': p.revenue_monthly, 'review_count': p.review_count,
                            'click_count': p.click_count, 'conversion_rate': p.conversion_rate,
                            'page_views': p.page_views, 'category': p.category,
                            'category_code': p.category_code, 'product_url': p.product_url,
                        })

                    # 기회점수
                    opp = calculate_opportunity(
                        products=products,
                        related_keywords=api.get_related_keywords(keyword),
                        keyword=keyword
                    )

                    # DB 업데이트
                    fdb.update_scan(scan_id,
                        status='scanned',
                        category=products[0].category if products else '',
                        opportunity_score=round(opp.total_score, 1),
                        top10_avg_revenue=opp.top4_10_avg_revenue,
                        top10_avg_sales=opp.top4_10_avg_sales,
                        top10_avg_price=opp.top4_10_avg_price,
                        revenue_concentration=round(opp.top3_share * 100, 1),
                        revenue_equality=round(opp.sellers_over_3m_rate * 100, 1),
                        new_product_rate=round(opp.new_product_rate * 100, 1),
                        ad_dependency=round(opp.avg_new_product_weight, 1),
                        recommended_keyword=opp.recommended_keyword,
                    )

                    _auto_scan_state['results'].append({
                        'scan_id': scan_id,
                        'keyword': keyword,
                        'score': round(opp.total_score, 1),
                        'grade': opp.grade,
                        'top3_share': round(opp.top3_share * 100, 1),
                        'sellers_3m': opp.sellers_over_3m,
                        'sellers_3m_rate': round(opp.sellers_over_3m_rate * 100, 1),
                        'entry_revenue': opp.top4_10_avg_revenue,
                        'new_weight': round(opp.avg_new_product_weight, 1),
                        'products': len(products),
                        'seed': cand['seed'],
                        'search_volume': cand['search'],
                    })

                    print(f'[AUTO-SCAN] {i+1}/{len(candidates)} {keyword} → {opp.total_score:.1f} ({opp.grade})')

                except Exception as e:
                    error_msg = str(e)
                    _auto_scan_state['errors'].append(f'{keyword}: {error_msg}')
                    print(f'[AUTO-SCAN] 에러: {keyword} — {error_msg}')

                    if 'LOGIN_REQUIRED' in error_msg:
                        _auto_scan_state['phase'] = 'login_required'
                        break

                import time
                time.sleep(2)  # 요청 간격

            _auto_scan_state['scanned'] = len(candidates)
            _auto_scan_state['phase'] = 'done'

        except Exception as e:
            import traceback
            traceback.print_exc()
            _auto_scan_state['phase'] = 'error'
            _auto_scan_state['errors'].append(str(e))
        finally:
            _auto_scan_state['running'] = False
            print(f'[AUTO-SCAN] 완료! 결과 {len(_auto_scan_state["results"])}개')


# === 헬프스토어 캡처 (북마클릿) ===
@app.route('/api/scan/import', methods=['POST'])
def api_scan_import():
    """
    헬프스토어 페이지에서 북마클릿으로 수집된 데이터를 받아 분석.
    CDP/확장 프로그램 없이, 사용자가 직접 헬프스토어에서 검색 후
    북마클릿 클릭 한번으로 데이터를 가져옴.
    """
    data = request.json
    keyword = data.get('keyword', '').strip()
    raw_products = data.get('products', [])

    if not keyword:
        return jsonify({'success': False, 'error': '키워드가 없습니다'})
    if not raw_products:
        return jsonify({'success': False, 'error': '상품 데이터가 없습니다'})

    # 스캔 레코드 생성
    scan_id = fdb.create_scan(keyword, 'capture', 'scanning')

    # 백그라운드에서 처리 (API 키워드 데이터 수집 + 기회점수)
    thread = threading.Thread(
        target=_run_scan_import,
        args=(scan_id, keyword, raw_products)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'success': True,
        'scan_id': scan_id,
        'products': len(raw_products),
        'message': f'"{keyword}" 상품 {len(raw_products)}개 수신 — 분석 시작!'
    })


def _run_scan_import(scan_id: int, keyword: str, raw_products: list):
    """북마클릿에서 받은 상품 데이터 + 서버 API 키워드 데이터 → 기회점수 산출"""
    with app.app_context():
        try:
            # 1. 상품 데이터를 CoupangProduct로 변환 + DB 저장
            products = []
            for i, rp in enumerate(raw_products):
                p = CoupangProduct(
                    ranking=rp.get('ranking', i + 1),
                    product_name=rp.get('name', ''),
                    brand=rp.get('brand', ''),
                    manufacturer=rp.get('manufacturer', ''),
                    price=int(rp.get('price', 0)),
                    sales_monthly=int(rp.get('sales', 0)),
                    revenue_monthly=int(rp.get('revenue', 0)),
                    review_count=int(rp.get('reviews', 0)),
                    click_count=int(rp.get('clicks', 0)),
                    conversion_rate=float(rp.get('cvr', 0)),
                    page_views=int(rp.get('clicks', 0)),
                    category=rp.get('category', ''),
                    category_code=rp.get('categoryCode', ''),
                    product_url=rp.get('url', ''),
                )
                # 매출 계산
                if p.revenue_monthly == 0 and p.sales_monthly > 0 and p.price > 0:
                    p.revenue_monthly = p.sales_monthly * p.price
                products.append(p)

                fdb.add_product(scan_id, {
                    'ranking': p.ranking, 'product_name': p.product_name,
                    'brand': p.brand, 'manufacturer': p.manufacturer,
                    'price': p.price, 'sales_monthly': p.sales_monthly,
                    'revenue_monthly': p.revenue_monthly, 'review_count': p.review_count,
                    'click_count': p.click_count, 'conversion_rate': p.conversion_rate,
                    'page_views': p.page_views, 'category': p.category,
                    'category_code': p.category_code, 'product_url': p.product_url,
                })

            # 2. 서버 API로 키워드 데이터 수집 (연관키워드/검색량)
            api = get_helpstore()
            api_result = api.search_keyword(keyword)

            for kw in api_result.related_keywords:
                fdb.add_inflow_keyword(scan_id, {
                    'keyword': kw.keyword, 'search_volume': kw.total_search,
                    'click_count': kw.pc_search + kw.mobile_search,
                    'click_rate': (kw.pc_click_rate + kw.mobile_click_rate) / 2,
                    'ad_weight': 0,
                })

            # 3. 띄어쓰기 변형 키워드
            _save_keyword_variants(scan_id, keyword, api_result.related_keywords)

            # 4. 기회점수 산출 (실제 쿠팡 데이터 기반!)
            opp_score = calculate_opportunity(
                products=products,
                inflow_keywords=[],
                related_keywords=api_result.related_keywords,
                keyword=keyword
            )

            # 5. 스캔 결과 업데이트
            fdb.update_scan(scan_id,
                status='scanned',
                category=api_result.main_category,
                opportunity_score=round(opp_score.total_score, 1),
                top10_avg_revenue=opp_score.top10_avg_revenue,
                top10_avg_sales=opp_score.top10_avg_sales,
                top10_avg_price=opp_score.top10_avg_price,
                revenue_concentration=round(opp_score.top1_share * 100, 1),
                revenue_equality=round(opp_score.revenue_equality * 100, 1),
                new_product_rate=round(opp_score.new_product_rate * 100, 1),
                ad_dependency=round(opp_score.ad_dependency, 1),
                recommended_keyword=opp_score.recommended_keyword,
            )

            print(
                f'[SCAN-CAPTURE] 완료: {keyword}\n'
                f'  기회점수: {opp_score.total_score:.1f} ({opp_score.grade})\n'
                f'  상품: {len(products)}개\n'
                f'  상위10 평균매출: {opp_score.top10_avg_revenue:,}원\n'
                f'  1위점유율: {opp_score.top1_share*100:.1f}% | 매출균등도: {opp_score.revenue_equality*100:.1f}%'
            )

        except Exception as e:
            import traceback
            print(f'[SCAN-CAPTURE] 에러: {keyword} — {e}')
            traceback.print_exc()
            fdb.update_scan(scan_id, status='failed')


@app.route('/api/scan/<int:scan_id>/poll')
def poll_scan(scan_id):
    """스캔 진행 상태 폴링"""
    scan = fdb.get_scan(scan_id)
    if not scan:
        return jsonify({'success': False})
    return jsonify({'success': True, 'scan': scan})


@app.route('/api/scans')
def get_scans():
    """시장조사 목록 조회"""
    scans = fdb.list_scans()
    return jsonify({'success': True, 'scans': scans})


@app.route('/api/scan/<int:scan_id>')
def get_scan_detail(scan_id):
    """시장조사 상세 (상품 + 키워드 포함)"""
    scan = fdb.get_scan(scan_id)
    if not scan:
        return jsonify({'success': False, 'error': '조사 기록 없음'})

    products = fdb.get_products(scan_id)
    keywords = fdb.get_inflow_keywords(scan_id)
    variants = fdb.get_keyword_variants(scan_id)

    return jsonify({
        'success': True,
        'scan': scan,
        'products': products,
        'keywords': keywords,
        'variants': variants,
    })


# === 쿠팡 키워드 API ===
_coupang_kw_cache = {}  # keyword → {autocomplete, related, ts}

@app.route('/api/scan/<int:scan_id>/keywords')
def api_scan_keywords(scan_id):
    """스캔 키워드 데이터 통합 반환 (변형 + 쿠팡 자동완성 + 연관)"""
    scan = fdb.get_scan(scan_id)
    if not scan:
        return jsonify({'success': False, 'error': '조사 기록 없음'})

    keyword = scan['keyword']

    # DB에서 키워드 변형 조회
    variants = fdb.get_keyword_variants(scan_id)

    # 쿠팡 자동완성/연관 — 캐시 확인
    import time
    cached = _coupang_kw_cache.get(keyword)
    if cached and (time.time() - cached.get('ts', 0)) < 3600:
        autocomplete = cached['autocomplete']
        related = cached['related']
    else:
        # 헬프스토어 API로 연관 키워드 수집 (Wing 워커 데드락 방지)
        try:
            api = get_helpstore()
            related_kws = api.get_related_keywords(keyword)
            autocomplete = [kw.keyword for kw in related_kws[:15]
                           if kw.total_search >= 1000 and not kw.is_brand]
            related = [kw.keyword for kw in related_kws[15:30]
                      if kw.total_search >= 500]
            _coupang_kw_cache[keyword] = {
                'autocomplete': autocomplete,
                'related': related,
                'ts': time.time()
            }
        except Exception as e:
            print(f'[KEYWORDS] 키워드 수집 실패: {e}')
            autocomplete = []
            related = []

    return jsonify({
        'success': True,
        'variants': variants,
        'autocomplete': autocomplete,
        'related': related
    })


# === 리뷰 분석 ===
_review_state = {}  # scan_id → {status, reviews, analysis}


@app.route('/api/scan/<int:scan_id>/reviews', methods=['POST'])
def api_scan_reviews(scan_id):
    """스캔의 상위 상품 리뷰 수집 + 분석"""
    if scan_id in _review_state and _review_state[scan_id].get('status') == 'analyzing':
        return jsonify({'success': True, 'message': '이미 분석 중...'})

    data = request.get_json(silent=True) or {}
    from analyzer.reviews import ANTHROPIC_API_KEY
    api_key = data.get('api_key', '') or ANTHROPIC_API_KEY

    _review_state[scan_id] = {'status': 'collecting', 'reviews': [], 'analysis': None}

    thread = threading.Thread(
        target=_run_review_analysis,
        args=(scan_id, api_key),
        daemon=True
    )
    thread.start()

    return jsonify({'success': True, 'message': '리뷰 수집 시작!'})


@app.route('/api/scan/<int:scan_id>/reviews')
def api_get_reviews(scan_id):
    """리뷰 분석 결과 조회 — 메모리 우선, 없으면 DB에서 로드"""
    state = _review_state.get(scan_id)
    if not state or state.get('status') == 'none':
        db_state = fdb.load_reviews_from_db(scan_id)
        if db_state:
            _review_state[scan_id] = db_state
            state = db_state
    if not state:
        state = {}
    return jsonify({
        'success': True,
        'status': state.get('status', 'none'),
        'review_count': len(state.get('reviews', [])),
        'analysis': state.get('analysis'),
    })


@app.route('/api/reviews/import', methods=['POST', 'OPTIONS'])
def api_reviews_import():
    """크롬 확장프로그램에서 수집된 리뷰 데이터 수신"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True})

    data = request.get_json(silent=True) or {}
    scan_id = data.get('scan_id')
    reviews = data.get('reviews', [])

    partial = data.get('partial', False)

    if not scan_id:
        return jsonify({'success': False, 'error': 'scan_id 필요'})
    if not reviews and not partial:
        return jsonify({'success': False, 'error': 'reviews 필요'})

    # scan_id를 int로 변환
    try:
        scan_id = int(scan_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'scan_id는 정수여야 합니다'})

    # partial 모드: 이전 리뷰에 추가
    product_name = data.get('product_name', '')
    if partial and scan_id in _review_state and _review_state[scan_id].get('reviews'):
        _review_state[scan_id]['reviews'].extend(reviews)
        _review_state[scan_id]['status'] = 'collecting'
        if 'by_product' not in _review_state[scan_id]:
            _review_state[scan_id]['by_product'] = {}
        if product_name and reviews:
            _review_state[scan_id]['by_product'][product_name] = len(reviews)
        product_index = data.get('product_index', 0)
        total_products = data.get('total_products', 1)
        print(f'[REVIEW-IMPORT] {product_name[:20]} → {len(reviews)}개 (상품 {product_index+1}/{total_products}, 누적 {len(_review_state[scan_id]["reviews"])}개)')

        # 마지막 상품이면 분석 시작
        if product_index >= total_products - 1:
            reviews = _review_state[scan_id]['reviews']
        else:
            return jsonify({'success': True, 'message': f'부분 수신 ({product_index+1}/{total_products})', 'review_count': len(_review_state[scan_id]["reviews"])})

    # 리뷰 저장 + 분석 시작
    _review_state[scan_id] = {
        'status': 'analyzing',
        'reviews': reviews,
        'analysis': None
    }

    # 키워드 조회
    keyword = ''
    scan = fdb.get_scan(scan_id)
    if scan:
        keyword = scan['keyword']

    # DB에 리뷰 저장
    fdb.save_reviews(scan_id, reviews)

    from analyzer.reviews import ANTHROPIC_API_KEY
    api_key = ANTHROPIC_API_KEY

    def _analyze():
        try:
            if api_key:
                analysis = analyze_reviews_claude(reviews, keyword, api_key)
            else:
                analysis = analyze_reviews_basic(reviews, keyword)
            _review_state[scan_id]['analysis'] = analysis
            _review_state[scan_id]['status'] = 'done'
            # 분석 결과도 DB에 저장
            fdb.save_review_analysis(scan_id, keyword, len(reviews), analysis)
            print(f'[REVIEW-IMPORT] 분석 완료: {keyword} ({len(reviews)}개 리뷰)')
        except Exception as e:
            import traceback
            traceback.print_exc()
            _review_state[scan_id]['status'] = 'error'
            _review_state[scan_id]['analysis'] = {'error': str(e)}

    threading.Thread(target=_analyze, daemon=True).start()

    return jsonify({
        'success': True,
        'message': f'{len(reviews)}개 리뷰 수신, AI 분석 시작',
        'review_count': len(reviews)
    })


def _run_review_analysis(scan_id: int, api_key: str = ''):
    """리뷰 수집 → 분석 백그라운드"""
    with app.app_context():
        try:
            scan = fdb.get_scan(scan_id)
            if not scan:
                _review_state[scan_id] = {'status': 'error', 'reviews': [], 'analysis': None}
                return

            keyword = scan['keyword']
            products = fdb.get_products(scan_id)[:10]

            if not products:
                _review_state[scan_id] = {'status': 'error', 'reviews': [], 'analysis': {'error': '상품 데이터 없음'}}
                return

            # 리뷰 수집 — Wing 워커 큐로 (스캔 완료 후라 워커 비어있음)
            _review_state[scan_id]['status'] = 'collecting'
            from analyzer.wing import _send
            import time as _time

            all_reviews = []
            for p in products[:10]:
                url = p['product_url']
                if not url:
                    continue
                try:
                    reviews = _send('collect_reviews', {
                        'product_url': url,
                        'max_reviews': 100
                    }, timeout=60)
                    if reviews:
                        all_reviews.extend(reviews)
                        print(f'[REVIEW] {p["product_name"][:20]} → {len(all_reviews)}개 누적')
                except Exception as e:
                    print(f'[REVIEW] 실패: {p["product_name"][:20]} — {e}')
                _time.sleep(0.5)

            _review_state[scan_id]['reviews'] = all_reviews
            print(f'[REVIEW] 총 {len(all_reviews)}개 리뷰 수집 완료')

            # 분석
            _review_state[scan_id]['status'] = 'analyzing'
            if api_key:
                analysis = analyze_reviews_claude(all_reviews, keyword, api_key)
            else:
                analysis = analyze_reviews_basic(all_reviews, keyword)

            _review_state[scan_id]['analysis'] = analysis
            _review_state[scan_id]['status'] = 'done'
            # DB에 리뷰 + 분석 저장
            fdb.save_reviews(scan_id, all_reviews)
            fdb.save_review_analysis(scan_id, keyword, len(all_reviews), analysis)
            print(f'[REVIEW] 분석 완료: {keyword}')

        except Exception as e:
            import traceback
            traceback.print_exc()
            _review_state[scan_id] = {
                'status': 'error',
                'reviews': _review_state.get(scan_id, {}).get('reviews', []),
                'analysis': {'error': str(e)}
            }


def _collect_reviews_direct(products) -> list:
    """별도 Playwright로 리뷰 수집 (Wing 워커와 독립)"""
    from playwright.sync_api import sync_playwright
    import re, time

    all_reviews = []
    is_server = os.environ.get('DOCKER_ENV') == '1'
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=is_server,
        args=['--disable-blink-features=AutomationControlled', '--window-position=-2000,-2000']
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    )
    page = context.new_page()

    try:
        for p in products[:10]:
            url = p['product_url']
            if not url:
                continue
            pid_match = re.search(r'products/(\d+)', url)
            if not pid_match:
                continue
            pid = pid_match.group(1)

            try:
                # 상품 상세 페이지에 먼저 접속하여 쿠키/세션 컨텍스트 확보
                page.goto(url, wait_until='domcontentloaded', timeout=15000)
                page.wait_for_timeout(3000)

                for pg in range(1, 6):  # 최대 5페이지 = 100개
                    result = page.evaluate(f'''() => {{
                        return new Promise(resolve => {{
                            fetch('/next-api/review?productId={pid}&page={pg}&size=20&sortBy=DATE_DESC&ratingSummary=true', {{
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

                    review_list = result.get('data', {}).get('reviews', [])
                    for r in review_list:
                        all_reviews.append({
                            'rating': r.get('rating', 0),
                            'headline': r.get('headline', ''),
                            'content': r.get('content', ''),
                        })

                    if len(review_list) < 20:
                        break
                    time.sleep(0.3)

                print(f'[REVIEW] {p["product_name"][:20]} → {len(all_reviews)}개 누적')
            except Exception as e:
                print(f'[REVIEW] 수집 실패: {p["product_name"][:20]} — {e}')

            time.sleep(0.5)

    except Exception as e:
        print(f'[REVIEW] 크롤링 에러: {e}')
    finally:
        context.close()
        browser.close()
        pw.stop()

    print(f'[REVIEW] 총 {len(all_reviews)}개 수집 완료')
    return all_reviews


def _load_all_reviews_from_db():
    """서버 시작 시 DB에서 모든 리뷰 상태 로드"""
    global _review_state
    try:
        _review_state = fdb.load_all_reviews()
    except Exception as e:
        print(f'[REVIEW-DB] 리뷰 로드 실패 (앱은 정상 시작): {e}')
        _review_state = {}


@app.route('/api/scan/<int:scan_id>/reviews/chat', methods=['POST'])
def api_review_chat(scan_id):
    """리뷰 Q&A 채팅 — Claude Haiku로 질문 답변"""
    data = request.get_json(silent=True) or {}
    question = data.get('question', '').strip()
    if not question:
        return jsonify({'error': '질문을 입력해주세요.'})

    # DB에서 리뷰 로드 (메모리에 없으면)
    state = _review_state.get(scan_id)
    if not state or not state.get('reviews'):
        state = fdb.load_reviews_from_db(scan_id)
    if not state or not state.get('reviews'):
        return jsonify({'error': '리뷰 데이터가 없습니다. 먼저 리뷰 분석을 실행해주세요.'})

    reviews = state['reviews']

    # 키워드 조회
    keyword = ''
    scan = fdb.get_scan(scan_id)
    if scan:
        keyword = scan['keyword']

    # 리뷰 텍스트 조합
    review_texts = []
    for i, r in enumerate(reviews[:200], 1):  # 최대 200개
        parts = []
        if r.get('rating'):
            parts.append(f"평점:{r['rating']}")
        if r.get('headline'):
            parts.append(r['headline'])
        if r.get('content'):
            parts.append(r['content'])
        if parts:
            review_texts.append(f"{i}. {' | '.join(parts)}")

    review_block = '\n'.join(review_texts)

    prompt = f"""당신은 쿠팡 "{keyword}" 카테고리 제품 전문가입니다.
상위 판매 상품 {len(reviews)}개의 소비자 리뷰를 모두 읽었습니다.

[리뷰 데이터]
{review_block}

[사용자 질문]
{question}

위 리뷰 데이터를 참고하여 사용자의 질문에 자연스럽게 대화하듯 답해주세요.
- 질문이 인사면 간단히 인사하고 리뷰에서 알 수 있는 것을 안내해주세요.
- 질문이 구체적이면 리뷰 근거를 들어 답해주세요.
- 이모지나 마크다운은 사용하지 마세요.
- 한국어로 답해주세요."""

    # Gemini Flash API 호출 (무료)
    from analyzer.reviews import GEMINI_API_KEY, _call_gemini
    if not GEMINI_API_KEY:
        return jsonify({'error': 'GEMINI_API_KEY가 설정되지 않았습니다.'})

    try:
        answer = _call_gemini(prompt, max_tokens=1024)
        if answer:
            return jsonify({'answer': answer})
        else:
            return jsonify({'error': 'AI 응답이 비어있습니다.'})
    except Exception as e:
        return jsonify({'error': f'API 호출 실패: {str(e)}'})


@app.route('/api/scan/<int:scan_id>/reanalyze-reviews', methods=['POST'])
def reanalyze_reviews(scan_id):
    """기존 수집된 리뷰로 AI 재분석 (재수집 없이)"""
    state = _review_state.get(scan_id)
    if not state:
        db_state = fdb.load_reviews_from_db(scan_id)
        if db_state:
            _review_state[scan_id] = db_state
            state = db_state

    if not state or not state.get('reviews'):
        return jsonify({'success': False, 'error': '저장된 리뷰가 없습니다'})

    reviews = state['reviews']
    scan = fdb.get_scan(scan_id)
    keyword = scan['keyword'] if scan else ''

    _review_state[scan_id]['status'] = 'analyzing'

    def _run():
        with app.app_context():
            try:
                from analyzer.reviews import analyze_reviews_claude, ANTHROPIC_API_KEY
                analysis = analyze_reviews_claude(reviews, keyword, ANTHROPIC_API_KEY)
                _review_state[scan_id]['analysis'] = analysis
                _review_state[scan_id]['status'] = 'done'
                fdb.save_review_analysis(scan_id, keyword, len(reviews), analysis)
                print(f'[REANALYZE] 완료: {keyword} ({len(reviews)}개)')
            except Exception as e:
                import traceback; traceback.print_exc()
                _review_state[scan_id]['status'] = 'error'

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'success': True, 'message': f'{len(reviews)}개 리뷰 AI 재분석 시작!'})


@app.route('/api/scan/<int:scan_id>/status', methods=['PUT'])
def update_scan_status(scan_id):
    """스캔 상태 변경 (go / pass)"""
    data = request.get_json(silent=True) or {}
    status = data.get('status')
    fdb.update_scan(scan_id, status=status)
    return jsonify({'success': True})


# === 기회분석 API ===
@app.route('/api/opportunities')
def get_opportunities():
    """기회점수 랭킹 조회"""
    status_filter = request.args.get('status', '')
    scans = fdb.get_opportunities(status_filter)
    return jsonify({'success': True, 'opportunities': scans})


# === RFQ API ===
@app.route('/api/rfq', methods=['POST'])
def create_rfq():
    """RFQ 생성"""
    data = request.json
    rfq_id = fdb.create_rfq(
        scan_id=data.get('scan_id'),
        product_name_en=data.get('product_name_en'),
        product_name_kr=data.get('product_name_kr'),
        category=data.get('category'),
        specifications=json.dumps(data.get('specifications', {})),
        target_price=data.get('target_price'),
        order_quantity=data.get('order_quantity'),
        moq=data.get('moq'),
        shipping_terms=data.get('shipping_terms', 'FOB'),
        certifications=json.dumps(data.get('certifications', [])),
    )
    return jsonify({'success': True, 'rfq_id': rfq_id})


@app.route('/api/scan/<int:scan_id>/rfq/generate', methods=['POST'])
def generate_rfq_from_scan(scan_id):
    """GO 판정된 스캔의 상품 데이터를 분석하여 RFQ 자동 생성"""
    # 스캔 조회
    scan_dict = fdb.get_scan(scan_id)
    if not scan_dict:
        return jsonify({'success': False, 'error': '스캔을 찾을 수 없습니다'})

    if scan_dict.get('status') != 'go':
        return jsonify({'success': False, 'error': 'GO 판정된 스캔만 RFQ 생성이 가능합니다'})

    # 상위 40개 상품 조회
    products = fdb.get_products(scan_id)[:40]

    if not products:
        return jsonify({'success': False, 'error': '상품 데이터가 없습니다'})

    # ── 1. 구성 분석: 상품명에서 수량/구성 패턴 추출 ──
    comp_pattern = re.compile(r'(\d+)\s*(개입|매입|P|종|장|개|매|팩|세트|묶음)', re.IGNORECASE)
    composition_groups = {}  # {"10개입": [products...]}

    for p in products:
        name = p.get('product_name', '') or ''
        matches = comp_pattern.findall(name)
        if matches:
            # 첫 번째 매치 사용
            qty, unit = matches[0]
            comp_key = f"{qty}{unit}"
        else:
            comp_key = '단품'

        if comp_key not in composition_groups:
            composition_groups[comp_key] = []
        composition_groups[comp_key].append(p)

    composition_analysis = []
    for comp, items in sorted(composition_groups.items(), key=lambda x: len(x[1]), reverse=True):
        revenues = [i.get('revenue_monthly', 0) or 0 for i in items]
        reviews = [i.get('review_count', 0) or 0 for i in items]
        composition_analysis.append({
            'composition': comp,
            'count': len(items),
            'avg_revenue': int(sum(revenues) / len(revenues)) if revenues else 0,
            'avg_reviews': int(sum(reviews) / len(reviews)) if reviews else 0
        })

    # ── 2. AI 스펙 작성 (Claude Haiku) ──
    top10 = products[:10]
    top10_names = [p.get('product_name', '') for p in top10]

    ai_specs = None
    recommended_composition = composition_analysis[0]['composition'] if composition_analysis else '단품'
    recommendation_reason = '가장 많은 상품이 채택한 구성'
    certifications = []

    # Gemini Flash로 AI 스펙 생성 (무료)
    from analyzer.reviews import GEMINI_API_KEY as _gemini_key, _call_gemini
    if _gemini_key and len(top10_names) > 0:
        try:
            prompt_text = (
                "다음은 쿠팡에서 잘 팔리는 상위 10개 상품명입니다:\n\n"
                + "\n".join(f"{i+1}. {n}" for i, n in enumerate(top10_names))
                + "\n\n이 상품들의 공통 스펙을 정리해주세요. "
                "소재, 사이즈, 색상, 포장, 인증 등을 파악하세요.\n\n"
                "반드시 아래 JSON 형식으로만 답변하세요 (다른 텍스트 없이):\n"
                '{"specs": ["소재: ...", "사이즈: ...", "색상: ..."], '
                '"recommended_composition": "8개입", '
                '"reason": "경쟁 적고 매출 양호", '
                '"certifications": ["KC인증"]}'
            )
            ai_text = _call_gemini(prompt_text, max_tokens=1024)
            if ai_text:
                print(f'[RFQ] AI 스펙 생성 성공: {ai_text[:100]}')
                json_match = re.search(r'\{[\s\S]*\}', ai_text)
                if json_match:
                    ai_result = json.loads(json_match.group())
                    ai_specs = ai_result.get('specs', [])
                    if ai_result.get('recommended_composition'):
                        recommended_composition = ai_result['recommended_composition']
                    if ai_result.get('reason'):
                        recommendation_reason = ai_result['reason']
                    if ai_result.get('certifications'):
                        certifications = ai_result['certifications']
        except Exception as e:
            import traceback, sys
            print(f"[RFQ Generate] AI 스펙 작성 실패: {e}", flush=True)
            traceback.print_exc()
            sys.stdout.flush()

    # ── 3. 목표단가 계산 ──
    req_data = request.get_json(silent=True) or {}
    commission_rate = req_data.get('commission_rate', 0.108)
    target_margin = req_data.get('target_margin', 0.40)
    logistics_cost = req_data.get('logistics_cost', 3000)
    exchange_rate = req_data.get('exchange_rate', 1450)

    # 시장 4~10등 평균 판매가
    ranked_products = sorted(
        [p for p in products if (p.get('revenue_monthly') or 0) > 0],
        key=lambda x: x.get('revenue_monthly', 0),
        reverse=True
    )
    mid_tier = ranked_products[3:10] if len(ranked_products) >= 10 else ranked_products[3:] if len(ranked_products) > 3 else ranked_products
    if mid_tier:
        market_avg_price = int(sum(p.get('price', 0) or 0 for p in mid_tier) / len(mid_tier))
    else:
        market_avg_price = int(sum(p.get('price', 0) or 0 for p in products) / len(products)) if products else 0

    selling_price = market_avg_price
    commission = int(selling_price * commission_rate)
    margin = int(selling_price * target_margin)
    target_cost_krw = selling_price - commission - margin - logistics_cost
    target_cost_krw = max(target_cost_krw, 0)
    target_price_usd = round(target_cost_krw / exchange_rate, 2)

    # 추천 MOQ
    suggested_moq = 1000
    if target_price_usd < 1:
        suggested_moq = 3000
    elif target_price_usd < 3:
        suggested_moq = 1000
    elif target_price_usd < 10:
        suggested_moq = 500
    else:
        suggested_moq = 200

    # ── 4. RFQ 데이터 조립 ──
    rfq_data = {
        'product_name': scan_dict.get('keyword', ''),
        'category': scan_dict.get('category', ''),
        'composition_analysis': composition_analysis,
        'recommended_composition': recommended_composition,
        'recommendation_reason': recommendation_reason,
        'specs': ai_specs or [],
        'certifications': certifications,
        'target_price_usd': target_price_usd,
        'target_price_krw': target_cost_krw,
        'market_avg_price': market_avg_price,
        'suggested_moq': suggested_moq,
        'calculation': {
            'selling_price': selling_price,
            'commission': commission,
            'margin': margin,
            'logistics': logistics_cost,
            'target_cost': target_cost_krw
        }
    }

    return jsonify({'success': True, 'rfq': rfq_data})


@app.route('/api/rfq/save', methods=['POST'])
def save_rfq():
    """RFQ 폼 데이터를 rfqs 테이블에 저장"""
    data = request.get_json(silent=True) or {}

    specs = data.get('specifications') or data.get('specs', [])
    certs = data.get('certifications', [])

    rfq_id = fdb.create_rfq(
        scan_id=data.get('scan_id'),
        product_name_en=data.get('product_name_en', ''),
        product_name_kr=data.get('product_name_kr', data.get('product_name', '')),
        category=data.get('category', ''),
        specifications=json.dumps(specs if isinstance(specs, (list, dict)) else specs, ensure_ascii=False),
        target_price=data.get('target_price') or data.get('target_price_usd'),
        target_price_currency=data.get('target_price_currency', 'USD'),
        order_quantity=data.get('order_quantity') or data.get('suggested_moq'),
        moq=data.get('moq') or data.get('suggested_moq'),
        shipping_terms=data.get('shipping_terms', 'FOB'),
        certifications=json.dumps(certs if isinstance(certs, list) else [certs], ensure_ascii=False),
    )

    return jsonify({'success': True, 'rfq_id': rfq_id})


@app.route('/api/rfqs')
def get_rfqs():
    """RFQ 목록 조회"""
    rfqs = fdb.list_rfqs()
    return jsonify({'success': True, 'rfqs': rfqs})


@app.route('/api/rfq/<int:rfq_id>', methods=['PUT'])
def update_rfq(rfq_id):
    """RFQ 수정"""
    data = request.get_json(silent=True) or {}

    # 존재 확인
    rfq = fdb.get_rfq(rfq_id)
    if not rfq:
        return jsonify({'success': False, 'error': 'RFQ 없음'})

    # certifications: 쉼표 구분 문자열 → JSON 배열로 변환
    certs_raw = data.get('certifications', '')
    if isinstance(certs_raw, str):
        certs = json.dumps([c.strip() for c in certs_raw.split(',') if c.strip()], ensure_ascii=False)
    else:
        certs = json.dumps(certs_raw, ensure_ascii=False)

    fdb.update_rfq(rfq_id,
        product_name_kr=data.get('product_name_kr'),
        product_name_en=data.get('product_name_en'),
        category=data.get('category'),
        specifications=data.get('specifications'),
        target_price=data.get('target_price'),
        order_quantity=data.get('order_quantity'),
        moq=data.get('moq'),
        shipping_terms=data.get('shipping_terms'),
        certifications=certs,
    )
    return jsonify({'success': True})


@app.route('/api/rfq/<int:rfq_id>', methods=['DELETE'])
def delete_rfq(rfq_id):
    """RFQ 삭제"""
    fdb.delete_rfq(rfq_id)
    return jsonify({'success': True})


@app.route('/api/rfq/<int:rfq_id>/publish', methods=['POST'])
def publish_rfq(rfq_id):
    """RFQ 영문 변환 + 알리바바 발행 준비"""
    rfq = fdb.get_rfq(rfq_id)
    if not rfq:
        return jsonify({'success': False, 'error': 'RFQ not found'})
    specs = rfq.get('specifications', '{}')
    try:
        specs_data = json.loads(specs) if isinstance(specs, str) else specs
    except:
        specs_data = {}

    # Claude로 영문 변환
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        try:
            from analyzer.reviews import ANTHROPIC_API_KEY
            api_key = ANTHROPIC_API_KEY
        except:
            pass

    product_name_kr = rfq.get('product_name_kr', '')
    specs_text = '\n'.join(specs_data.get('specs', [])) if isinstance(specs_data, dict) else str(specs_data)
    certs = specs_data.get('certifications', []) if isinstance(specs_data, dict) else []

    english_data = {
        'product_name_en': product_name_kr,
        'specs_en': specs_text,
        'subject': f'RFQ: {product_name_kr}',
        'message': '',
        'target_price': rfq.get('target_price', 0),
        'quantity': rfq.get('order_quantity', 1000),
        'shipping': rfq.get('shipping_terms', 'FOB'),
    }

    if api_key:
        try:
            import requests as _req
            prompt = f"""Write a concise RFQ email in English for Alibaba. Be polite but get to the point.

Product: {product_name_kr}
Specs: {specs_text}
Certs: {', '.join(certs) if certs else 'N/A'}
Target: ${rfq.get('target_price', 0)}/unit, Qty: {rfq.get('order_quantity', 1000)}pcs, {rfq.get('shipping_terms', 'FOB')}

Keep message under 150 words. Include specs, price, qty, and ask for: unit price, MOQ, sample, lead time.

Sign as: Becore Lab Co., Ltd. (do NOT include email or URLs in the message - Alibaba blocks them)

JSON only:
{{"product_name_en": "...", "subject": "RFQ: ...", "message": "Dear Supplier,\\n\\n...\\n\\nBest regards,\\nBecore Lab Co., Ltd.\\nkychung@becorelab.kr", "specs_en": "..."}}"""

            resp = _req.post(
                'https://api.anthropic.com/v1/messages',
                headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
                json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 2000, 'messages': [{'role': 'user', 'content': prompt}]},
                timeout=30
            )
            if resp.ok:
                ai_text = resp.json()['content'][0]['text']
                import re
                json_match = re.search(r'\{[\s\S]*\}', ai_text)
                if json_match:
                    english_data = json.loads(json_match.group())
        except Exception as e:
            print(f'[RFQ Publish] 번역 실패: {e}')

    # DB 업데이트: 영문명 저장 + 상태 변경
    fdb.update_rfq(rfq_id,
        product_name_en=english_data.get('product_name_en', product_name_kr),
        status='ready',
    )

    return jsonify({
        'success': True,
        'english_rfq': english_data,
        'rfq_id': rfq_id
    })


@app.route('/api/rfq/<int:rfq_id>/auto-publish', methods=['POST'])
def auto_publish_rfq(rfq_id):
    """알리바바에 RFQ 자동 등록 (Playwright headed 모드)"""
    data = request.get_json(silent=True) or {}
    english_message = data.get('message', '')
    product_name = data.get('product_name', '')
    quantity = data.get('quantity', 1000)

    if not english_message:
        return jsonify({'success': False, 'error': '영문 RFQ가 필요합니다. 먼저 발행 버튼을 눌러주세요.'})

    def _publish():
        try:
            from playwright.sync_api import sync_playwright

            ali_profile = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.alibaba_profile')
            os.makedirs(ali_profile, exist_ok=True)

            is_server = os.environ.get('DOCKER_ENV') == '1'
            pw = sync_playwright().start()
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=ali_profile,
                headless=is_server,
                viewport={'width': 1200, 'height': 800},
                args=['--disable-blink-features=AutomationControlled']
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            page.goto('https://rfq.alibaba.com/rfq/rfqForm.htm?newAiForm=true',
                       wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)

            # 로그인 필요하면 대기
            if 'login' in page.url.lower():
                print('[ALIBABA] 로그인 필요 — 브라우저에서 로그인해주세요')
                for _ in range(120):
                    page.wait_for_timeout(1000)
                    if 'login' not in page.url.lower():
                        break
                page.goto('https://rfq.alibaba.com/rfq/rfqForm.htm?newAiForm=true',
                           wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(3000)

            # Product name — 영문명 사용
            en_name = product_name
            # publish API에서 영문명 가져오기
            try:
                from analyzer.reviews import ANTHROPIC_API_KEY as _akey
                if _akey:
                    import requests as _rr
                    _r = _rr.post('https://api.anthropic.com/v1/messages',
                        headers={'x-api-key': _akey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
                        json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 100,
                              'messages': [{'role': 'user', 'content': f'Translate to English product name (short, professional): {product_name}. Reply with just the English name, nothing else.'}]},
                        timeout=10)
                    if _r.ok:
                        en_name = _r.json()['content'][0]['text'].strip().strip('"')
            except:
                pass

            try:
                page.locator('input[placeholder*="enter"], input[placeholder*="roduct"], input[placeholder*="입력"]').first.fill(en_name)
                print(f'[ALIBABA] 제품명 입력: {en_name}')
            except Exception as e:
                print(f'[ALIBABA] 제품명 실패: {e}')

            page.wait_for_timeout(500)

            # Detailed requirements
            try:
                page.locator('textarea').first.fill(english_message)
                print(f'[ALIBABA] 상세 내용 입력 ({len(english_message)}자)')
            except Exception as e:
                print(f'[ALIBABA] 상세 내용 실패: {e}')

            print('[ALIBABA] 폼 채움 완료! 대표님 확인 후 제출해주세요.')

            # 5분간 브라우저 유지
            page.wait_for_timeout(300000)
            ctx.close()
            pw.stop()
        except Exception as e:
            print(f'[ALIBABA] 에러: {e}')
            import traceback
            traceback.print_exc()
            import traceback
            traceback.print_exc()

    import threading
    threading.Thread(target=_publish, daemon=True).start()

    return jsonify({
        'success': True,
        'message': '알리바바 브라우저가 열립니다. 폼이 자동 채워지면 확인 후 제출해주세요.'
    })


@app.route('/api/rfq/<int:rfq_id>')
def get_rfq_detail(rfq_id):
    """RFQ 상세 + 견적 목록"""
    rfq = fdb.get_rfq(rfq_id)
    if not rfq:
        return jsonify({'success': False, 'error': 'RFQ 없음'})

    quotations = fdb.get_quotations(rfq_id)

    return jsonify({
        'success': True,
        'rfq': rfq,
        'quotations': quotations,
    })


# === 견적 API ===
@app.route('/api/quotation', methods=['POST'])
def add_quotation():
    """견적 추가"""
    data = request.json
    quote_id = fdb.add_quotation(
        rfq_id=data.get('rfq_id'),
        supplier_name=data.get('supplier_name'),
        supplier_url=data.get('supplier_url'),
        supplier_rating=data.get('supplier_rating'),
        supplier_years=data.get('supplier_years'),
        unit_price=data.get('unit_price'),
        moq=data.get('moq'),
        lead_time_days=data.get('lead_time_days'),
        sample_cost=data.get('sample_cost'),
        certifications=json.dumps(data.get('certifications', [])),
        notes=data.get('notes'),
    )
    return jsonify({'success': True, 'quotation_id': quote_id})


@app.route('/api/quotation/parse', methods=['POST'])
def parse_quotation():
    """AI로 알리바바 업체 답변 파싱"""
    data = request.get_json(silent=True) or {}
    raw_text = data.get('text', '')
    rfq_id = data.get('rfq_id')

    if not raw_text:
        return jsonify({'success': False, 'error': '견적 텍스트를 입력해주세요'})

    from analyzer.reviews import ANTHROPIC_API_KEY
    api_key = ANTHROPIC_API_KEY

    parsed = {
        'supplier_name': '',
        'unit_price': 0,
        'unit_price_currency': 'USD',
        'moq': 0,
        'lead_time_days': 0,
        'sample_cost': 0,
        'certifications': '',
        'supplier_rating': 0,
        'supplier_years': 0,
        'notes': raw_text[:500]
    }

    if api_key:
        import requests as _req
        prompt = f"""Extract ALL info from this Alibaba supplier quote. Read EVERY line carefully.

{raw_text[:3000]}

Find: company name, price, MOQ, lead time (days), sample cost, certifications, years in business, shipping terms, payment terms.
If "15-20 days" → use 17. If "over 8 years" → use 8.

JSON only (no other text):
{{"supplier_name": "", "unit_price": 0, "currency": "USD", "moq": 0, "lead_time_days": 0, "sample_cost": 0, "certifications": "", "supplier_years": 0, "shipping_terms": "", "notes": ""}}"""

        try:
            resp = _req.post('https://api.anthropic.com/v1/messages',
                headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
                json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 1000,
                      'messages': [{'role': 'user', 'content': prompt}]},
                timeout=30)
            if resp.ok:
                ai_text = resp.json()['content'][0]['text']
                json_match = re.search(r'\{[\s\S]*\}', ai_text)
                if json_match:
                    parsed = json.loads(json_match.group())
        except Exception as e:
            print(f'[QUOTE PARSE] AI 파싱 실패: {e}')

    # 누락 항목 경고
    warnings = []
    if not parsed.get('unit_price'): warnings.append('단가 정보 없음')
    if not parsed.get('moq'): warnings.append('MOQ 정보 없음')
    if not parsed.get('lead_time_days'): warnings.append('리드타임 정보 없음')

    return jsonify({
        'success': True,
        'parsed': parsed,
        'warnings': warnings
    })


@app.route('/api/rfq/<int:rfq_id>/compare')
def compare_quotations(rfq_id):
    """견적 비교 데이터 (AI 점수 산출 포함)"""
    rfq = fdb.get_rfq(rfq_id)
    quotes_list = fdb.get_quotations(rfq_id)

    # AI 점수 산출: 가격(40%) + 신뢰도(25%) + 조건(20%) + 속도(15%)
    if quotes_list:
        prices = [q['unit_price'] for q in quotes_list if q['unit_price']]
        moqs = [q['moq'] for q in quotes_list if q['moq']]
        leads = [q['lead_time_days'] for q in quotes_list if q['lead_time_days']]

        min_price = min(prices) if prices else 1
        max_price = max(prices) if prices else 1
        min_moq = min(moqs) if moqs else 1
        max_moq = max(moqs) if moqs else 1
        min_lead = min(leads) if leads else 1
        max_lead = max(leads) if leads else 1

        for q in quotes_list:
            price_score = (1 - (q['unit_price'] - min_price) / max(max_price - min_price, 0.01)) * 100 if q['unit_price'] else 50
            trust_score = min(100, (q.get('supplier_rating', 0) or 0) * 20 + (q.get('supplier_years', 0) or 0) * 5)
            condition_score = (1 - (q.get('moq', 0) - min_moq) / max(max_moq - min_moq, 1)) * 100 if q.get('moq') else 50
            speed_score = (1 - (q.get('lead_time_days', 0) - min_lead) / max(max_lead - min_lead, 1)) * 100 if q.get('lead_time_days') else 50

            q['total_score'] = round(price_score * 0.4 + trust_score * 0.25 + condition_score * 0.2 + speed_score * 0.15, 1)
            q['price_score'] = round(price_score, 1)
            q['trust_score'] = round(trust_score, 1)
            q['condition_score'] = round(condition_score, 1)
            q['speed_score'] = round(speed_score, 1)

        quotes_list.sort(key=lambda x: x['total_score'], reverse=True)

    # AI 추천
    recommendation = ''
    if quotes_list:
        best = quotes_list[0]
        recommendation = f"{best['supplier_name']}을 추천합니다 (점수 {best['total_score']}점). 단가 ${best['unit_price']}, MOQ {best['moq']}개"

    return jsonify({
        'success': True,
        'rfq': rfq if rfq else {},
        'quotations': quotes_list,
        'recommendation': recommendation
    })


@app.route('/api/quotation/<int:quote_id>', methods=['DELETE'])
def delete_quotation(quote_id):
    """견적 삭제"""
    fdb.delete_quotation(quote_id)
    return jsonify({'success': True})


@app.route('/api/quotation/<int:quote_id>/select', methods=['PUT'])
def select_quotation(quote_id):
    """업체 선정"""
    fdb.select_quotation(quote_id)
    return jsonify({'success': True})


# === 히스토리 API ===
@app.route('/api/history')
def get_history():
    """소싱 히스토리 조회"""
    history = fdb.get_history()
    return jsonify({'success': True, 'history': history})


# === 대시보드 통계 ===
@app.route('/api/stats')
def get_stats():
    """대시보드 통계"""
    stats = fdb.get_stats()
    return jsonify({'success': True, 'stats': stats})


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
if __name__ == '__main__':
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    fdb.init_firestore()
    _load_all_reviews_from_db()
    print("\n[BECORELAB] Market Finder v0.1")
    print("[BECORELAB] http://localhost:8090\n")
    app.run(host='0.0.0.0', port=8090, debug=True, use_reloader=False)
