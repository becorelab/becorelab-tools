"""
비코어랩 쿠팡 소싱 기회 분석기 — 메인 Flask 앱
포트: 8090 (기존 sourcing_app.py 8080과 분리)
"""

import os
import sys
import json
import sqlite3
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.helpstore import (
    HelpstoreAPI, scan_keyword_api_only,
    CoupangProduct, InflowKeyword
)
from analyzer.scoring import calculate_opportunity, generate_keyword_variants, OpportunityScore
from analyzer.wing import wing_search, wing_ensure_login, get_wing_status

app = Flask(__name__)

# 전역 헬프스토어 API 인스턴스
helpstore_api = None

def get_helpstore():
    global helpstore_api
    if helpstore_api is None:
        helpstore_api = HelpstoreAPI()
    return helpstore_api
app.config['SECRET_KEY'] = 'becorelab-sourcing-analyzer-2026'

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analyzer.db')


# ─────────────────────────────────────────────
# DB 연결
# ─────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """DB 테이블 초기화"""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript('''
        -- 시장조사 기록 (키워드 단위)
        CREATE TABLE IF NOT EXISTS market_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            scan_type TEXT DEFAULT 'auto',  -- auto / manual
            category TEXT,
            opportunity_score REAL,
            top10_avg_revenue INTEGER,
            top10_avg_sales INTEGER,
            top10_avg_price INTEGER,
            revenue_concentration REAL,      -- 1위 점유율
            revenue_equality REAL,           -- 매출균등도 (10위/1위)
            new_product_rate REAL,            -- 신상품 진입률
            ad_dependency REAL,              -- 광고 의존도
            recommended_keyword TEXT,         -- 추천 진입 키워드
            status TEXT DEFAULT 'scanned',   -- scanned / analyzed / go / pass
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 상품 상세 (상위 40개)
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            ranking INTEGER,
            product_name TEXT,
            brand TEXT,
            manufacturer TEXT,
            price INTEGER,
            sales_monthly INTEGER,            -- 월 판매량
            revenue_monthly INTEGER,           -- 월 매출
            review_count INTEGER,
            click_count INTEGER,
            conversion_rate REAL,              -- 전환율
            page_views INTEGER,                -- PV
            new_product_weight REAL,           -- 신상품 가중치
            category TEXT,
            category_code TEXT,
            product_url TEXT,
            FOREIGN KEY (scan_id) REFERENCES market_scans(id) ON DELETE CASCADE
        );

        -- 유입 키워드
        CREATE TABLE IF NOT EXISTS inflow_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            product_id INTEGER,
            keyword TEXT NOT NULL,
            search_volume INTEGER,            -- 조회수
            click_count INTEGER,              -- 클릭수
            click_rate REAL,                  -- 클릭율
            impression_increase REAL,         -- 노출증가
            ad_weight REAL,                   -- 광고비중
            FOREIGN KEY (scan_id) REFERENCES market_scans(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        -- 키워드 변형 (띄어쓰기 등)
        CREATE TABLE IF NOT EXISTS keyword_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            original_keyword TEXT NOT NULL,
            variant_keyword TEXT NOT NULL,
            search_volume INTEGER,
            competition_level TEXT,
            opportunity_note TEXT,
            FOREIGN KEY (scan_id) REFERENCES market_scans(id) ON DELETE CASCADE
        );

        -- RFQ (견적 요청)
        CREATE TABLE IF NOT EXISTS rfqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            product_name_en TEXT,
            product_name_kr TEXT,
            category TEXT,
            specifications TEXT,              -- JSON: 소재, 사이즈, 색상 등
            target_price REAL,
            target_price_currency TEXT DEFAULT 'USD',
            order_quantity INTEGER,
            moq INTEGER,
            shipping_terms TEXT DEFAULT 'FOB',
            certifications TEXT,              -- JSON: KC, CE 등
            reference_images TEXT,            -- JSON: 이미지 URL 리스트
            alibaba_rfq_id TEXT,
            status TEXT DEFAULT 'draft',      -- draft / posted / receiving / closed
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 견적 (업체 응답)
        CREATE TABLE IF NOT EXISTS quotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rfq_id INTEGER NOT NULL,
            supplier_name TEXT,
            supplier_url TEXT,
            supplier_rating REAL,
            supplier_years INTEGER,           -- 업력
            unit_price REAL,
            unit_price_currency TEXT DEFAULT 'USD',
            moq INTEGER,
            lead_time_days INTEGER,
            sample_cost REAL,
            certifications TEXT,              -- JSON
            notes TEXT,
            is_selected INTEGER DEFAULT 0,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE
        );

        -- 소싱 히스토리 (종합)
        CREATE TABLE IF NOT EXISTS sourcing_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            rfq_id INTEGER,
            product_name TEXT,
            status TEXT DEFAULT 'discovered',
            -- discovered → analyzed → rfq_posted → quoting →
            -- supplier_selected → sampling → sample_received → ordered → completed / dropped
            opportunity_score REAL,
            selected_keyword TEXT,
            selected_supplier TEXT,
            target_price REAL,
            final_price REAL,
            margin_rate REAL,
            notes TEXT,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (scan_id) REFERENCES market_scans(id),
            FOREIGN KEY (rfq_id) REFERENCES rfqs(id)
        );

        -- 인덱스
        CREATE INDEX IF NOT EXISTS idx_scans_keyword ON market_scans(keyword);
        CREATE INDEX IF NOT EXISTS idx_scans_score ON market_scans(opportunity_score DESC);
        CREATE INDEX IF NOT EXISTS idx_scans_status ON market_scans(status);
        CREATE INDEX IF NOT EXISTS idx_products_scan ON products(scan_id);
        CREATE INDEX IF NOT EXISTS idx_inflow_scan ON inflow_keywords(scan_id);
        CREATE INDEX IF NOT EXISTS idx_rfqs_status ON rfqs(status);
        CREATE INDEX IF NOT EXISTS idx_history_status ON sourcing_history(status);
    ''')
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# 라우트
# ─────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


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
    db = get_db()
    cursor = db.execute('''
        INSERT INTO market_scans (keyword, scan_type, status)
        VALUES (?, 'manual', 'scanning')
    ''', (keyword,))
    db.commit()
    scan_id = cursor.lastrowid

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
        db = get_db()
        try:
            if use_cdp:
                try:
                    _run_scan_cdp(db, scan_id, keyword)
                except Exception as cdp_err:
                    # CDP 실패 시 API 모드로 자동 폴백
                    print(f'[SCAN-CDP] 실패 → API 모드로 전환: {cdp_err}')
                    _run_scan_api(db, scan_id, keyword)
            else:
                _run_scan_api(db, scan_id, keyword)
        except Exception as e:
            import traceback
            print(f'[SCAN] 에러: {keyword} — {e}')
            traceback.print_exc()
            db.execute('''
                UPDATE market_scans SET status = 'failed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (scan_id,))
            db.commit()


def _run_scan_api(db, scan_id: int, keyword: str):
    """서버 API 전용 스캔 (기존 로직)"""
    # 1. 헬프스토어 서버 API로 키워드 데이터 수집
    api = get_helpstore()
    result = api.search_keyword(keyword)

    # 2. 연관 키워드를 inflow_keywords 테이블에 저장
    for kw in result.related_keywords:
        db.execute('''
            INSERT INTO inflow_keywords (scan_id, keyword, search_volume,
                click_count, click_rate, ad_weight)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            scan_id, kw.keyword, kw.total_search,
            kw.pc_search + kw.mobile_search,
            (kw.pc_click_rate + kw.mobile_click_rate) / 2,
            0  # 서버 API에서는 광고비중 데이터 없음
        ))

    # 3. 띄어쓰기 변형 키워드 생성 및 저장
    _save_keyword_variants(db, scan_id, keyword, result.related_keywords)

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
    db.execute('''
        UPDATE market_scans SET
            status = 'scanned',
            category = ?,
            opportunity_score = ?,
            top10_avg_revenue = 0,
            top10_avg_sales = 0,
            top10_avg_price = 0,
            revenue_equality = 0,
            new_product_rate = 0,
            ad_dependency = 0,
            recommended_keyword = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        result.main_category,
        round(simple_score, 1),
        recommended,
        scan_id
    ))
    db.commit()
    print(f'[SCAN-API] 완료: {keyword} (점수: {simple_score:.1f}, 연관키워드: {len(result.related_keywords)}개)')


def _run_scan_cdp(db, scan_id: int, keyword: str):
    """
    CDP 전체 스캔 — 실제 쿠팡 데이터 (매출/판매량/클릭수/전환율)
    서버 API 데이터 + 브라우저 자동화 데이터 결합
    """
    print(f'[SCAN-CDP] 시작: {keyword} (Chrome CDP 연동)')

    # 전체 스캔 (서버 API + 브라우저 자동화)
    result = scan_keyword_full_sync(keyword)

    # ─── 상품 데이터 저장 ───
    for product in result.products:
        db.execute('''
            INSERT INTO products (scan_id, ranking, product_name, brand, manufacturer,
                price, sales_monthly, revenue_monthly, review_count, click_count,
                conversion_rate, page_views, category, category_code, product_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scan_id, product.ranking, product.product_name, product.brand,
            product.manufacturer, product.price, product.sales_monthly,
            product.revenue_monthly, product.review_count, product.click_count,
            product.conversion_rate, product.page_views, product.category,
            product.category_code, product.product_url
        ))

    # ─── 유입 키워드 저장 ───
    for kw in result.inflow_keywords:
        db.execute('''
            INSERT INTO inflow_keywords (scan_id, keyword, search_volume,
                click_count, click_rate, impression_increase, ad_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            scan_id, kw.keyword, kw.search_volume,
            kw.click_count, kw.click_rate,
            kw.impression_increase, kw.ad_weight
        ))

    # ─── 연관 키워드 저장 (API에서 가져온 것) ───
    for kw in result.related_keywords:
        db.execute('''
            INSERT INTO inflow_keywords (scan_id, keyword, search_volume,
                click_count, click_rate, ad_weight)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            scan_id, kw.keyword, kw.total_search,
            kw.pc_search + kw.mobile_search,
            (kw.pc_click_rate + kw.mobile_click_rate) / 2, 0
        ))

    # ─── 띄어쓰기 변형 키워드 ───
    _save_keyword_variants(db, scan_id, keyword, result.related_keywords)

    # ─── 기회점수 산출 (실제 쿠팡 데이터 기반!) ───
    opp_score = calculate_opportunity(
        products=result.products,
        inflow_keywords=result.inflow_keywords,
        related_keywords=result.related_keywords,
        keyword=keyword
    )

    # ─── 스캔 결과 업데이트 ───
    db.execute('''
        UPDATE market_scans SET
            status = 'scanned',
            category = ?,
            opportunity_score = ?,
            top10_avg_revenue = ?,
            top10_avg_sales = ?,
            top10_avg_price = ?,
            revenue_concentration = ?,
            revenue_equality = ?,
            new_product_rate = ?,
            ad_dependency = ?,
            recommended_keyword = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        result.main_category,
        round(opp_score.total_score, 1),
        opp_score.top10_avg_revenue,
        opp_score.top10_avg_sales,
        opp_score.top10_avg_price,
        round(opp_score.top1_share * 100, 1),
        round(opp_score.revenue_equality * 100, 1),
        round(opp_score.new_product_rate * 100, 1),
        round(opp_score.ad_dependency, 1),
        opp_score.recommended_keyword,
        scan_id
    ))
    db.commit()

    print(
        f'[SCAN-CDP] 완료: {keyword}\n'
        f'  기회점수: {opp_score.total_score:.1f} ({opp_score.grade})\n'
        f'  상품: {len(result.products)}개 | 유입키워드: {len(result.inflow_keywords)}개\n'
        f'  상위10 평균매출: {opp_score.top10_avg_revenue:,}원\n'
        f'  1위점유율: {opp_score.top1_share*100:.1f}% | 매출균등도: {opp_score.revenue_equality*100:.1f}%\n'
        f'  신상품진입률: {opp_score.new_product_rate*100:.1f}% | 광고의존도: {opp_score.ad_dependency:.1f}%\n'
        f'  추천키워드: {opp_score.recommended_keyword}'
    )


def _save_keyword_variants(db, scan_id: int, keyword: str, related_keywords: list):
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
        db.execute('''
            INSERT INTO keyword_variants (scan_id, original_keyword,
                variant_keyword, search_volume, competition_level)
            VALUES (?, ?, ?, ?, ?)
        ''', (scan_id, keyword, variant, variant_search, variant_comp))


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
    db = get_db()
    cursor = db.execute('''
        INSERT INTO market_scans (keyword, scan_type, status)
        VALUES (?, 'wing', 'scanning')
    ''', (keyword,))
    db.commit()
    scan_id = cursor.lastrowid

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
        db = get_db()
        try:
            # 1. 쿠팡윙 상품 데이터
            products = wing_search(keyword)

            for p in products:
                db.execute('''
                    INSERT INTO products (scan_id, ranking, product_name, brand,
                        manufacturer, price, sales_monthly, revenue_monthly,
                        review_count, click_count, conversion_rate, page_views,
                        category, category_code, product_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    scan_id, p.ranking, p.product_name, p.brand,
                    p.manufacturer, p.price, p.sales_monthly,
                    p.revenue_monthly, p.review_count, p.click_count,
                    p.conversion_rate, p.page_views, p.category,
                    p.category_code, p.product_url
                ))

            # 2. 헬프스토어 키워드 데이터 (연관키워드/검색량)
            api = get_helpstore()
            api_result = api.search_keyword(keyword)

            for kw in api_result.related_keywords:
                db.execute('''
                    INSERT INTO inflow_keywords (scan_id, keyword, search_volume,
                        click_count, click_rate, ad_weight)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    scan_id, kw.keyword, kw.total_search,
                    kw.pc_search + kw.mobile_search,
                    (kw.pc_click_rate + kw.mobile_click_rate) / 2, 0
                ))

            # 3. 키워드 변형
            _save_keyword_variants(db, scan_id, keyword, api_result.related_keywords)

            # 4. 기회점수 산출
            opp_score = calculate_opportunity(
                products=products,
                inflow_keywords=[],
                related_keywords=api_result.related_keywords,
                keyword=keyword
            )

            # 5. DB 업데이트
            db.execute('''
                UPDATE market_scans SET
                    status = 'scanned',
                    category = ?,
                    opportunity_score = ?,
                    top10_avg_revenue = ?,
                    top10_avg_sales = ?,
                    top10_avg_price = ?,
                    revenue_concentration = ?,
                    revenue_equality = ?,
                    new_product_rate = ?,
                    ad_dependency = ?,
                    recommended_keyword = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                api_result.main_category,
                round(opp_score.total_score, 1),
                opp_score.top4_10_avg_revenue,  # 4~10등 평균매출 (진입 기대)
                opp_score.top4_10_avg_sales,
                opp_score.top4_10_avg_price,
                round(opp_score.top3_share * 100, 1),  # 상위3 점유율
                round(opp_score.sellers_over_3m_rate * 100, 1),  # 300만+ 비율
                round(opp_score.new_product_rate * 100, 1),
                round(opp_score.avg_new_product_weight, 1),  # 신상품 가중치
                opp_score.recommended_keyword,
                scan_id
            ))
            db.commit()

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
            db.execute('''
                UPDATE market_scans SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, scan_id))
            db.commit()


# === 카테고리 탐색 ===
from analyzer.categories import CATEGORY_SEEDS, get_all_seeds, get_category_names


@app.route('/api/categories')
def api_categories():
    """탐색 가능한 카테고리 목록"""
    cats = []
    for name, keywords in CATEGORY_SEEDS.items():
        cats.append({'name': name, 'count': len(keywords)})
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

            for seed in seeds:
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
                    db = get_db()
                    cursor = db.execute('''
                        INSERT INTO market_scans (keyword, scan_type, status)
                        VALUES (?, 'auto', 'scanning')
                    ''', (keyword,))
                    db.commit()
                    scan_id = cursor.lastrowid

                    products = wing_search(keyword)

                    # 상품 저장
                    for p in products:
                        db.execute('''
                            INSERT INTO products (scan_id, ranking, product_name, brand,
                                manufacturer, price, sales_monthly, revenue_monthly,
                                review_count, click_count, conversion_rate, page_views,
                                category, category_code, product_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            scan_id, p.ranking, p.product_name, p.brand,
                            p.manufacturer, p.price, p.sales_monthly,
                            p.revenue_monthly, p.review_count, p.click_count,
                            p.conversion_rate, p.page_views, p.category,
                            p.category_code, p.product_url
                        ))

                    # 기회점수
                    opp = calculate_opportunity(
                        products=products,
                        related_keywords=api.get_related_keywords(keyword),
                        keyword=keyword
                    )

                    # DB 업데이트
                    db.execute('''
                        UPDATE market_scans SET
                            status = 'scanned', category = ?, opportunity_score = ?,
                            top10_avg_revenue = ?, top10_avg_sales = ?, top10_avg_price = ?,
                            revenue_concentration = ?, revenue_equality = ?,
                            new_product_rate = ?, ad_dependency = ?,
                            recommended_keyword = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        products[0].category if products else '',
                        round(opp.total_score, 1),
                        opp.top4_10_avg_revenue, opp.top4_10_avg_sales, opp.top4_10_avg_price,
                        round(opp.top3_share * 100, 1),
                        round(opp.sellers_over_3m_rate * 100, 1),
                        round(opp.new_product_rate * 100, 1),
                        round(opp.avg_new_product_weight, 1),
                        opp.recommended_keyword, scan_id
                    ))
                    db.commit()

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

    db = get_db()

    # 스캔 레코드 생성
    cursor = db.execute('''
        INSERT INTO market_scans (keyword, scan_type, status)
        VALUES (?, 'capture', 'scanning')
    ''', (keyword,))
    db.commit()
    scan_id = cursor.lastrowid

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
        db = get_db()
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

                db.execute('''
                    INSERT INTO products (scan_id, ranking, product_name, brand,
                        manufacturer, price, sales_monthly, revenue_monthly,
                        review_count, click_count, conversion_rate, page_views,
                        category, category_code, product_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    scan_id, p.ranking, p.product_name, p.brand,
                    p.manufacturer, p.price, p.sales_monthly,
                    p.revenue_monthly, p.review_count, p.click_count,
                    p.conversion_rate, p.page_views, p.category,
                    p.category_code, p.product_url
                ))

            # 2. 서버 API로 키워드 데이터 수집 (연관키워드/검색량)
            api = get_helpstore()
            api_result = api.search_keyword(keyword)

            for kw in api_result.related_keywords:
                db.execute('''
                    INSERT INTO inflow_keywords (scan_id, keyword, search_volume,
                        click_count, click_rate, ad_weight)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    scan_id, kw.keyword, kw.total_search,
                    kw.pc_search + kw.mobile_search,
                    (kw.pc_click_rate + kw.mobile_click_rate) / 2, 0
                ))

            # 3. 띄어쓰기 변형 키워드
            _save_keyword_variants(db, scan_id, keyword, api_result.related_keywords)

            # 4. 기회점수 산출 (실제 쿠팡 데이터 기반!)
            opp_score = calculate_opportunity(
                products=products,
                inflow_keywords=[],
                related_keywords=api_result.related_keywords,
                keyword=keyword
            )

            # 5. 스캔 결과 업데이트
            db.execute('''
                UPDATE market_scans SET
                    status = 'scanned',
                    category = ?,
                    opportunity_score = ?,
                    top10_avg_revenue = ?,
                    top10_avg_sales = ?,
                    top10_avg_price = ?,
                    revenue_concentration = ?,
                    revenue_equality = ?,
                    new_product_rate = ?,
                    ad_dependency = ?,
                    recommended_keyword = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                api_result.main_category,
                round(opp_score.total_score, 1),
                opp_score.top10_avg_revenue,
                opp_score.top10_avg_sales,
                opp_score.top10_avg_price,
                round(opp_score.top1_share * 100, 1),
                round(opp_score.revenue_equality * 100, 1),
                round(opp_score.new_product_rate * 100, 1),
                round(opp_score.ad_dependency, 1),
                opp_score.recommended_keyword,
                scan_id
            ))
            db.commit()

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
            db.execute('''
                UPDATE market_scans SET status = 'failed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (scan_id,))
            db.commit()


@app.route('/api/scan/<int:scan_id>/poll')
def poll_scan(scan_id):
    """스캔 진행 상태 폴링"""
    db = get_db()
    scan = db.execute('SELECT id, status, opportunity_score, keyword, recommended_keyword, category FROM market_scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return jsonify({'success': False})
    return jsonify({'success': True, 'scan': dict(scan)})


@app.route('/api/scans')
def get_scans():
    """시장조사 목록 조회"""
    db = get_db()
    scans = db.execute('''
        SELECT * FROM market_scans
        ORDER BY scanned_at DESC
        LIMIT 100
    ''').fetchall()
    return jsonify({'success': True, 'scans': [dict(s) for s in scans]})


@app.route('/api/scan/<int:scan_id>')
def get_scan_detail(scan_id):
    """시장조사 상세 (상품 + 키워드 포함)"""
    db = get_db()
    scan = db.execute('SELECT * FROM market_scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return jsonify({'success': False, 'error': '조사 기록 없음'})

    products = db.execute('''
        SELECT * FROM products WHERE scan_id = ? ORDER BY ranking
    ''', (scan_id,)).fetchall()

    keywords = db.execute('''
        SELECT * FROM inflow_keywords WHERE scan_id = ? ORDER BY search_volume DESC
    ''', (scan_id,)).fetchall()

    variants = db.execute('''
        SELECT * FROM keyword_variants WHERE scan_id = ?
    ''', (scan_id,)).fetchall()

    return jsonify({
        'success': True,
        'scan': dict(scan),
        'products': [dict(p) for p in products],
        'keywords': [dict(k) for k in keywords],
        'variants': [dict(v) for v in variants]
    })


@app.route('/api/scan/<int:scan_id>/status', methods=['PUT'])
def update_scan_status(scan_id):
    """스캔 상태 변경 (go / pass)"""
    data = request.json
    status = data.get('status')
    db = get_db()
    db.execute('''
        UPDATE market_scans SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (status, scan_id))
    db.commit()
    return jsonify({'success': True})


# === 기회분석 API ===
@app.route('/api/opportunities')
def get_opportunities():
    """기회점수 랭킹 조회"""
    db = get_db()
    scans = db.execute('''
        SELECT * FROM market_scans
        WHERE opportunity_score IS NOT NULL
        ORDER BY opportunity_score DESC
        LIMIT 50
    ''').fetchall()
    return jsonify({'success': True, 'opportunities': [dict(s) for s in scans]})


# === RFQ API ===
@app.route('/api/rfq', methods=['POST'])
def create_rfq():
    """RFQ 생성"""
    data = request.json
    db = get_db()
    cursor = db.execute('''
        INSERT INTO rfqs (scan_id, product_name_en, product_name_kr, category,
                         specifications, target_price, order_quantity, moq,
                         shipping_terms, certifications, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
    ''', (
        data.get('scan_id'),
        data.get('product_name_en'),
        data.get('product_name_kr'),
        data.get('category'),
        json.dumps(data.get('specifications', {})),
        data.get('target_price'),
        data.get('order_quantity'),
        data.get('moq'),
        data.get('shipping_terms', 'FOB'),
        json.dumps(data.get('certifications', []))
    ))
    db.commit()
    return jsonify({'success': True, 'rfq_id': cursor.lastrowid})


@app.route('/api/rfqs')
def get_rfqs():
    """RFQ 목록 조회"""
    db = get_db()
    rfqs = db.execute('SELECT * FROM rfqs ORDER BY created_at DESC').fetchall()
    return jsonify({'success': True, 'rfqs': [dict(r) for r in rfqs]})


@app.route('/api/rfq/<int:rfq_id>')
def get_rfq_detail(rfq_id):
    """RFQ 상세 + 견적 목록"""
    db = get_db()
    rfq = db.execute('SELECT * FROM rfqs WHERE id = ?', (rfq_id,)).fetchone()
    if not rfq:
        return jsonify({'success': False, 'error': 'RFQ 없음'})

    quotations = db.execute('''
        SELECT * FROM quotations WHERE rfq_id = ? ORDER BY unit_price
    ''', (rfq_id,)).fetchall()

    return jsonify({
        'success': True,
        'rfq': dict(rfq),
        'quotations': [dict(q) for q in quotations]
    })


# === 견적 API ===
@app.route('/api/quotation', methods=['POST'])
def add_quotation():
    """견적 추가"""
    data = request.json
    db = get_db()
    cursor = db.execute('''
        INSERT INTO quotations (rfq_id, supplier_name, supplier_url, supplier_rating,
                               supplier_years, unit_price, moq, lead_time_days,
                               sample_cost, certifications, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('rfq_id'),
        data.get('supplier_name'),
        data.get('supplier_url'),
        data.get('supplier_rating'),
        data.get('supplier_years'),
        data.get('unit_price'),
        data.get('moq'),
        data.get('lead_time_days'),
        data.get('sample_cost'),
        json.dumps(data.get('certifications', [])),
        data.get('notes')
    ))
    db.commit()
    return jsonify({'success': True, 'quotation_id': cursor.lastrowid})


# === 히스토리 API ===
@app.route('/api/history')
def get_history():
    """소싱 히스토리 조회"""
    db = get_db()
    history = db.execute('''
        SELECT h.*, m.keyword as scan_keyword, r.product_name_kr as rfq_product
        FROM sourcing_history h
        LEFT JOIN market_scans m ON h.scan_id = m.id
        LEFT JOIN rfqs r ON h.rfq_id = r.id
        ORDER BY h.updated_at DESC
    ''').fetchall()
    return jsonify({'success': True, 'history': [dict(h) for h in history]})


# === 대시보드 통계 ===
@app.route('/api/stats')
def get_stats():
    """대시보드 통계"""
    db = get_db()
    stats = {
        'total_scans': db.execute('SELECT COUNT(*) FROM market_scans').fetchone()[0],
        'auto_scans': db.execute("SELECT COUNT(*) FROM market_scans WHERE scan_type='auto'").fetchone()[0],
        'manual_scans': db.execute("SELECT COUNT(*) FROM market_scans WHERE scan_type='manual'").fetchone()[0],
        'go_products': db.execute("SELECT COUNT(*) FROM market_scans WHERE status='go'").fetchone()[0],
        'active_rfqs': db.execute("SELECT COUNT(*) FROM rfqs WHERE status IN ('posted','receiving')").fetchone()[0],
        'total_quotations': db.execute('SELECT COUNT(*) FROM quotations').fetchone()[0],
        'top_opportunity': None
    }
    top = db.execute('''
        SELECT keyword, opportunity_score FROM market_scans
        WHERE opportunity_score IS NOT NULL
        ORDER BY opportunity_score DESC LIMIT 1
    ''').fetchone()
    if top:
        stats['top_opportunity'] = {'keyword': top[0], 'score': top[1]}

    return jsonify({'success': True, 'stats': stats})


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
if __name__ == '__main__':
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    init_db()
    print("\n[BECORELAB] Sourcing Opportunity Analyzer v0.1")
    print("[BECORELAB] http://localhost:8090\n")
    app.run(host='0.0.0.0', port=8090, debug=True, use_reloader=False)
