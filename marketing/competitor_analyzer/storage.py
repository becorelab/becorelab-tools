"""
비코어랩 경쟁분석 — Firebase Firestore 저장/조회 모듈

컬렉션 구조:
  competitor_analysis/                         ← 메인 컬렉션
    {product_key}_{date}/                      ← 문서 ID (예: 캡슐세제_2026-04-26)
      product, analyzed_at, priority_score,
      our_product, market_summary, ...요약 데이터
      products/ (서브컬렉션)
        competitor_{idx} — competitors_table 상품
        multi_{idx}      — multi_keyword_products 상품
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger(__name__)

# ── Firestore 클라이언트 싱글톤 ──────────────────────────────────────────────
_db = None


def _find_key_path() -> str | None:
    """Firebase 서비스 계정 키 파일 자동 탐색.

    우선순위:
    1. 환경변수 GOOGLE_APPLICATION_CREDENTIALS
    2. 소싱앱 디렉토리 (../sourcing/analyzer/) — 기존 키 공유
    3. 현재 디렉토리 (competitor_analyzer/)
    """
    # 1) 환경변수
    env_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2) 소싱앱 디렉토리에서 탐색 (becorelab-tools-firebase-adminsdk-*.json)
    sourcing_analyzer_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),  # competitor_analyzer/
        '..', '..', 'sourcing', 'analyzer',
    )
    sourcing_analyzer_dir = os.path.normpath(sourcing_analyzer_dir)
    if os.path.isdir(sourcing_analyzer_dir):
        for fname in os.listdir(sourcing_analyzer_dir):
            if fname.endswith('.json') and 'firebase-adminsdk' in fname:
                return os.path.join(sourcing_analyzer_dir, fname)

    # 3) 현재 디렉토리
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for fname in os.listdir(current_dir):
        if fname.endswith('.json') and 'firebase-adminsdk' in fname:
            return os.path.join(current_dir, fname)

    return None


def _get_db() -> firestore.Client | None:
    """Firestore 클라이언트 반환. 초기화 실패 시 None 반환."""
    global _db
    if _db is not None:
        return _db

    key_path = _find_key_path()
    if not key_path:
        logger.warning('[COMPETITOR_STORAGE] Firebase 키 파일을 찾을 수 없습니다. Firebase 저장 비활성화.')
        return None

    try:
        # 기존 firebase_admin 앱이 이미 초기화돼 있으면 재사용
        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            logger.info('[COMPETITOR_STORAGE] Firebase 앱 초기화 완료')
        else:
            logger.info('[COMPETITOR_STORAGE] 기존 Firebase 앱 재사용')

        _db = firestore.Client.from_service_account_json(key_path)
        logger.info('[COMPETITOR_STORAGE] Firestore 연결 완료: project=%s', _db.project)
        return _db

    except Exception as e:
        logger.warning('[COMPETITOR_STORAGE] Firestore 초기화 실패: %s', e)
        return None


def _now_str() -> str:
    """현재 시각 문자열 (UTC, ISO 포맷)"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def _to_serializable(obj):
    """datetime 등 JSON 직렬화 불가 타입을 str으로 변환"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_serializable(i) for i in obj]
    return obj


def _make_doc_id(product_key: str, date: str) -> str:
    """문서 ID 생성 (예: 캡슐세제_2026-04-26)"""
    # Firestore 문서 ID에 '/'는 사용 불가 → 안전 문자만 사용
    safe_key = product_key.replace('/', '_').replace(' ', '_')
    return f'{safe_key}_{date}'


# ── 저장 ───────────────────────────────────────────────────────────────────

def save_analysis(analysis: dict) -> str:
    """
    경쟁 분석 결과를 Firestore에 저장.

    - 메인 문서: 요약 데이터 (market_summary, price/review analysis 등)
    - 서브컬렉션 products/: competitors_table + multi_keyword_products 개별 상품

    Returns:
        저장된 문서 ID (예: '캡슐세제_2026-04-26'), 실패 시 빈 문자열
    """
    client = _get_db()
    if client is None:
        return ''

    try:
        from competitor_analyzer.config import FIREBASE_COLLECTION
    except ImportError:
        FIREBASE_COLLECTION = 'competitor_analysis'

    product_key = analysis.get('product', 'unknown')
    analyzed_at = analysis.get('analyzed_at', _now_str())

    # analyzed_at이 datetime 객체면 str로 변환
    if isinstance(analyzed_at, datetime):
        analyzed_at = analyzed_at.isoformat()

    # 날짜 파싱 (analyzed_at에서 YYYY-MM-DD 추출)
    try:
        date_str = analyzed_at[:10]  # 'YYYY-MM-DD'
    except Exception:
        date_str = datetime.now().strftime('%Y-%m-%d')

    doc_id = _make_doc_id(product_key, date_str)

    # ── 메인 문서 데이터 구성 ────────────────────────────────────────────
    # competitors_table, multi_keyword_products는 서브컬렉션으로 분리
    competitors_table = analysis.get('competitors_table', [])
    multi_keyword_products = analysis.get('multi_keyword_products', [])

    main_doc = {
        'product': product_key,
        'analyzed_at': analyzed_at,
        'priority_score': analysis.get('priority_score', 0.0),
        'our_product': _to_serializable(analysis.get('our_product', {})),
        'market_summary': _to_serializable(analysis.get('market_summary', {})),
        'multi_keyword_summary': _to_serializable(analysis.get('multi_keyword_summary', {})),
        'price_analysis': _to_serializable(analysis.get('price_analysis', {})),
        'review_analysis': _to_serializable(analysis.get('review_analysis', {})),
        'mall_grade_analysis': _to_serializable(analysis.get('mall_grade_analysis', {})),
        'keyword_analysis': _to_serializable(analysis.get('keyword_analysis', {})),
        'ranking_trend': _to_serializable(analysis.get('ranking_trend', {})),
        'traffic_analysis': _to_serializable(analysis.get('traffic_analysis', {})),
        'diagnosis': _to_serializable(analysis.get('diagnosis', [])),
        'recommendations': _to_serializable(analysis.get('recommendations', [])),
        'our_brand_products': _to_serializable(analysis.get('our_brand_products', [])),
        'competitors_count': len(competitors_table),
        'multi_keyword_products_count': len(multi_keyword_products),
        'saved_at': _now_str(),
    }

    # ── 메인 문서 저장 ───────────────────────────────────────────────────
    doc_ref = client.collection(FIREBASE_COLLECTION).document(doc_id)
    doc_ref.set(main_doc)
    logger.info('[COMPETITOR_STORAGE] 메인 문서 저장 완료: %s/%s', FIREBASE_COLLECTION, doc_id)

    # ── 서브컬렉션 products/ 저장 (batch write, 500건 제한 대응) ─────────
    products_col = doc_ref.collection('products')

    # 기존 서브컬렉션 문서 삭제 (재실행 시 중복 방지)
    _delete_subcollection(products_col)

    # competitors_table 저장
    _batch_save_products(client, products_col, competitors_table, prefix='competitor')

    # multi_keyword_products 저장
    _batch_save_products(client, products_col, multi_keyword_products, prefix='multi')

    total_products = len(competitors_table) + len(multi_keyword_products)
    logger.info('[COMPETITOR_STORAGE] 서브컬렉션 products/ 저장 완료: %d개 상품', total_products)

    return doc_id


def _delete_subcollection(col_ref, batch_size: int = 400):
    """서브컬렉션 문서 전체 삭제 (batch 단위 처리)"""
    try:
        db = col_ref._client
        docs = list(col_ref.limit(batch_size).stream())
        while docs:
            batch = db.batch()
            for doc in docs:
                batch.delete(doc.reference)
            batch.commit()
            docs = list(col_ref.limit(batch_size).stream())
    except Exception as e:
        logger.warning('[COMPETITOR_STORAGE] 서브컬렉션 삭제 중 오류 (무시): %s', e)


def _batch_save_products(client, col_ref, products: list, prefix: str, chunk: int = 400):
    """상품 리스트를 batch write로 저장 (Firestore 500건 제한 대응)"""
    if not products:
        return

    for start in range(0, len(products), chunk):
        batch = client.batch()
        for idx, product in enumerate(products[start:start + chunk], start=start):
            doc_id = f'{prefix}_{idx:04d}'
            ref = col_ref.document(doc_id)
            batch.set(ref, {
                'type': prefix,
                'idx': idx,
                **_to_serializable(product),
            })
        batch.commit()


# ── 조회 ───────────────────────────────────────────────────────────────────

def get_analysis(product_key: str, date: str) -> dict | None:
    """
    특정 날짜의 분석 결과 조회.

    Args:
        product_key: 제품 키 (예: '캡슐세제')
        date: 날짜 문자열 (예: '2026-04-26')

    Returns:
        분석 결과 dict (메인 문서만, products 서브컬렉션 제외). 없으면 None.
    """
    client = _get_db()
    if client is None:
        return None

    try:
        from competitor_analyzer.config import FIREBASE_COLLECTION
    except ImportError:
        FIREBASE_COLLECTION = 'competitor_analysis'

    doc_id = _make_doc_id(product_key, date)
    doc = client.collection(FIREBASE_COLLECTION).document(doc_id).get()
    return doc.to_dict() if doc.exists else None


def get_latest(product_key: str) -> dict | None:
    """
    특정 제품의 가장 최신 분석 결과 조회.

    Returns:
        가장 최근 analyzed_at 기준 메인 문서 dict. 없으면 None.
    """
    client = _get_db()
    if client is None:
        return None

    try:
        from competitor_analyzer.config import FIREBASE_COLLECTION
    except ImportError:
        FIREBASE_COLLECTION = 'competitor_analysis'

    safe_key = product_key.replace('/', '_').replace(' ', '_')

    # product 필드 필터링 후 analyzed_at 내림차순 1건
    try:
        docs = list(
            client.collection(FIREBASE_COLLECTION)
            .where('product', '==', product_key)
            .order_by('analyzed_at', direction=firestore.Query.DESCENDING)
            .limit(1)
            .stream()
        )
    except Exception:
        # 복합 인덱스 미생성 시 폴백 — Python에서 필터/정렬
        docs = list(
            client.collection(FIREBASE_COLLECTION)
            .stream()
        )
        docs = [d for d in docs if d.to_dict().get('product') == product_key]
        docs.sort(key=lambda d: d.to_dict().get('analyzed_at', ''), reverse=True)
        docs = docs[:1]

    if not docs:
        return None
    return docs[0].to_dict()


def get_latest_with_products(product_key: str) -> dict | None:
    """
    최신 분석 결과 + 서브컬렉션 products/ 데이터 포함 조회.

    Returns:
        메인 문서에 competitors_table, multi_keyword_products 필드 추가된 dict.
        없으면 None.
    """
    client = _get_db()
    if client is None:
        return None

    try:
        from competitor_analyzer.config import FIREBASE_COLLECTION
    except ImportError:
        FIREBASE_COLLECTION = 'competitor_analysis'

    # 최신 문서 ID 파악
    data = get_latest(product_key)
    if not data:
        return None

    analyzed_at = data.get('analyzed_at', '')
    date_str = analyzed_at[:10] if analyzed_at else ''
    doc_id = _make_doc_id(product_key, date_str)

    # 서브컬렉션 조회
    products_col = (
        client.collection(FIREBASE_COLLECTION)
        .document(doc_id)
        .collection('products')
    )
    product_docs = list(products_col.stream())
    product_list = [d.to_dict() for d in product_docs]

    competitors_table = sorted(
        [p for p in product_list if p.get('type') == 'competitor'],
        key=lambda x: x.get('idx', 9999),
    )
    multi_keyword_products = sorted(
        [p for p in product_list if p.get('type') == 'multi'],
        key=lambda x: x.get('idx', 9999),
    )

    data['competitors_table'] = competitors_table
    data['multi_keyword_products'] = multi_keyword_products
    return data


def list_dates(product_key: str) -> list[str]:
    """
    특정 제품의 분석 날짜 목록 반환 (최신순).

    Returns:
        ['2026-04-26', '2026-04-25', ...] 형태 날짜 문자열 리스트.
        Firebase 연결 불가 시 빈 리스트.
    """
    client = _get_db()
    if client is None:
        return []

    try:
        from competitor_analyzer.config import FIREBASE_COLLECTION
    except ImportError:
        FIREBASE_COLLECTION = 'competitor_analysis'

    try:
        docs = list(
            client.collection(FIREBASE_COLLECTION)
            .where('product', '==', product_key)
            .stream()
        )
    except Exception as e:
        logger.warning('[COMPETITOR_STORAGE] list_dates 오류: %s', e)
        return []

    dates = []
    for doc in docs:
        data = doc.to_dict()
        analyzed_at = data.get('analyzed_at', '')
        if analyzed_at:
            date_part = analyzed_at[:10]
            if date_part not in dates:
                dates.append(date_part)

    dates.sort(reverse=True)
    return dates
