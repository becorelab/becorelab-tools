"""
비코어랩 소싱콕 — Firestore DB 레이어
SQLite → Firestore 전환 모듈

컬렉션 구조:
  _meta/counters          — 자동 증가 ID 카운터
  market_scans/{id}       — 시장조사 기록
  products/{auto}         — 상품 상세 (scan_id 필드)
  inflow_keywords/{auto}  — 유입 키워드 (scan_id 필드)
  keyword_variants/{auto} — 키워드 변형 (scan_id 필드)
  rfqs/{id}               — 견적 요청
  quotations/{id}         — 업체 견적 (rfq_id 필드)
  sourcing_history/{id}   — 소싱 히스토리
  goldbox_daily/{auto}    — 골드박스 일별 기록
  collected_reviews/{auto} — 수집 리뷰 (scan_id 필드)
  review_analyses/{auto}  — 리뷰 분석 (scan_id 필드)
"""

import os
import json
from datetime import datetime, timezone
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials

# ── 초기화 ──
_db = None

def _get_key_path():
    """Firebase 서비스 계정 키 파일 경로 자동 탐색"""
    analyzer_dir = os.path.dirname(os.path.abspath(__file__))
    for f in os.listdir(analyzer_dir):
        if f.endswith('.json') and 'firebase-adminsdk' in f:
            return os.path.join(analyzer_dir, f)
    raise FileNotFoundError('Firebase 서비스 계정 키 파일을 찾을 수 없습니다.')


def init_firestore():
    """Firestore 클라이언트 초기화 (앱 시작 시 1회 호출)"""
    global _db
    if _db is not None:
        return _db

    key_path = _get_key_path()
    cred = credentials.Certificate(key_path)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

    _db = firestore.Client.from_service_account_json(key_path)
    print(f'[FIRESTORE] 연결 완료: {_db.project}')
    return _db


def db():
    """Firestore 클라이언트 반환 (thread-safe)"""
    global _db
    if _db is None:
        init_firestore()
    return _db


def _now():
    """현재 시각 문자열 (SQLite CURRENT_TIMESTAMP 호환)"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


# ── 자동 증가 ID ──
def _next_id(collection_name: str) -> int:
    """Firestore 트랜잭션으로 안전한 자동 증가 ID 생성"""
    counter_ref = db().collection('_meta').document('counters')

    @firestore.transactional
    def _increment(transaction):
        snapshot = counter_ref.get(transaction=transaction)
        data = snapshot.to_dict() or {}
        current = data.get(collection_name, 0)
        new_id = current + 1
        transaction.update(counter_ref, {collection_name: new_id})
        return new_id

    transaction = db().transaction()

    # 카운터 문서가 없으면 생성
    if not counter_ref.get().exists:
        counter_ref.set({})

    return _increment(transaction)


# ══════════════════════════════════════════════
# market_scans
# ══════════════════════════════════════════════
def create_scan(keyword: str, scan_type: str = 'manual', status: str = 'scanning') -> int:
    """스캔 생성, 정수 ID 반환"""
    scan_id = _next_id('market_scans')
    db().collection('market_scans').document(str(scan_id)).set({
        'id': scan_id,
        'keyword': keyword,
        'scan_type': scan_type,
        'status': status,
        'category': None,
        'opportunity_score': None,
        'top10_avg_revenue': None,
        'top10_avg_sales': None,
        'top10_avg_price': None,
        'revenue_concentration': None,
        'revenue_equality': None,
        'new_product_rate': None,
        'ad_dependency': None,
        'recommended_keyword': None,
        'scanned_at': _now(),
        'updated_at': _now(),
    })
    return scan_id


def update_scan(scan_id: int, **fields):
    """스캔 필드 업데이트"""
    fields['updated_at'] = _now()
    db().collection('market_scans').document(str(scan_id)).update(fields)


def get_scan(scan_id: int) -> dict:
    """스캔 1건 조회 (없으면 None)"""
    doc = db().collection('market_scans').document(str(scan_id)).get()
    return doc.to_dict() if doc.exists else None


def list_scans(limit: int = 100) -> list:
    """스캔 목록 (최신순)"""
    docs = (db().collection('market_scans')
            .order_by('scanned_at', direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream())
    return [d.to_dict() for d in docs]


def get_opportunities(status_filter: str = '') -> list:
    """기회점수 랭킹"""
    ref = db().collection('market_scans')
    if status_filter in ('go', 'scanned'):
        query = ref.where('status', '==', status_filter)
    else:
        query = ref
    results = []
    for d in query.stream():
        data = d.to_dict()
        if data.get('opportunity_score') is not None:
            results.append(data)
    # Python에서 정렬 (Firestore 복합 인덱스 불필요)
    results.sort(key=lambda x: x.get('opportunity_score', 0), reverse=True)
    if status_filter != 'go':
        results = results[:50]
    return results


# ══════════════════════════════════════════════
# products
# ══════════════════════════════════════════════
def add_product(scan_id: int, product: dict):
    """상품 1건 추가"""
    product['scan_id'] = scan_id
    db().collection('products').add(product)


def save_products_batch(scan_id: int, products: list):
    """상품 일괄 저장 (batch write)"""
    batch = db().batch()
    col = db().collection('products')
    for p in products:
        p['scan_id'] = scan_id
        ref = col.document()
        batch.set(ref, p)
    batch.commit()


def get_products(scan_id: int) -> list:
    """스캔의 상품 목록"""
    docs = (db().collection('products')
            .where('scan_id', '==', scan_id)
            .stream())
    results = [d.to_dict() for d in docs]
    results.sort(key=lambda x: x.get('ranking', 9999))
    return results


# ══════════════════════════════════════════════
# inflow_keywords
# ══════════════════════════════════════════════
def add_inflow_keyword(scan_id: int, kw: dict):
    """유입 키워드 1건 추가"""
    kw['scan_id'] = scan_id
    db().collection('inflow_keywords').add(kw)


def save_inflow_keywords_batch(scan_id: int, keywords: list):
    """유입 키워드 일괄 저장"""
    batch = db().batch()
    col = db().collection('inflow_keywords')
    for kw in keywords:
        kw['scan_id'] = scan_id
        ref = col.document()
        batch.set(ref, kw)
    batch.commit()


def get_inflow_keywords(scan_id: int) -> list:
    """스캔의 유입 키워드 목록"""
    docs = (db().collection('inflow_keywords')
            .where('scan_id', '==', scan_id)
            .stream())
    results = [d.to_dict() for d in docs]
    results.sort(key=lambda x: x.get('search_volume', 0), reverse=True)
    return results


# ══════════════════════════════════════════════
# keyword_variants
# ══════════════════════════════════════════════
def add_keyword_variant(scan_id: int, variant: dict):
    """키워드 변형 1건 추가"""
    variant['scan_id'] = scan_id
    db().collection('keyword_variants').add(variant)


def get_keyword_variants(scan_id: int) -> list:
    """스캔의 키워드 변형 목록"""
    docs = (db().collection('keyword_variants')
            .where('scan_id', '==', scan_id)
            .stream())
    return [d.to_dict() for d in docs]


# ══════════════════════════════════════════════
# goldbox_daily
# ══════════════════════════════════════════════
def add_goldbox_products(date: str, products: list):
    """골드박스 일별 상품 일괄 저장"""
    batch = db().batch()
    col = db().collection('goldbox_daily')
    for p in products:
        p['crawled_date'] = date
        p['crawled_at'] = _now()
        ref = col.document()
        batch.set(ref, p)
    batch.commit()


def get_goldbox_dates(limit: int = 30) -> list:
    """골드박스 날짜별 상품 수"""
    # Firestore에는 GROUP BY가 없으므로 날짜별로 집계
    docs = (db().collection('goldbox_daily')
            .order_by('crawled_date', direction=firestore.Query.DESCENDING)
            .stream())

    date_counts = {}
    for d in docs:
        data = d.to_dict()
        dt = data.get('crawled_date', '')
        date_counts[dt] = date_counts.get(dt, 0) + 1
        if len(date_counts) > limit:
            break

    return [{'crawled_date': k, 'count': v}
            for k, v in sorted(date_counts.items(), reverse=True)[:limit]]


def get_goldbox_by_date(date: str) -> list:
    """특정 날짜의 골드박스 상품"""
    docs = (db().collection('goldbox_daily')
            .where('crawled_date', '==', date)
            .stream())
    return [d.to_dict() for d in docs]


# ══════════════════════════════════════════════
# rfqs
# ══════════════════════════════════════════════
def create_rfq(**fields) -> int:
    """RFQ 생성, 정수 ID 반환"""
    rfq_id = _next_id('rfqs')
    fields['id'] = rfq_id
    fields['status'] = fields.get('status', 'draft')
    fields['created_at'] = _now()
    fields['updated_at'] = _now()
    db().collection('rfqs').document(str(rfq_id)).set(fields)
    return rfq_id


def get_rfq(rfq_id: int) -> dict:
    """RFQ 1건 조회"""
    doc = db().collection('rfqs').document(str(rfq_id)).get()
    return doc.to_dict() if doc.exists else None


def list_rfqs() -> list:
    """RFQ 목록 (최신순)"""
    docs = (db().collection('rfqs')
            .order_by('created_at', direction=firestore.Query.DESCENDING)
            .stream())
    return [d.to_dict() for d in docs]


def update_rfq(rfq_id: int, **fields):
    """RFQ 업데이트"""
    fields['updated_at'] = _now()
    db().collection('rfqs').document(str(rfq_id)).update(fields)


def delete_rfq(rfq_id: int):
    """RFQ 삭제 (연관 견적도 삭제)"""
    # 견적 삭제
    quotes = (db().collection('quotations')
              .where('rfq_id', '==', rfq_id)
              .stream())
    batch = db().batch()
    for q in quotes:
        batch.delete(q.reference)
    batch.commit()

    # RFQ 삭제
    db().collection('rfqs').document(str(rfq_id)).delete()


# ══════════════════════════════════════════════
# quotations
# ══════════════════════════════════════════════
def add_quotation(**fields) -> int:
    """견적 추가, 정수 ID 반환"""
    quote_id = _next_id('quotations')
    fields['id'] = quote_id
    fields['is_selected'] = fields.get('is_selected', 0)
    fields['received_at'] = _now()
    db().collection('quotations').document(str(quote_id)).set(fields)
    return quote_id


def get_quotations(rfq_id: int) -> list:
    """RFQ의 견적 목록"""
    docs = (db().collection('quotations')
            .where('rfq_id', '==', rfq_id)
            .stream())
    results = [d.to_dict() for d in docs]
    results.sort(key=lambda x: x.get('unit_price', 9999999))
    return results


def get_quotation(quote_id: int) -> dict:
    """견적 1건 조회"""
    doc = db().collection('quotations').document(str(quote_id)).get()
    return doc.to_dict() if doc.exists else None


def update_quotation(quote_id: int, **fields):
    """견적 업데이트"""
    db().collection('quotations').document(str(quote_id)).update(fields)


def delete_quotation(quote_id: int):
    """견적 삭제"""
    db().collection('quotations').document(str(quote_id)).delete()


def select_quotation(quote_id: int):
    """업체 선정 (해당 RFQ의 다른 견적은 선정 해제)"""
    quote = get_quotation(quote_id)
    if not quote:
        return
    rfq_id = quote['rfq_id']

    # 같은 RFQ의 모든 견적 선정 해제
    quotes = (db().collection('quotations')
              .where('rfq_id', '==', rfq_id)
              .stream())
    batch = db().batch()
    for q in quotes:
        batch.update(q.reference, {'is_selected': 0})
    batch.commit()

    # 선택된 견적만 선정
    update_quotation(quote_id, is_selected=1)
    update_rfq(rfq_id, status='closed')


# ══════════════════════════════════════════════
# collected_reviews
# ══════════════════════════════════════════════
def save_reviews(scan_id: int, reviews: list):
    """리뷰 저장 (기존 데이터 교체)"""
    # 기존 삭제
    old_docs = (db().collection('collected_reviews')
                .where('scan_id', '==', scan_id)
                .stream())
    batch = db().batch()
    count = 0
    for d in old_docs:
        batch.delete(d.reference)
        count += 1
        if count >= 400:  # batch 제한 500에 여유 남기기
            batch.commit()
            batch = db().batch()
            count = 0
    if count > 0:
        batch.commit()

    # 새로 저장
    batch = db().batch()
    col = db().collection('collected_reviews')
    count = 0
    for r in reviews:
        r['scan_id'] = scan_id
        r['collected_at'] = _now()
        ref = col.document()
        batch.set(ref, r)
        count += 1
        if count >= 400:
            batch.commit()
            batch = db().batch()
            count = 0
    if count > 0:
        batch.commit()

    print(f'[FIRESTORE] {len(reviews)}개 리뷰 저장 완료 (scan_id={scan_id})')


def get_reviews(scan_id: int) -> list:
    """스캔의 리뷰 목록"""
    docs = (db().collection('collected_reviews')
            .where('scan_id', '==', scan_id)
            .stream())
    return [d.to_dict() for d in docs]


# ══════════════════════════════════════════════
# review_analyses
# ══════════════════════════════════════════════
def save_review_analysis(scan_id: int, keyword: str, review_count: int, analysis: dict):
    """분석 결과 저장 (기존 데이터 교체)"""
    # 기존 삭제
    old_docs = (db().collection('review_analyses')
                .where('scan_id', '==', scan_id)
                .stream())
    batch = db().batch()
    for d in old_docs:
        batch.delete(d.reference)
    batch.commit()

    # 새로 저장
    db().collection('review_analyses').add({
        'scan_id': scan_id,
        'keyword': keyword,
        'review_count': review_count,
        'analysis_json': json.dumps(analysis, ensure_ascii=False),
        'analyzed_at': _now(),
    })
    print(f'[FIRESTORE] 분석 결과 저장 완료 (scan_id={scan_id})')


def get_review_analysis(scan_id: int) -> dict:
    """스캔의 최신 분석 결과"""
    docs = list(db().collection('review_analyses')
                .where('scan_id', '==', scan_id)
                .stream())
    if not docs:
        return None
    # 인덱스 없이도 작동하도록 Python에서 정렬
    results = [d.to_dict() for d in docs]
    results.sort(key=lambda x: x.get('analyzed_at', ''), reverse=True)
    return results[0]


# ══════════════════════════════════════════════
# detail_analyses (상세 분석)
# ══════════════════════════════════════════════
def save_detail_analysis(scan_id: int, keyword: str, analysis: dict):
    """상세 분석 결과 저장"""
    old_docs = (db().collection('detail_analyses')
                .where('scan_id', '==', scan_id)
                .stream())
    batch = db().batch()
    for d in old_docs:
        batch.delete(d.reference)
    batch.commit()

    db().collection('detail_analyses').add({
        'scan_id': scan_id,
        'keyword': keyword,
        'analysis_json': json.dumps(analysis, ensure_ascii=False),
        'analyzed_at': _now(),
    })


def get_detail_analysis(scan_id: int) -> dict:
    """상세 분석 결과 조회"""
    docs = list(db().collection('detail_analyses')
                .where('scan_id', '==', scan_id)
                .stream())
    if not docs:
        return None
    results = [d.to_dict() for d in docs]
    results.sort(key=lambda x: x.get('analyzed_at', ''), reverse=True)
    data = results[0]
    try:
        return json.loads(data.get('analysis_json', '{}'))
    except (json.JSONDecodeError, KeyError):
        return None


def get_scan_ids_with_reviews() -> list:
    """리뷰가 있는 scan_id 목록"""
    docs = db().collection('collected_reviews').stream()
    scan_ids = set()
    for d in docs:
        data = d.to_dict()
        sid = data.get('scan_id')
        if sid is not None:
            scan_ids.add(sid)
    return list(scan_ids)


# ══════════════════════════════════════════════
# sourcing_history (JOIN 대체)
# ══════════════════════════════════════════════
def get_history() -> list:
    """소싱 히스토리 (scan/rfq 키워드 포함)"""
    docs = (db().collection('sourcing_history')
            .order_by('updated_at', direction=firestore.Query.DESCENDING)
            .stream())
    results = []
    for d in docs:
        h = d.to_dict()
        # JOIN 대체: scan_keyword, rfq_product 추가
        if h.get('scan_id'):
            scan = get_scan(h['scan_id'])
            h['scan_keyword'] = scan.get('keyword', '') if scan else ''
        if h.get('rfq_id'):
            rfq = get_rfq(h['rfq_id'])
            h['rfq_product'] = rfq.get('product_name_kr', '') if rfq else ''
        results.append(h)
    return results


# ══════════════════════════════════════════════
# 대시보드 통계
# ══════════════════════════════════════════════
def get_stats() -> dict:
    """대시보드 통계"""
    scans = list(db().collection('market_scans').stream())
    scan_list = [s.to_dict() for s in scans]

    total_scans = len(scan_list)
    auto_scans = sum(1 for s in scan_list if s.get('scan_type') == 'auto')
    manual_scans = sum(1 for s in scan_list if s.get('scan_type') == 'manual')
    go_products = sum(1 for s in scan_list if s.get('status') == 'go')

    rfqs = list(db().collection('rfqs').stream())
    rfq_list = [r.to_dict() for r in rfqs]
    active_rfqs = sum(1 for r in rfq_list if r.get('status') in ('posted', 'receiving'))

    total_quotations = len(list(db().collection('quotations').stream()))

    top_opportunity = None
    scored = [s for s in scan_list if s.get('opportunity_score') is not None]
    if scored:
        best = max(scored, key=lambda s: s['opportunity_score'])
        top_opportunity = {'keyword': best['keyword'], 'score': best['opportunity_score']}

    return {
        'total_scans': total_scans,
        'auto_scans': auto_scans,
        'manual_scans': manual_scans,
        'go_products': go_products,
        'active_rfqs': active_rfqs,
        'total_quotations': total_quotations,
        'top_opportunity': top_opportunity,
    }


# ══════════════════════════════════════════════
# 리뷰 상태 로드 (서버 시작 시)
# ══════════════════════════════════════════════
def load_reviews_from_db(scan_id: int) -> dict:
    """DB에서 리뷰 + 분석 결과 로드하여 _review_state 형태로 반환"""
    reviews = get_reviews(scan_id)
    analysis_data = get_review_analysis(scan_id)

    if not reviews and not analysis_data:
        return None

    review_list = [
        {
            'product_name': r.get('product_name', ''),
            'rating': r.get('rating'),
            'headline': r.get('headline', ''),
            'content': r.get('content', ''),
            'date': r.get('date', ''),
            'option': r.get('option', ''),
        }
        for r in reviews
    ]

    analysis = None
    if analysis_data:
        try:
            analysis = json.loads(analysis_data['analysis_json'])
        except (json.JSONDecodeError, KeyError):
            analysis = None

    return {
        'status': 'done' if analysis else 'collecting',
        'reviews': review_list,
        'analysis': analysis,
    }


def load_all_reviews() -> dict:
    """서버 시작 시 모든 리뷰 상태 로드"""
    review_state = {}
    scan_ids = get_scan_ids_with_reviews()
    for sid in scan_ids:
        state = load_reviews_from_db(sid)
        if state:
            review_state[sid] = state
    if review_state:
        print(f'[FIRESTORE] {len(review_state)}개 스캔의 리뷰 데이터 로드 완료')
    return review_state
