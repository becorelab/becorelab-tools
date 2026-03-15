"""
비코어랩 쿠팡 마켓 파인더 — 메인 Flask 앱
포트: 8090 (기존 sourcing_app.py 8080과 분리)
"""

import os
import sys
import json
import re
import sqlite3
import threading
from datetime import datetime
from collections import Counter
from flask import Flask, render_template, request, jsonify, g

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

        -- 골드박스 일별 기록
        CREATE TABLE IF NOT EXISTS goldbox_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawled_date TEXT NOT NULL,          -- YYYY-MM-DD
            product_name TEXT,
            price INTEGER,
            discount TEXT,
            product_url TEXT,
            extracted_keyword TEXT,
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_goldbox_date ON goldbox_daily(crawled_date);

        -- 수집 리뷰
        CREATE TABLE IF NOT EXISTS collected_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            product_name TEXT,
            rating INTEGER,
            headline TEXT,
            content TEXT,
            date TEXT,
            option TEXT,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (scan_id) REFERENCES market_scans(id) ON DELETE CASCADE
        );

        -- 리뷰 분석 결과
        CREATE TABLE IF NOT EXISTS review_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            keyword TEXT,
            review_count INTEGER,
            analysis_json TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (scan_id) REFERENCES market_scans(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_collected_reviews_scan ON collected_reviews(scan_id);
        CREATE INDEX IF NOT EXISTS idx_review_analyses_scan ON review_analyses(scan_id);

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
    'keywords': [],
    'scanned': 0,
    'total': 0,
    'current': '',
    'results': [],
}


@app.route('/api/goldbox/start', methods=['POST'])
def api_goldbox_start():
    """골드박스 수집 + 분석 시작"""
    if _goldbox_state['running']:
        return jsonify({'success': False, 'error': '이미 진행 중'})

    data = request.get_json(silent=True) or {}
    max_scan = data.get('max_scan', 15)

    _goldbox_state.update({
        'running': True, 'phase': 'crawling', 'products': [],
        'keywords': [], 'scanned': 0, 'total': 0, 'current': '', 'results': [],
    })

    thread = threading.Thread(target=_run_goldbox, args=(max_scan,), daemon=True)
    thread.start()
    return jsonify({'success': True, 'message': '골드박스 수집 시작!'})


@app.route('/api/goldbox/status')
def api_goldbox_status():
    return jsonify({
        'success': True,
        'phase': _goldbox_state['phase'],
        'products': len(_goldbox_state['products']),
        'scanned': _goldbox_state['scanned'],
        'total': _goldbox_state['total'],
        'current': _goldbox_state['current'],
        'running': _goldbox_state['running'],
        'result_count': len(_goldbox_state['results']),
    })


@app.route('/api/goldbox/products')
def api_goldbox_products():
    return jsonify({'success': True, 'products': _goldbox_state['products']})


@app.route('/api/goldbox/history')
def api_goldbox_history():
    """골드박스 일별 기록"""
    db = get_db()
    # 날짜별 상품 수
    dates = db.execute('''
        SELECT crawled_date, COUNT(*) as count
        FROM goldbox_daily
        GROUP BY crawled_date
        ORDER BY crawled_date DESC
        LIMIT 30
    ''').fetchall()
    return jsonify({'success': True, 'dates': [dict(d) for d in dates]})


@app.route('/api/goldbox/history/<date>')
def api_goldbox_history_date(date):
    """특정 날짜의 골드박스 상품"""
    db = get_db()
    products = db.execute('''
        SELECT * FROM goldbox_daily
        WHERE crawled_date = ?
        ORDER BY id
    ''', (date,)).fetchall()
    return jsonify({'success': True, 'date': date, 'products': [dict(p) for p in products]})


@app.route('/api/goldbox/results')
def api_goldbox_results():
    results = sorted(_goldbox_state['results'], key=lambda r: r.get('score', 0), reverse=True)
    return jsonify({'success': True, 'results': results})


def _run_goldbox(max_scan: int):
    """골드박스 크롤링 → 키워드 추출 → 윙 스캔"""
    with app.app_context():
        try:
            # Phase 1: 골드박스 페이지 크롤링
            _goldbox_state['phase'] = 'crawling'
            _goldbox_state['current'] = '골드박스 페이지 로딩...'

            # 골드박스는 공개 페이지 → 별도 Playwright로 크롤링 (Wing 워커 안 씀)
            products = _crawl_goldbox_direct(GOLDBOX_URL)
            _goldbox_state['products'] = products
            _goldbox_state['current'] = f'{len(products)}개 상품 수집 완료'

            # DB에 일별 저장
            import re
            today = datetime.now().strftime('%Y-%m-%d')
            db = get_db()
            for p in products:
                words = re.findall(r'[가-힣]{2,6}', p.get('name', ''))
                extracted = ' '.join(words[:3]) if words else ''
                db.execute('''
                    INSERT INTO goldbox_daily (crawled_date, product_name, price, discount, product_url, extracted_keyword)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (today, p.get('name', ''), p.get('price', 0), p.get('discount', ''), p.get('url', ''), extracted))
            db.commit()
            print(f'[GOLDBOX] {today} — {len(products)}개 상품 DB 저장')

            if not products:
                _goldbox_state['phase'] = 'error'
                _goldbox_state['current'] = '상품을 찾을 수 없습니다'
                return

            # Phase 2: 키워드 추출
            _goldbox_state['phase'] = 'extracting'
            keywords = _extract_keywords_from_products(products)
            _goldbox_state['keywords'] = keywords
            _goldbox_state['total'] = min(len(keywords), max_scan)

            # Phase 3: 윙 스캔
            _goldbox_state['phase'] = 'scanning'
            api = get_helpstore()
            db = get_db()

            for i, kw in enumerate(keywords[:max_scan]):
                if not _goldbox_state['running']:
                    break

                _goldbox_state['current'] = kw
                _goldbox_state['scanned'] = i

                try:
                    # 윙 스캔
                    cursor = db.execute(
                        "INSERT INTO market_scans (keyword, scan_type, status) VALUES (?, 'goldbox', 'scanning')",
                        (kw,))
                    db.commit()
                    scan_id = cursor.lastrowid

                    scan_products = wing_search(kw)

                    for p in scan_products:
                        db.execute('''
                            INSERT INTO products (scan_id, ranking, product_name, brand,
                                manufacturer, price, sales_monthly, revenue_monthly,
                                review_count, click_count, conversion_rate, page_views,
                                category, category_code, product_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (scan_id, p.ranking, p.product_name, p.brand,
                              p.manufacturer, p.price, p.sales_monthly,
                              p.revenue_monthly, p.review_count, p.click_count,
                              p.conversion_rate, p.page_views, p.category,
                              p.category_code, p.product_url))

                    related = api.get_related_keywords(kw)
                    opp = calculate_opportunity(products=scan_products, related_keywords=related, keyword=kw)

                    db.execute('''
                        UPDATE market_scans SET status='scanned', category=?, opportunity_score=?,
                            top10_avg_revenue=?, top10_avg_sales=?, top10_avg_price=?,
                            revenue_concentration=?, revenue_equality=?,
                            new_product_rate=?, ad_dependency=?,
                            recommended_keyword=?, updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                    ''', (scan_products[0].category if scan_products else '', round(opp.total_score, 1),
                          opp.top4_10_avg_revenue, opp.top4_10_avg_sales, opp.top4_10_avg_price,
                          round(opp.top3_share*100, 1), round(opp.sellers_over_3m_rate*100, 1),
                          round(opp.new_product_rate*100, 1), round(opp.avg_new_product_weight, 1),
                          opp.recommended_keyword, scan_id))
                    db.commit()

                    _goldbox_state['results'].append({
                        'scan_id': scan_id, 'keyword': kw,
                        'score': round(opp.total_score, 1), 'grade': opp.grade,
                        'top3_share': round(opp.top3_share*100, 1),
                        'sellers_3m': opp.sellers_over_3m,
                        'sellers_3m_rate': round(opp.sellers_over_3m_rate*100, 1),
                        'entry_revenue': opp.top4_10_avg_revenue,
                        'new_weight': round(opp.avg_new_product_weight, 1),
                        'products': len(scan_products),
                    })
                except Exception as e:
                    print(f'[GOLDBOX] 스캔 에러: {kw} — {e}')
                    if 'LOGIN_REQUIRED' in str(e):
                        _goldbox_state['phase'] = 'login_required'
                        break

                import time
                time.sleep(2)

            _goldbox_state['scanned'] = min(len(keywords), max_scan)
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
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()

    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(5000)

        # 페이지에 수집 스크립트 주입 — 스크롤하면서 실시간 수집
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

        # 스크롤하면서 수집
        no_change = 0
        prev_total = 0
        for i in range(300):
            page.evaluate('window.scrollBy(0, 500)')
            page.wait_for_timeout(300)

            # 5회마다 수집 + 체크
            if i % 5 == 4:
                page.evaluate('window.__goldbox_collect()')
                total = page.evaluate('Object.keys(window.__goldbox_items).length')

                if i % 15 == 14:
                    print(f'[GOLDBOX] 스크롤 {i+1}회, 누적: {total}개')

                if total == prev_total:
                    no_change += 1
                    if no_change >= 6:  # 30회 스크롤 무변화 → 종료
                        break
                else:
                    no_change = 0
                prev_total = total

        # 마지막 수집
        page.evaluate('window.__goldbox_collect()')

        # 결과 가져오기
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


def _extract_keywords_from_products(products: list) -> list:
    """
    골드박스 상품명 → 헬프스토어 연관키워드 → 쇼핑 키워드 추출

    핵심: 브랜드 키워드(셀렉스프로틴)가 아닌 제품군 키워드(단백질 쉐이크)를 찾기
    방법: 상품명에서 개별 일반명사를 추출 → 헬프스토어 검색 → 쇼핑 키워드 수집
    """
    import re
    api = get_helpstore()
    shopping_keywords = {}
    searched = set()

    for p in products[:30]:
        name = p.get('name', '')
        words = re.findall(r'[가-힣]{2,6}', name)

        for word in words:
            # 이미 검색한 단어 스킵
            if word in searched:
                continue
            searched.add(word)

            # 1글자나 너무 일반적인 단어 스킵
            if len(word) < 2:
                continue
            # 브랜드명 스킵 (상품명 첫 단어는 보통 브랜드)
            if word == words[0] and len(words) > 2:
                continue

            try:
                related = api.get_related_keywords(word)
                for kw in related:
                    if kw.is_brand:
                        continue
                    if kw.total_search < 3000:
                        continue
                    if kw.product_count < 100:
                        continue
                    if _is_noise_keyword(kw.keyword):
                        continue
                    # 브랜드명이 키워드에 포함되면 제외
                    if words[0] in kw.keyword:
                        continue
                    if kw.keyword not in shopping_keywords:
                        shopping_keywords[kw.keyword] = kw.total_search

                import time
                time.sleep(0.3)
            except Exception:
                pass

    # 검색량 높은 순 정렬 + 중복 제거
    sorted_kws = sorted(shopping_keywords.items(), key=lambda x: x[1], reverse=True)
    result = [kw for kw, _ in sorted_kws]
    print(f'[GOLDBOX] 상품 {len(products)}개 → 쇼핑 키워드 {len(result)}개 추출')
    for kw, vol in sorted_kws[:10]:
        print(f'  {kw}: {vol:,}')
    return result


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


# === 쿠팡 키워드 API ===
_coupang_kw_cache = {}  # keyword → {autocomplete, related, ts}

@app.route('/api/scan/<int:scan_id>/keywords')
def api_scan_keywords(scan_id):
    """스캔 키워드 데이터 통합 반환 (변형 + 쿠팡 자동완성 + 연관)"""
    db = get_db()
    scan = db.execute('SELECT keyword FROM market_scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return jsonify({'success': False, 'error': '조사 기록 없음'})

    keyword = scan['keyword']

    # DB에서 키워드 변형 조회
    variants = db.execute('''
        SELECT * FROM keyword_variants WHERE scan_id = ?
    ''', (scan_id,)).fetchall()

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
        'variants': [dict(v) for v in variants],
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
        db_state = _load_reviews_from_db(scan_id)
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
    with app.app_context():
        db_conn = sqlite3.connect(DB_PATH)
        db_conn.row_factory = sqlite3.Row
        scan = db_conn.execute('SELECT keyword FROM market_scans WHERE id = ?', (scan_id,)).fetchone()
        if scan:
            keyword = scan['keyword']
        db_conn.close()

    # DB에 리뷰 저장
    _save_reviews_to_db(scan_id, reviews)

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
            _save_analysis_to_db(scan_id, keyword, len(reviews), analysis)
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
            db = get_db()
            scan = db.execute('SELECT keyword FROM market_scans WHERE id = ?', (scan_id,)).fetchone()
            if not scan:
                _review_state[scan_id] = {'status': 'error', 'reviews': [], 'analysis': None}
                return

            keyword = scan['keyword']
            products = db.execute(
                'SELECT * FROM products WHERE scan_id = ? ORDER BY ranking LIMIT 10',
                (scan_id,)
            ).fetchall()

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
            _save_reviews_to_db(scan_id, all_reviews)
            _save_analysis_to_db(scan_id, keyword, len(all_reviews), analysis)
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
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=False,
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


def _save_reviews_to_db(scan_id: int, reviews: list):
    """리뷰를 DB에 저장 (기존 데이터 교체)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM collected_reviews WHERE scan_id = ?', (scan_id,))
        for r in reviews:
            conn.execute(
                'INSERT INTO collected_reviews (scan_id, product_name, rating, headline, content, date, option) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (scan_id, r.get('product_name', ''), r.get('rating'), r.get('headline', ''), r.get('content', ''), r.get('date', ''), r.get('option', ''))
            )
        conn.commit()
        conn.close()
        print(f'[REVIEW-DB] {len(reviews)}개 리뷰 DB 저장 완료 (scan_id={scan_id})')
    except Exception as e:
        print(f'[REVIEW-DB] 저장 실패: {e}')


def _save_analysis_to_db(scan_id: int, keyword: str, review_count: int, analysis: dict):
    """분석 결과를 DB에 저장 (기존 데이터 교체)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM review_analyses WHERE scan_id = ?', (scan_id,))
        conn.execute(
            'INSERT INTO review_analyses (scan_id, keyword, review_count, analysis_json) VALUES (?, ?, ?, ?)',
            (scan_id, keyword, review_count, json.dumps(analysis, ensure_ascii=False))
        )
        conn.commit()
        conn.close()
        print(f'[REVIEW-DB] 분석 결과 DB 저장 완료 (scan_id={scan_id})')
    except Exception as e:
        print(f'[REVIEW-DB] 분석 저장 실패: {e}')


def _load_reviews_from_db(scan_id: int) -> dict:
    """DB에서 리뷰 + 분석 결과 로드하여 _review_state 형태로 반환"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        reviews = conn.execute('SELECT * FROM collected_reviews WHERE scan_id = ?', (scan_id,)).fetchall()
        analysis_row = conn.execute('SELECT * FROM review_analyses WHERE scan_id = ? ORDER BY analyzed_at DESC LIMIT 1', (scan_id,)).fetchone()
        conn.close()

        if not reviews and not analysis_row:
            return None

        review_list = [
            {'product_name': r['product_name'], 'rating': r['rating'], 'headline': r['headline'], 'content': r['content'], 'date': r['date'], 'option': r['option']}
            for r in reviews
        ]
        analysis = json.loads(analysis_row['analysis_json']) if analysis_row else None
        return {
            'status': 'done' if analysis else 'collecting',
            'reviews': review_list,
            'analysis': analysis
        }
    except Exception as e:
        print(f'[REVIEW-DB] 로드 실패: {e}')
        return None


def _load_all_reviews_from_db():
    """서버 시작 시 DB에서 모든 리뷰 상태 로드"""
    global _review_state
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        scan_ids = conn.execute('SELECT DISTINCT scan_id FROM collected_reviews').fetchall()
        for row in scan_ids:
            sid = row['scan_id']
            state = _load_reviews_from_db(sid)
            if state:
                _review_state[sid] = state
        conn.close()
        if _review_state:
            print(f'[REVIEW-DB] {len(_review_state)}개 스캔의 리뷰 데이터 DB에서 로드 완료')
    except Exception as e:
        print(f'[REVIEW-DB] 초기 로드 실패: {e}')


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
        state = _load_reviews_from_db(scan_id)
    if not state or not state.get('reviews'):
        return jsonify({'error': '리뷰 데이터가 없습니다. 먼저 리뷰 분석을 실행해주세요.'})

    reviews = state['reviews']

    # 키워드 조회
    keyword = ''
    db = get_db()
    scan = db.execute('SELECT keyword FROM market_scans WHERE id = ?', (scan_id,)).fetchone()
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

    # Claude API 호출
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        from analyzer.reviews import ANTHROPIC_API_KEY
        api_key = ANTHROPIC_API_KEY
    if not api_key:
        return jsonify({'error': 'ANTHROPIC_API_KEY가 설정되지 않았습니다.'})

    try:
        import requests as req
        resp = req.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 1024,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=30
        )
        result = resp.json()
        if 'content' in result and len(result['content']) > 0:
            answer = result['content'][0].get('text', '')
            return jsonify({'answer': answer})
        else:
            error_msg = result.get('error', {}).get('message', str(result))
            return jsonify({'error': f'API 오류: {error_msg}'})
    except Exception as e:
        return jsonify({'error': f'API 호출 실패: {str(e)}'})


@app.route('/api/scan/<int:scan_id>/status', methods=['PUT'])
def update_scan_status(scan_id):
    """스캔 상태 변경 (go / pass)"""
    data = request.get_json(silent=True) or {}
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
    status_filter = request.args.get('status', '')

    if status_filter == 'go':
        scans = db.execute('''
            SELECT * FROM market_scans WHERE status = 'go'
            ORDER BY opportunity_score DESC
        ''').fetchall()
    elif status_filter == 'scanned':
        scans = db.execute('''
            SELECT * FROM market_scans WHERE status = 'scanned' AND opportunity_score IS NOT NULL
            ORDER BY opportunity_score DESC LIMIT 50
        ''').fetchall()
    else:
        scans = db.execute('''
            SELECT * FROM market_scans WHERE opportunity_score IS NOT NULL
            ORDER BY opportunity_score DESC LIMIT 50
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


@app.route('/api/scan/<int:scan_id>/rfq/generate', methods=['POST'])
def generate_rfq_from_scan(scan_id):
    """GO 판정된 스캔의 상품 데이터를 분석하여 RFQ 자동 생성"""
    db = get_db()

    # 스캔 조회
    scan = db.execute('SELECT * FROM market_scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return jsonify({'success': False, 'error': '스캔을 찾을 수 없습니다'})

    scan_dict = dict(scan)
    if scan_dict.get('status') != 'go':
        return jsonify({'success': False, 'error': 'GO 판정된 스캔만 RFQ 생성이 가능합니다'})

    # 상위 40개 상품 조회
    products = db.execute('''
        SELECT * FROM products WHERE scan_id = ?
        ORDER BY ranking ASC LIMIT 40
    ''', (scan_id,)).fetchall()

    if not products:
        return jsonify({'success': False, 'error': '상품 데이터가 없습니다'})

    products = [dict(p) for p in products]

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

    # API 키 — 환경변수 → reviews.py 순서로 체크
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not anthropic_key:
        try:
            from analyzer.reviews import ANTHROPIC_API_KEY as _rfq_key
            anthropic_key = _rfq_key
        except:
            pass
    # 리뷰 분석의 chat 엔드포인트에서 쓰는 방식과 동일하게
    if not anthropic_key:
        for env_name in ['ANTHROPIC_API_KEY', 'CLAUDE_API_KEY']:
            anthropic_key = os.environ.get(env_name, '')
            if anthropic_key:
                break
    if anthropic_key and len(top10_names) > 0:
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
            import requests as _requests
            resp = _requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': anthropic_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json'
                },
                json={
                    'model': 'claude-haiku-4-5-20251001',
                    'max_tokens': 1024,
                    'messages': [{'role': 'user', 'content': prompt_text}]
                },
                timeout=30
            )
            if resp.ok:
                ai_text = resp.json()['content'][0]['text'].strip()
                print(f'[RFQ] AI 스펙 생성 성공: {ai_text[:100]}')
                # JSON 블록 추출 (```json ... ``` 감싸진 경우 대비)
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
    db = get_db()

    specs = data.get('specifications') or data.get('specs', [])
    certs = data.get('certifications', [])

    cursor = db.execute('''
        INSERT INTO rfqs (scan_id, product_name_en, product_name_kr, category,
                         specifications, target_price, target_price_currency,
                         order_quantity, moq, shipping_terms, certifications, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
    ''', (
        data.get('scan_id'),
        data.get('product_name_en', ''),
        data.get('product_name_kr', data.get('product_name', '')),
        data.get('category', ''),
        json.dumps(specs if isinstance(specs, (list, dict)) else specs, ensure_ascii=False),
        data.get('target_price') or data.get('target_price_usd'),
        data.get('target_price_currency', 'USD'),
        data.get('order_quantity') or data.get('suggested_moq'),
        data.get('moq') or data.get('suggested_moq'),
        data.get('shipping_terms', 'FOB'),
        json.dumps(certs if isinstance(certs, list) else [certs], ensure_ascii=False)
    ))
    db.commit()

    return jsonify({'success': True, 'rfq_id': cursor.lastrowid})


@app.route('/api/rfqs')
def get_rfqs():
    """RFQ 목록 조회"""
    db = get_db()
    rfqs = db.execute('SELECT * FROM rfqs ORDER BY created_at DESC').fetchall()
    return jsonify({'success': True, 'rfqs': [dict(r) for r in rfqs]})


@app.route('/api/rfq/<int:rfq_id>', methods=['PUT'])
def update_rfq(rfq_id):
    """RFQ 수정"""
    data = request.get_json(silent=True) or {}
    db = get_db()

    # 존재 확인
    rfq = db.execute('SELECT id FROM rfqs WHERE id = ?', (rfq_id,)).fetchone()
    if not rfq:
        return jsonify({'success': False, 'error': 'RFQ 없음'})

    # certifications: 쉼표 구분 문자열 → JSON 배열로 변환
    certs_raw = data.get('certifications', '')
    if isinstance(certs_raw, str):
        certs = json.dumps([c.strip() for c in certs_raw.split(',') if c.strip()], ensure_ascii=False)
    else:
        certs = json.dumps(certs_raw, ensure_ascii=False)

    db.execute('''
        UPDATE rfqs SET
            product_name_kr = ?, product_name_en = ?, category = ?,
            specifications = ?, target_price = ?, order_quantity = ?,
            moq = ?, shipping_terms = ?, certifications = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        data.get('product_name_kr'), data.get('product_name_en'),
        data.get('category'), data.get('specifications'),
        data.get('target_price'), data.get('order_quantity'),
        data.get('moq'), data.get('shipping_terms'),
        certs, rfq_id
    ))
    db.commit()
    return jsonify({'success': True})


@app.route('/api/rfq/<int:rfq_id>', methods=['DELETE'])
def delete_rfq(rfq_id):
    """RFQ 삭제"""
    db = get_db()
    db.execute('DELETE FROM quotations WHERE rfq_id = ?', (rfq_id,))
    db.execute('DELETE FROM rfqs WHERE id = ?', (rfq_id,))
    db.commit()
    return jsonify({'success': True})


@app.route('/api/rfq/<int:rfq_id>/publish', methods=['POST'])
def publish_rfq(rfq_id):
    """RFQ 영문 변환 + 알리바바 발행 준비"""
    db = get_db()
    rfq = db.execute('SELECT * FROM rfqs WHERE id = ?', (rfq_id,)).fetchone()
    if not rfq:
        return jsonify({'success': False, 'error': 'RFQ not found'})

    rfq = dict(rfq)
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

Sign as: Becore Lab Co., Ltd. / kychung@becorelab.kr

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
    db.execute('UPDATE rfqs SET product_name_en = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
               (english_data.get('product_name_en', product_name_kr), 'ready', rfq_id))
    db.commit()

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
            pw = sync_playwright().start()
            browser = pw.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
            page = browser.new_page()

            # 알리바바 RFQ 페이지 열기
            page.goto('https://sourcing.alibaba.com/rfq/post_request.htm', wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)

            # 로그인 필요하면 대기 (최대 2분)
            if 'login' in page.url.lower():
                print('[ALIBABA] 로그인 필요 — 브라우저에서 로그인해주세요')
                for _ in range(120):
                    page.wait_for_timeout(1000)
                    if 'login' not in page.url.lower():
                        break
                page.wait_for_timeout(2000)

            # RFQ 폼 채우기
            try:
                # 제품명
                name_input = page.locator('input[name*="subject"], input[placeholder*="product"], input[name*="productName"], #subject').first
                if name_input.count() > 0:
                    name_input.fill(product_name)

                # 수량
                qty_input = page.locator('input[name*="quantity"], input[name*="qty"], input[placeholder*="quantity"]').first
                if qty_input.count() > 0:
                    qty_input.fill(str(quantity))

                # 상세 내용
                detail_input = page.locator('textarea[name*="detail"], textarea[name*="description"], textarea[placeholder*="detail"], textarea').first
                if detail_input.count() > 0:
                    detail_input.fill(english_message)

                print(f'[ALIBABA] RFQ 폼 자동 채움 완료: {product_name}')
            except Exception as e:
                print(f'[ALIBABA] 폼 채우기 부분 실패: {e}')
                # 실패해도 페이지는 열어둠 — 사용자가 수동으로 입력 가능

            # 브라우저 열어둠 (사용자가 확인 후 직접 제출) — 2분 대기
            page.wait_for_timeout(120000)

            browser.close()
            pw.stop()
        except Exception as e:
            print(f'[ALIBABA] 자동 발행 에러: {e}')
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
    _load_all_reviews_from_db()
    print("\n[BECORELAB] Market Finder v0.1")
    print("[BECORELAB] http://localhost:8090\n")
    app.run(host='0.0.0.0', port=8090, debug=True, use_reloader=False)
