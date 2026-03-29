"""
비코어랩 쿠팡 소싱콕 — 메인 Flask 앱
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
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 스캔 진척도 추적
_scan_progress = {}  # {scan_id: {'step': 1, 'total': 3, 'message': '...'}}


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
    # PowerShell Invoke-WebRequest 한글 인코딩 대응 (force=True로 charset 무시)
    data = request.get_json(force=True, silent=True) or {}
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
    _scan_progress[scan_id] = {'step': 1, 'total': 3, 'message': '키워드 데이터 수집 중...'}
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

    # 4. 상품 데이터 수집 (윙 서버 시도 → 실패 시 키워드 데이터만)
    _scan_progress[scan_id] = {'step': 2, 'total': 3, 'message': '상품 데이터 수집 중...'}
    products = []
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
        print(f'[SCAN-API] 윙 상품 {len(products)}개 수집 완료')
    except Exception as wing_err:
        print(f'[SCAN-API] 윙 데이터 수집 실패 (키워드 데이터만 사용): {wing_err}')

    # 5. 기회점수 산출 (scoring.py 통일 — UI와 동일한 점수)
    _scan_progress[scan_id] = {'step': 3, 'total': 3, 'message': '기회점수 분석 중...'}
    opp_score = calculate_opportunity(
        products=products,
        inflow_keywords=[],
        related_keywords=result.related_keywords,
        keyword=keyword
    )

    # 6. 스캔 결과 업데이트
    fdb.update_scan(scan_id,
        status='scanned',
        category=result.main_category,
        opportunity_score=round(opp_score.total_score, 1),
        top10_avg_revenue=opp_score.top4_10_avg_revenue,
        top10_avg_sales=opp_score.top4_10_avg_sales,
        top10_avg_price=opp_score.top4_10_avg_price,
        revenue_concentration=round(opp_score.top3_share * 100, 1),
        revenue_equality=round(opp_score.revenue_equality * 100, 1),
        new_product_rate=round(opp_score.new_product_rate * 100, 1),
        ad_dependency=round(opp_score.avg_new_product_weight, 1),
        recommended_keyword=opp_score.recommended_keyword,
    )
    _scan_progress.pop(scan_id, None)
    print(
        f'[SCAN-API] 완료: {keyword}\n'
        f'  기회점수: {opp_score.total_score:.1f} ({opp_score.grade})\n'
        f'  상품 {len(products)}개 | 연관키워드 {len(result.related_keywords)}개'
    )


def _run_scan_cdp(scan_id: int, keyword: str):
    """
    CDP 전체 스캔 — 실제 쿠팡 데이터 (매출/판매량/클릭수/전환율)
    서버 API 데이터 + 브라우저 자동화 데이터 결합
    """
    print(f'[SCAN-CDP] 시작: {keyword} (Chrome CDP 연동)')

    # 전체 스캔 (서버 API + 브라우저 자동화)
    _scan_progress[scan_id] = {'step': 1, 'total': 4, 'message': '쿠팡 실데이터 수집 중...'}
    result = scan_keyword_full_sync(keyword)

    # ─── 상품 데이터 저장 ───
    _scan_progress[scan_id] = {'step': 2, 'total': 4, 'message': f'상품 {len(result.products)}개 저장 중...'}
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
    _scan_progress[scan_id] = {'step': 3, 'total': 4, 'message': '기회점수 분석 중...'}
    opp_score = calculate_opportunity(
        products=result.products,
        inflow_keywords=result.inflow_keywords,
        related_keywords=result.related_keywords,
        keyword=keyword
    )

    # ─── 스캔 결과 업데이트 ───
    _scan_progress[scan_id] = {'step': 4, 'total': 4, 'message': '결과 저장 중...'}
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
    _scan_progress.pop(scan_id, None)


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
                revenue_equality=round(opp_score.revenue_equality * 100, 1),
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


# === 골드박스 자동 스캔 ===
_goldbox_scan_state = {
    'running': False,
    'phase': '',        # extracting / scanning / done / error
    'current': '',
    'scanned': 0,
    'total': 0,
    'results': [],      # [{keyword, scan_id, opportunity_score}]
}


@app.route('/api/goldbox/auto-scan', methods=['POST'])
def api_goldbox_auto_scan():
    """골드박스 상품 → Gemini 키워드 추출 → 순차 스캔 → TOP5"""
    if _goldbox_scan_state['running']:
        return jsonify({'success': False, 'error': '이미 진행 중'})

    data = request.get_json(force=True, silent=True) or {}
    date = data.get('date', '')  # 특정 날짜, 없으면 최신
    delay = int(data.get('delay', 10))  # 스캔 간 대기(초)
    min_search = int(data.get('min_search', 0))  # 최소 검색량 (연관 키워드용, 향후)

    _goldbox_scan_state.update({
        'running': True, 'phase': 'extracting', 'current': '키워드 추출 중...',
        'scanned': 0, 'total': 0, 'results': [],
    })

    thread = threading.Thread(target=_run_goldbox_auto_scan, args=(date, delay), daemon=True)
    thread.start()
    return jsonify({'success': True, 'message': '골드박스 자동 스캔 시작!'})


@app.route('/api/goldbox/auto-scan/status')
def api_goldbox_auto_scan_status():
    return jsonify({
        'success': True,
        'running': _goldbox_scan_state['running'],
        'phase': _goldbox_scan_state['phase'],
        'current': _goldbox_scan_state['current'],
        'scanned': _goldbox_scan_state['scanned'],
        'total': _goldbox_scan_state['total'],
        'results': _goldbox_scan_state['results'],
    })


def _calc_entry_score(scan: dict) -> float:
    """골드박스 진입점수 — 기회점수에 실전 진입 장벽 보정 적용"""
    opp = scan.get('opportunity_score', 0) or 0
    npr = scan.get('new_product_rate', 50) or 0    # 신규진입률 (%)
    rc = scan.get('revenue_concentration', 50) or 0  # 매출집중도 (%)

    # 1) 신규진입률 보정 — 낮으면 기존 브랜드 장악, 진입 어려움
    if npr >= 25:
        npr_mod = 1.0
    elif npr >= 15:
        npr_mod = 0.85
    elif npr >= 10:
        npr_mod = 0.65
    elif npr >= 5:
        npr_mod = 0.35
    else:
        npr_mod = 0.15   # 5% 미만: 사실상 진입 불가

    # 2) 매출집중도 보정 — 상위 셀러 독점이면 진입 어려움
    if rc <= 35:
        rc_mod = 1.0
    elif rc <= 50:
        rc_mod = 0.85
    elif rc <= 65:
        rc_mod = 0.65
    else:
        rc_mod = 0.45    # 65% 초과: 과점 시장

    return round(opp * npr_mod * rc_mod, 1)


@app.route('/api/goldbox/auto-scan/results')
def api_goldbox_auto_scan_results():
    """골드박스 스캔 결과 (DB 기반 — 날짜 필터 지원, 진입점수 포함)"""
    date_filter = request.args.get('date', '')
    scans = fdb.list_scans(limit=500)
    gb_scans = [s for s in scans if s.get('scan_type') == 'goldbox']
    if date_filter:
        gb_scans = [s for s in gb_scans if s.get('scanned_at', '').startswith(date_filter)]
    for s in gb_scans:
        s['entry_score'] = _calc_entry_score(s)
    gb_scans.sort(key=lambda x: x.get('entry_score') or 0, reverse=True)
    return jsonify({
        'success': True,
        'count': len(gb_scans),
        'scans': gb_scans,
    })


def _run_goldbox_auto_scan(date: str, delay: int):
    """골드박스 자동 스캔 메인 로직"""
    import time, re, json as _json
    from analyzer.reviews import _call_gemini

    with app.app_context():
        try:
            # 1. 골드박스 상품명 가져오기
            if date:
                products = fdb.get_goldbox_by_date(date)
            else:
                dates = fdb.get_goldbox_dates()
                if not dates:
                    _goldbox_scan_state.update({'phase': 'error', 'current': '골드박스 데이터 없음'})
                    return
                products = fdb.get_goldbox_by_date(dates[0].get('crawled_date', dates[0]) if isinstance(dates[0], dict) else dates[0])

            names = [p.get('product_name', '') for p in products if p.get('product_name')]
            if not names:
                _goldbox_scan_state.update({'phase': 'error', 'current': '상품명 없음'})
                return

            _goldbox_scan_state['current'] = f'{len(names)}개 상품에서 키워드 추출 중...'
            print(f'[GOLDBOX-SCAN] 상품 {len(names)}개에서 키워드 추출 시작')

            # 2. Gemini로 키워드 추출 (50개씩 나눠서 전체 처리)
            nl = chr(10)
            items = []
            batch_size = 50
            for batch_start in range(0, len(names), batch_size):
                batch = names[batch_start:batch_start + batch_size]
                _goldbox_scan_state['current'] = f'키워드 추출 중... ({batch_start+len(batch)}/{len(names)})'
                numbered = nl.join(f'{i+1}. {n}' for i, n in enumerate(batch))
                prompt = f"""쿠팡 상품명에서 검색 키워드를 추출해주세요.
브랜드명, 용량, 수량, 모델번호 제거. 상품 종류 2~3단어만.
JSON 배열로만 응답: [{{"name":"원래상품명","keyword":"추출결과"}}]

{numbered}"""

                gemini_result = _call_gemini(prompt, max_tokens=4000)
                if not gemini_result:
                    print(f'[GOLDBOX-SCAN] 배치 {batch_start//batch_size+1} Gemini 실패, 스킵')
                    continue

                gemini_result = re.sub(r'```json\s*', '', gemini_result)
                gemini_result = re.sub(r'```\s*', '', gemini_result)
                json_match = re.search(r'\[[\s\S]*\]', gemini_result)
                if json_match:
                    try:
                        items.extend(_json.loads(json_match.group()))
                    except _json.JSONDecodeError:
                        print(f'[GOLDBOX-SCAN] 배치 {batch_start//batch_size+1} JSON 파싱 실패')

            if not items:
                _goldbox_scan_state.update({'phase': 'error', 'current': 'Gemini 키워드 추출 실패'})
                return

            # 키워드→원본 상품명 매핑 (중복 키워드는 상품명 리스트로)
            keyword_sources = {}  # {keyword: [상품명1, 상품명2, ...]}
            for item in items:
                kw = item.get('keyword', '').strip()
                nm = item.get('name', '').strip()
                if kw:
                    if kw not in keyword_sources:
                        keyword_sources[kw] = []
                    if nm and nm not in keyword_sources[kw]:
                        keyword_sources[kw].append(nm)

            keywords = list(keyword_sources.keys())
            print(f'[GOLDBOX-SCAN] 키워드 {len(keywords)}개 추출 (중복 제거)')

            # 3. 이미 스캔한 키워드 스킵
            existing_scans = fdb.list_scans()
            existing_keywords = set(s.get('keyword', '').strip().lower() for s in existing_scans)
            new_keywords = [kw for kw in keywords if kw.strip().lower() not in existing_keywords]
            skipped = len(keywords) - len(new_keywords)
            if skipped > 0:
                print(f'[GOLDBOX-SCAN] 기존 스캔 {skipped}개 스킵, 신규 {len(new_keywords)}개')

            _goldbox_scan_state.update({
                'phase': 'scanning',
                'total': len(new_keywords),
                'current': f'{len(new_keywords)}개 키워드 스캔 시작 (기존 {skipped}개 스킵)',
            })

            # 4. 순차 스캔
            for i, kw in enumerate(new_keywords):
                _goldbox_scan_state['current'] = f'[{i+1}/{len(new_keywords)}] "{kw}" 스캔 중...'
                _goldbox_scan_state['scanned'] = i

                try:
                    scan_id = fdb.create_scan(kw, 'goldbox', 'scanning')
                    _run_scan_api(scan_id, kw)

                    # 기회점수 가져오기 + 원본 상품명 저장
                    scan_data = fdb.get_scan(scan_id)
                    score = scan_data.get('opportunity_score', 0) if scan_data else 0
                    sources = keyword_sources.get(kw, [])
                    if sources:
                        fdb.update_scan(scan_id, source_products=sources)

                    _goldbox_scan_state['results'].append({
                        'keyword': kw,
                        'scan_id': scan_id,
                        'opportunity_score': score,
                        'source_products': sources,
                    })
                    print(f'[GOLDBOX-SCAN] {i+1}/{len(new_keywords)} "{kw}" → 기회점수 {score}')

                except Exception as e:
                    print(f'[GOLDBOX-SCAN] "{kw}" 스캔 실패: {e}')
                    _goldbox_scan_state['results'].append({
                        'keyword': kw,
                        'scan_id': None,
                        'opportunity_score': 0,
                        'source_products': keyword_sources.get(kw, []),
                        'error': str(e),
                    })

                if i < len(new_keywords) - 1:
                    time.sleep(delay)

            # 5. TOP5 정리
            _goldbox_scan_state['scanned'] = len(new_keywords)
            results_sorted = sorted(
                [r for r in _goldbox_scan_state['results'] if r.get('opportunity_score', 0) > 0],
                key=lambda x: x['opportunity_score'],
                reverse=True
            )
            _goldbox_scan_state['results'] = results_sorted
            _goldbox_scan_state['phase'] = 'done'
            _goldbox_scan_state['current'] = f'완료! {len(new_keywords)}개 스캔, TOP {min(5, len(results_sorted))} 산출'
            print(f'[GOLDBOX-SCAN] 완료! TOP5: {[r["keyword"] for r in results_sorted[:5]]}')

        except Exception as e:
            import traceback
            traceback.print_exc()
            _goldbox_scan_state.update({'phase': 'error', 'current': str(e)})
        finally:
            _goldbox_scan_state['running'] = False


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
                        revenue_equality=round(opp.revenue_equality * 100, 1),
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
    progress = _scan_progress.get(scan_id)
    return jsonify({'success': True, 'scan': scan, 'progress': progress})


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
_detail_state = {}  # scan_id → {status, progress, analysis}


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

            # 리뷰 수집 — Playwright 직접 수집
            _review_state[scan_id]['status'] = 'collecting'
            all_reviews = _collect_reviews_direct(products)
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
    """CDP 연결된 Chrome에서 DOM 파싱으로 리뷰 수집 (playwright-stealth 적용)"""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth
    import time

    all_reviews = []
    pw = sync_playwright().start()
    stealth = Stealth()

    try:
        cdp_url = os.getenv('CDP_ENDPOINT', 'http://127.0.0.1:9222')
        browser = pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        # 기존 탭 재사용 (봇 감지 우회)
        page = context.pages[0] if context.pages else context.new_page()
        stealth.apply_stealth_sync(page)

        for p in products[:10]:
            url = p.get('product_url', '')
            if not url:
                continue
            pname = p.get('product_name', '')[:20]

            try:
                page.goto(url, wait_until='domcontentloaded', timeout=15000)
                time.sleep(3)
                # 리뷰 영역으로 스크롤
                page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
                time.sleep(2)

                # DOM에서 리뷰 추출 (article 태그 + 날짜 패턴 필터)
                reviews = page.evaluate("""() => {
                    const articles = document.querySelectorAll('article');
                    const result = [];
                    articles.forEach(a => {
                        const text = a.textContent.trim().replace(/\\s+/g, ' ');
                        // 날짜 패턴(YYYY.MM.DD)이 있는 article만 리뷰로 인식
                        if (!/\\d{4}\\.\\d{2}\\.\\d{2}/.test(text)) return;
                        if (text.length < 30) return;
                        result.push({
                            rating: 5,
                            headline: '',
                            content: text.substring(0, 500),
                        });
                    });
                    return result;
                }""")

                if reviews:
                    # 상품명 추가
                    for r in reviews:
                        r['productName'] = pname
                    all_reviews.extend(reviews)
                    print(f'[REVIEW] {pname} → {len(reviews)}개 (누적 {len(all_reviews)})')
                else:
                    print(f'[REVIEW] {pname} → 0개')

            except Exception as e:
                print(f'[REVIEW] 수집 실패: {pname} — {e}')

            time.sleep(1)

    except Exception as e:
        print(f'[REVIEW] CDP 연결 실패: {e}')
        print('[REVIEW] Chrome을 --remote-debugging-port=9222로 실행해주세요')
    finally:
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

    # DB에서 리뷰/분석 로드 (메모리에 없으면)
    state = _review_state.get(scan_id)
    if not state or not state.get('reviews'):
        state = fdb.load_reviews_from_db(scan_id)
    if not state:
        state = {}

    reviews = state.get('reviews', [])
    analysis = state.get('analysis')

    # 리뷰도 분석도 없으면 에러
    if not reviews and not analysis:
        return jsonify({'error': '리뷰 데이터가 없습니다. 먼저 리뷰 분석을 실행해주세요.'})

    # 키워드 조회
    keyword = ''
    scan = fdb.get_scan(scan_id)
    if scan:
        keyword = scan['keyword']

    # 리뷰 원본이 있으면 원본 사용, 없으면 분석 결과로 대체
    if reviews:
        review_texts = []
        for i, r in enumerate(reviews[:200], 1):
            parts = []
            if r.get('rating'):
                parts.append(f"평점:{r['rating']}")
            if r.get('headline'):
                parts.append(r['headline'])
            if r.get('content'):
                parts.append(r['content'])
            if parts:
                review_texts.append(f"{i}. {' | '.join(parts)}")
        context_block = '\n'.join(review_texts)
        context_label = f'상위 판매 상품 {len(reviews)}개의 소비자 리뷰'
    else:
        # 분석 결과를 컨텍스트로 사용
        import json as _json
        context_block = _json.dumps(analysis, ensure_ascii=False, indent=2)
        context_label = 'AI 분석 결과 (장단점, 인기 형태, 소싱 포인트 등)'

    prompt = f"""당신은 쿠팡 "{keyword}" 카테고리 제품 전문가입니다.
다음은 {context_label}입니다.

[분석 데이터]
{context_block}

[사용자 질문]
{question}

위 데이터를 참고하여 사용자의 질문에 자연스럽게 대화하듯 답해주세요.
- 질문이 인사면 간단히 인사하고 분석에서 알 수 있는 것을 안내해주세요.
- 질문이 구체적이면 데이터 근거를 들어 답해주세요.
- 이모지나 마크다운은 사용하지 마세요.
- 한국어로 답해주세요."""

    # AI API 제거 — 리뷰 Q&A 비활성화
    return jsonify({'error': '리뷰 Q&A 기능은 현재 비활성화되어 있습니다.'})


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


# ══════════════════════════════════════════════
# 상세 분석 (CDP + Gemini)
# ══════════════════════════════════════════════
@app.route('/api/scan/<int:scan_id>/detail-analysis', methods=['POST'])
def start_detail_analysis(scan_id):
    """상위 상품 상세페이지 수집 + AI 비교 분석"""
    if scan_id in _detail_state and _detail_state[scan_id].get('status') in ('collecting', 'analyzing'):
        return jsonify({'success': True, 'message': '이미 분석 중...'})

    products = fdb.get_products(scan_id)
    products.sort(key=lambda x: x.get('revenue_monthly', 0), reverse=True)
    products = products[:10]
    if not products:
        return jsonify({'success': False, 'error': '상품 데이터가 없습니다'})

    scan = fdb.get_scan(scan_id)
    keyword = scan['keyword'] if scan else ''

    _detail_state[scan_id] = {'status': 'collecting', 'progress': '0/' + str(len(products)), 'analysis': None}

    def _run():
        with app.app_context():
            try:
                collected = _collect_product_details(products, scan_id)
                if not collected:
                    _detail_state[scan_id] = {'status': 'error', 'progress': '', 'analysis': {'error': '상품 정보를 수집하지 못했습니다. Chrome CDP가 실행 중인지 확인해주세요.'}}
                    return

                _detail_state[scan_id]['status'] = 'analyzing'
                analysis = _analyze_product_details(collected, keyword)
                _detail_state[scan_id]['analysis'] = analysis
                _detail_state[scan_id]['status'] = 'done'
                fdb.save_detail_analysis(scan_id, keyword, analysis)
                print(f'[DETAIL] 분석 완료: {keyword} ({len(collected)}개 상품)')
            except Exception as e:
                import traceback; traceback.print_exc()
                _detail_state[scan_id] = {'status': 'error', 'progress': '', 'analysis': {'error': str(e)}}

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'success': True, 'message': f'{len(products)}개 상품 상세 분석 시작!'})


@app.route('/api/scan/<int:scan_id>/detail-analysis')
def get_detail_analysis(scan_id):
    """상세 분석 결과 조회"""
    state = _detail_state.get(scan_id)
    if not state or state.get('status') == 'none':
        saved = fdb.get_detail_analysis(scan_id)
        if saved:
            _detail_state[scan_id] = {'status': 'done', 'progress': '', 'analysis': saved}
            state = _detail_state[scan_id]
    if not state:
        state = {'status': 'none', 'progress': '', 'analysis': None}
    return jsonify({
        'success': True,
        'status': state.get('status', 'none'),
        'progress': state.get('progress', ''),
        'analysis': state.get('analysis'),
    })


@app.route('/api/scan/<int:scan_id>/detail-chat', methods=['POST'])
def detail_chat(scan_id):
    """수집된 상품 원본 데이터 기반으로 추가 질문에 Gemini가 답변"""
    data = request.get_json(force=True, silent=True) or {}
    question = data.get('question', '').strip()
    if not question:
        return jsonify({'success': False, 'error': '질문을 입력해주세요'})

    raw_products = fdb.get_detail_raw_products(scan_id)
    if not raw_products:
        return jsonify({'success': False, 'error': '원본 데이터가 없습니다. 상세 분석을 먼저 실행해주세요.'})

    scan = fdb.get_scan(scan_id)
    keyword = scan['keyword'] if scan else ''

    # 원본 데이터 텍스트 구성
    product_blocks = []
    for i, p in enumerate(raw_products, 1):
        block = f'[상품 {i}] {p.get("title", p.get("product_name", ""))} (순위 {p.get("ranking", i)}위)\n'
        block += f'가격: {p.get("price", "미확인")} | 월매출: {p.get("revenue_monthly", 0):,}원 | 리뷰: {p.get("review_count", 0)}개\n'
        block += f'상세내용:\n{p.get("detail_text", "")[:1200]}'
        product_blocks.append(block)

    context = '\n\n---\n\n'.join(product_blocks)

    from analyzer.reviews import _call_gemini
    prompt = f'''아래는 쿠팡 "{keyword}" 키워드 상위 {len(raw_products)}개 상품의 실제 상세페이지 데이터입니다.

{context}

---
질문: {question}

위 상품 데이터를 바탕으로 질문에 정확하게 답해주세요. 없는 정보는 "확인 불가"라고 솔직하게 말해주세요.'''

    answer = _call_gemini(prompt, max_tokens=3000)
    if not answer:
        return jsonify({'success': False, 'error': 'AI 응답 실패'})

    return jsonify({'success': True, 'answer': answer, 'products_count': len(raw_products)})


# ══════════════════════════════════════════════
# NotebookLM 연동
# ══════════════════════════════════════════════
_nlm_state = {}  # scan_id → {status, notebook_id, message}

@app.route('/api/scan/<int:scan_id>/nlm/status')
def nlm_status(scan_id):
    """NotebookLM 연동 상태 조회"""
    from analyzer.notebooklm import is_available
    state = _nlm_state.get(scan_id, {})
    return jsonify({
        'success': True,
        'nlm_available': is_available(),
        'status': state.get('status', 'none'),
        'notebook_id': state.get('notebook_id', ''),
        'message': state.get('message', ''),
    })


@app.route('/api/scan/<int:scan_id>/nlm/upload', methods=['POST'])
def nlm_upload(scan_id):
    """수집된 리뷰를 NotebookLM 노트북에 업로드"""
    if scan_id in _nlm_state and _nlm_state[scan_id].get('status') == 'uploading':
        return jsonify({'success': True, 'message': '업로드 중...', 'status': 'uploading'})

    # 리뷰 데이터 확인
    reviews = fdb.get_reviews(scan_id)
    if not reviews:
        return jsonify({'success': False, 'error': '리뷰 데이터가 없습니다. 리뷰 탭에서 수집을 먼저 실행해주세요.'})

    scan = fdb.get_scan(scan_id)
    keyword = scan['keyword'] if scan else f'scan_{scan_id}'

    _nlm_state[scan_id] = {'status': 'uploading', 'notebook_id': '', 'message': '노트북 생성 중...'}

    def _run():
        with app.app_context():
            try:
                from analyzer.notebooklm import get_or_create_notebook, add_text_source, build_review_text

                # 노트북 생성/조회
                notebook_id = get_or_create_notebook(scan_id, keyword)
                if not notebook_id:
                    _nlm_state[scan_id] = {'status': 'error', 'notebook_id': '', 'message': '노트북 생성 실패'}
                    return

                _nlm_state[scan_id]['message'] = '리뷰 업로드 중...'

                # 리뷰 데이터를 상품별로 그룹핑
                reviews_by_product = {}
                for rv in reviews:
                    pname = rv.get('product_name') or rv.get('productName') or keyword
                    reviews_by_product.setdefault(pname, []).append(rv)

                review_text = build_review_text(reviews_by_product, keyword)

                # NotebookLM에 업로드
                import datetime
                date_str = datetime.date.today().strftime('%y%m%d')
                source_id = add_text_source(notebook_id, review_text, title=f'{keyword}_리뷰_{date_str}')

                _nlm_state[scan_id] = {
                    'status': 'ready',
                    'notebook_id': notebook_id,
                    'message': f'업로드 완료! ({len(reviews_by_product)}개 상품 리뷰)',
                }
                print(f'[NLM] 업로드 완료: {keyword} → 노트북 {notebook_id[:8]}...')

            except Exception as e:
                import traceback; traceback.print_exc()
                _nlm_state[scan_id] = {'status': 'error', 'notebook_id': '', 'message': str(e)}

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'success': True, 'status': 'uploading', 'message': '업로드 시작!'})


@app.route('/api/scan/<int:scan_id>/nlm/query', methods=['POST'])
def nlm_query(scan_id):
    """NotebookLM 노트북에 질문"""
    data = request.get_json(force=True, silent=True) or {}
    question = data.get('question', '').strip()
    conversation_id = data.get('conversation_id', '')

    if not question:
        return jsonify({'success': False, 'error': '질문을 입력해주세요'})

    state = _nlm_state.get(scan_id, {})
    notebook_id = state.get('notebook_id', '')
    if not notebook_id:
        return jsonify({'success': False, 'error': 'NotebookLM에 업로드되지 않았습니다. 먼저 업로드해주세요.'})

    try:
        from analyzer.notebooklm import query as nlm_query_fn
        result = nlm_query_fn(notebook_id, question, conversation_id=conversation_id, timeout=120)
        return jsonify({
            'success': True,
            'answer': result.get('answer', ''),
            'conversation_id': result.get('conversation_id', ''),
            'citations': result.get('citations', []),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def _get_cdp_url() -> str:
    """CDP 엔드포인트 URL (환경변수 또는 기본값)"""
    return os.getenv('CDP_ENDPOINT', 'http://127.0.0.1:9222')


def _get_cdp_cookies(domain_filter: str = '') -> list:
    """CDP Chrome에서 쿠키 추출"""
    import requests as req
    try:
        cdp_url = _get_cdp_url()
        tabs = req.get(f'{cdp_url}/json', timeout=5).json()
        if not tabs:
            return []

        import websocket, json
        tab_ws = tabs[0].get('webSocketDebuggerUrl', '')
        ws = websocket.create_connection(tab_ws, timeout=5)
        ws.send(json.dumps({'id': 1, 'method': 'Network.getAllCookies'}))
        result = json.loads(ws.recv())
        ws.close()

        cookies = result.get('result', {}).get('cookies', [])
        if domain_filter:
            cookies = [c for c in cookies if domain_filter in c.get('domain', '')]
        print(f'[CDP] 쿠키 {len(cookies)}개 추출 ({domain_filter})')
        return cookies
    except Exception as e:
        print(f'[CDP] 쿠키 추출 실패: {e}')
        return []


def _fetch_page_via_cdp(url: str, wait_seconds: int = 7) -> dict:
    """Chrome CDP 새 탭으로 쿠팡 상품 데이터 추출 (Akamai 완전 우회)
    Returns: {'title': ..., 'price': ..., 'detail': ..., 'images': [...]}
    """
    import requests as req, websocket, json as _json, time
    cdp_url = _get_cdp_url()
    tab_id = None
    try:
        new_tab = req.put(f'{cdp_url}/json/new', timeout=5).json()
        tab_id = new_tab.get('id', '')
        tab_ws = new_tab.get('webSocketDebuggerUrl', '')
        if not tab_ws:
            return {}

        ws = websocket.create_connection(tab_ws, timeout=60)

        def _send_wait(cmd_id, method, params=None):
            ws.send(_json.dumps({'id': cmd_id, 'method': method, 'params': params or {}}))
            for _ in range(100):
                try:
                    msg = _json.loads(ws.recv())
                    if msg.get('id') == cmd_id:
                        return msg
                except Exception:
                    break
            return {}

        _send_wait(1, 'Page.navigate', {'url': url})
        time.sleep(wait_seconds)

        # 상세페이지 lazy loading 트리거 — 페이지 끝까지 스크롤
        scroll_js = 'window.scrollTo(0, document.body.scrollHeight); document.body.scrollHeight'
        for _ in range(5):
            _send_wait(99, 'Runtime.evaluate', {'expression': scroll_js, 'returnByValue': True})
            time.sleep(1)
        # 맨 위로 돌아가기
        _send_wait(98, 'Runtime.evaluate', {'expression': 'window.scrollTo(0,0)', 'returnByValue': True})
        time.sleep(1)

        js = r"""
(function() {
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

  return JSON.stringify({title: title, price: price, detail: detail, images: images});
})()
"""
        resp = _send_wait(2, 'Runtime.evaluate', {'expression': js, 'returnByValue': True})
        ws.close()

        value = resp.get('result', {}).get('result', {}).get('value', '{}') or '{}'
        return _json.loads(value)

    except Exception as e:
        print(f'[CDP_FETCH] 오류: {e}')
        return {}
    finally:
        if tab_id:
            try:
                req.get(f'{cdp_url}/json/close/{tab_id}', timeout=5)
            except Exception:
                pass


def _collect_product_details(products, scan_id) -> list:
    """Chrome CDP 직접 네비게이션으로 상품 상세페이지 수집 (Akamai 완전 우회)"""
    import time, requests as req

    collected = []
    total = len(products)

    cdp_url = _get_cdp_url()
    try:
        tabs = req.get(f'{cdp_url}/json', timeout=5).json()
        if not tabs:
            print('[DETAIL] CDP 미연결 — Chrome CDP 실행 필요')
            return []
        print(f'[DETAIL] CDP 연결 확인 (탭 {len(tabs)}개)')
    except Exception as e:
        print(f'[DETAIL] CDP 연결 실패: {e}')
        return []

    for i, p in enumerate(products):
        url = p.get('product_url', '')
        pname = p.get('product_name', '')[:30]
        _detail_state[scan_id]['progress'] = f'{i+1}/{total}'

        if not url:
            continue
        try:
            data = _fetch_page_via_cdp(url, wait_seconds=7)
            if not data or not data.get('detail'):
                print(f'[DETAIL] {i+1}/{total} {pname} → 데이터 없음')
                time.sleep(2)
                continue

            title = data.get('title') or pname
            price = data.get('price', '')
            detail_text = data.get('detail', '')
            images = data.get('images', [])

            collected.append({
                'product_name': pname,
                'product_url': url,
                'title': title,
                'price': price,
                'detail_text': detail_text,
                'image_urls': images,
                'ranking': p.get('ranking', i+1),
                'revenue_monthly': p.get('revenue_monthly', 0),
                'review_count': p.get('review_count', 0),
            })
            print(f'[DETAIL] {i+1}/{total} {pname} → 텍스트 {len(detail_text)}자, 이미지 {len(images)}장')

        except Exception as e:
            print(f'[DETAIL] {i+1}/{total} {pname} → 실패: {e}')

        time.sleep(2)

    print(f'[DETAIL] 총 {len(collected)}/{len(products)}개 수집 완료')
    return collected


def _analyze_product_details(collected: list, keyword: str) -> dict:
    """수집된 상품 데이터를 Gemini로 비교 분석"""
    from analyzer.reviews import _call_gemini

    # 상품 데이터 텍스트 구성
    product_texts = []
    for i, p in enumerate(collected, 1):
        text = f"""[상품 {i}] {p['title']}
가격: {p['price']}
월매출: {p['revenue_monthly']:,}원 | 리뷰: {p['review_count']}개 | 순위: {p['ranking']}위
상세페이지: {p['detail_text'][:800]}
이미지 수: {len(p['image_urls'])}장"""
        product_texts.append(text)

    products_block = '\n\n---\n\n'.join(product_texts)

    prompt = f"""당신은 쿠팡 소싱 전문가입니다.
아래는 "{keyword}" 키워드의 상위 {len(collected)}개 상품의 상세페이지 데이터입니다.

{products_block}

위 데이터를 분석하여 아래 항목을 JSON 형식으로 답해주세요:

1. "market_overview": 이 시장의 전반적 특징 요약 (3줄)
2. "common_specs": 대부분의 상품이 채택한 공통 스펙 (배열, "소재: ...", "사이즈: ..." 등)
3. "price_range": {{"min": "최저가", "max": "최고가", "sweet_spot": "가장 많은 가격대", "reason": "이유"}}
4. "popular_compositions": 가장 많이 쓰이는 구성/입수 패턴 3가지 (배열, 각 {{"type": "", "count": "상품수", "reason": ""}})
5. "key_selling_points": 상세페이지에서 공통적으로 강조하는 셀링 포인트 5가지 (배열)
6. "detail_page_patterns": 상세페이지 디자인/구성 공통 패턴 3가지 (배열)
7. "differentiation": 기존 제품 대비 차별화 아이디어 3가지 (배열)
8. "sourcing_tips": 이 제품을 소싱할 때 집중할 포인트 3가지 (배열)
9. "risk_factors": 주의해야 할 리스크 2가지 (배열)
10. "recommended_specs": 추천 스펙 시트 (배열, "소재: ...", "사이즈: ..." 등)

JSON만 답해주세요."""

    content = _call_gemini(prompt, max_tokens=8000)
    if content:
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            import json
            try:
                analysis = json.loads(json_match.group())
                analysis['_source'] = 'gemini'
                analysis['_products_analyzed'] = len(collected)
                analysis['_analyzed_products'] = [{'name': p['title'], 'price': p['price'], 'url': p['product_url']} for p in collected]
                return analysis
            except json.JSONDecodeError:
                pass

    return {
        'error': 'AI 분석 실패',
        '_products_analyzed': len(collected),
        '_raw_data': [{'name': p['title'], 'price': p['price']} for p in collected],
    }


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


# === 관심 상품 (Watchlist) API ===
@app.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    doc = fdb.db().collection('_meta').document('watchlist').get()
    scan_ids = (doc.to_dict() or {}).get('scan_ids', []) if doc.exists else []
    return jsonify({'success': True, 'scan_ids': scan_ids})

@app.route('/api/watchlist/<int:scan_id>', methods=['POST'])
def toggle_watchlist(scan_id):
    ref = fdb.db().collection('_meta').document('watchlist')
    doc = ref.get()
    scan_ids = (doc.to_dict() or {}).get('scan_ids', []) if doc.exists else []
    if scan_id in scan_ids:
        scan_ids.remove(scan_id)
        added = False
    else:
        scan_ids.append(scan_id)
        added = True
    ref.set({'scan_ids': scan_ids})
    return jsonify({'success': True, 'added': added})


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

    try:
        from analyzer.reviews import _call_gemini
        prompt = f"""Write a concise RFQ email in English for Alibaba. Be polite but get to the point.

Product: {product_name_kr}
Specs: {specs_text}
Certs: {', '.join(certs) if certs else 'N/A'}
Target: ${rfq.get('target_price', 0)}/unit, Qty: {rfq.get('order_quantity', 1000)}pcs, {rfq.get('shipping_terms', 'FOB')}

Keep message under 150 words. Include specs, price, qty, and ask for: unit price, MOQ, sample, lead time.

Sign as: Becore Lab Co., Ltd. (do NOT include email or URLs in the message - Alibaba blocks them)

JSON only:
{{"product_name_en": "...", "subject": "RFQ: ...", "message": "Dear Supplier,\\n\\n...\\n\\nBest regards,\\nBecore Lab Co., Ltd.\\nkychung@becorelab.kr", "specs_en": "..."}}"""

        ai_text = _call_gemini(prompt, max_tokens=2000)
        if ai_text:
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
# 기존 스캔 점수 일괄 재계산 (scoring.py 통일)
# ─────────────────────────────────────────────
@app.route('/api/rescore-all', methods=['POST'])
def rescore_all():
    """기존 스캔의 기회점수를 scoring.py 기반으로 일괄 재계산
    상품 데이터가 있는 스캔만 재계산 (없으면 스킵)"""
    scans = fdb.list_scans(limit=500)
    updated = 0
    skipped = 0
    errors = 0

    for scan in scans:
        scan_id = scan.get('id')
        keyword = scan.get('keyword', '')
        if not scan_id:
            continue

        try:
            # Firestore에서 상품 데이터 로드
            products_raw = fdb.get_products(scan_id)
            if not products_raw:
                skipped += 1
                continue

            # dict → CoupangProduct 변환
            products = []
            for pr in products_raw:
                products.append(CoupangProduct(
                    ranking=pr.get('ranking', 0),
                    product_name=pr.get('product_name', ''),
                    brand=pr.get('brand', ''),
                    manufacturer=pr.get('manufacturer', ''),
                    price=pr.get('price', 0),
                    sales_monthly=pr.get('sales_monthly', 0),
                    revenue_monthly=pr.get('revenue_monthly', 0),
                    review_count=pr.get('review_count', 0),
                    click_count=pr.get('click_count', 0),
                    conversion_rate=pr.get('conversion_rate', 0),
                    page_views=pr.get('page_views', 0),
                    category=pr.get('category', ''),
                    category_code=pr.get('category_code', ''),
                    product_url=pr.get('product_url', ''),
                ))

            # scoring.py로 재계산
            opp_score = calculate_opportunity(
                products=products,
                inflow_keywords=[],
                related_keywords=[],
                keyword=keyword
            )

            # Firestore 업데이트
            fdb.update_scan(scan_id,
                opportunity_score=round(opp_score.total_score, 1),
                top10_avg_revenue=opp_score.top4_10_avg_revenue,
                top10_avg_sales=opp_score.top4_10_avg_sales,
                top10_avg_price=opp_score.top4_10_avg_price,
                revenue_concentration=round(opp_score.top3_share * 100, 1),
                revenue_equality=round(opp_score.revenue_equality * 100, 1),
                new_product_rate=round(opp_score.new_product_rate * 100, 1),
                ad_dependency=round(opp_score.avg_new_product_weight, 1),
            )
            updated += 1
            print(f'[RESCORE] {scan_id} {keyword}: {scan.get("opportunity_score")} → {opp_score.total_score:.1f}')

        except Exception as e:
            errors += 1
            print(f'[RESCORE] 에러 {scan_id} {keyword}: {e}')

    return jsonify({
        'success': True,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
        'message': f'{updated}개 재계산 완료 ({skipped}개 스킵, {errors}개 에러)'
    })


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
if __name__ == '__main__':
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    fdb.init_firestore()
    _load_all_reviews_from_db()
    print("\n[BECORELAB] 소싱콕 v0.1")
    print("[BECORELAB] http://localhost:8090\n")
    app.run(host='0.0.0.0', port=8090, debug=True, use_reloader=False)
