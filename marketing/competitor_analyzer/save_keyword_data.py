"""
스마트스토어 마케팅 채널 키워드/유입 데이터 Firebase 저장 모듈

컬렉션 구조:
  smartstore_marketing/                              ← 메인 컬렉션
    keywords_{period_start}_{period_end}/            ← 키워드 트래픽 문서
      data_type, period_start, period_end,
      keyword_count, totals (전체 행)
      keywords/ (서브컬렉션)
        kw_0000, kw_0001, ...                        ← 개별 키워드 행
    referrals_{period_start}_{period_end}/           ← 유입 채널 문서
      data_type, period_start, period_end,
      referral_count, totals (전체 행)
      referrals/ (서브컬렉션)
        ref_0000, ref_0001, ...                      ← 개별 채널 행

사용법:
  # 파일에서 읽어 저장
  python save_keyword_data.py \\
      --keywords /tmp/keyword_data.txt \\
      --referrals /tmp/referral_data.txt \\
      --start 2026-02-01 --end 2026-04-25

  # 또는 임포트해서 사용
  from competitor_analyzer.save_keyword_data import (
      parse_keyword_tsv, parse_referral_tsv, save_keyword_traffic
  )
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Firebase 연결 (storage.py와 동일한 패턴) ─────────────────────────────────
_db = None

FIREBASE_COLLECTION = 'smartstore_marketing'


def _find_key_path() -> Optional[str]:
    """Firebase 서비스 계정 키 파일 자동 탐색 (storage.py와 동일 로직)"""
    # 1) 환경변수
    env_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2) 소싱앱 디렉토리 (../sourcing/analyzer/)
    sourcing_analyzer_dir = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', 'sourcing', 'analyzer',
    ))
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


def _get_db():
    """Firestore 클라이언트 반환. 초기화 실패 시 None."""
    global _db
    if _db is not None:
        return _db

    key_path = _find_key_path()
    if not key_path:
        logger.warning('[KEYWORD_STORAGE] Firebase 키 파일을 찾을 수 없습니다.')
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials
        from google.cloud import firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            logger.info('[KEYWORD_STORAGE] Firebase 앱 초기화 완료')
        else:
            logger.info('[KEYWORD_STORAGE] 기존 Firebase 앱 재사용')

        _db = firestore.Client.from_service_account_json(key_path)
        logger.info('[KEYWORD_STORAGE] Firestore 연결 완료: project=%s', _db.project)
        return _db

    except Exception as e:
        logger.error('[KEYWORD_STORAGE] Firestore 초기화 실패: %s', e)
        return None


# ── 숫자 파싱 헬퍼 ────────────────────────────────────────────────────────────

def _parse_num(val: str) -> Optional[float]:
    """
    쉼표, % 제거 후 숫자 변환.
    빈 값 / '-' / 변환 불가 시 None 반환.
    """
    v = val.strip().replace(',', '').replace('%', '')
    if v in ('', '-', 'N/A', 'n/a'):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_int(val: str) -> Optional[int]:
    n = _parse_num(val)
    return int(n) if n is not None else None


# ── 키워드 트래픽 TSV 파싱 ────────────────────────────────────────────────────

# 헤더 컬럼 (16개)
KEYWORD_COLS = [
    '채널속성', '채널그룹', '채널명', '키워드',
    '고객수', '유입수', '페이지수', '유입당페이지수',
    '결제수_라스트', '유입당결제율_라스트', '결제금액_라스트', '유입당결제금액_라스트',
    '결제수_14d', '유입당결제율_14d', '결제금액_14d', '유입당결제금액_14d',
]

_KEYWORD_HEADER_MARKER = '채널속성'  # 헤더 행 감지용


def parse_keyword_tsv(text: str) -> tuple[dict, list[dict]]:
    """
    스마트스토어 키워드 트래픽 탭 구분 텍스트 파싱.

    Args:
        text: 탭 구분 원본 텍스트 (헤더 행 반복 포함 가능)

    Returns:
        (totals, keywords)
        - totals: '전체' 요약 행 dict (첫 번째만)
        - keywords: 개별 키워드 행 dict 리스트 (전체 행 제외)
    """
    totals: Optional[dict] = None
    keywords: list[dict] = []
    seen_total = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split('\t')
        # 헤더 행 스킵
        if parts[0].strip() == _KEYWORD_HEADER_MARKER:
            continue

        if len(parts) < 4:
            continue

        채널속성 = parts[0].strip()
        채널그룹 = parts[1].strip() if len(parts) > 1 else ''
        채널명 = parts[2].strip() if len(parts) > 2 else ''
        키워드 = parts[3].strip() if len(parts) > 3 else ''

        # 숫자 컬럼 (인덱스 4~15)
        def _get(idx: int) -> str:
            return parts[idx].strip() if len(parts) > idx else ''

        row = {
            '채널속성': 채널속성,
            '채널그룹': 채널그룹,
            '채널명': 채널명,
            '키워드': 키워드,
            '고객수': _parse_int(_get(4)),
            '유입수': _parse_int(_get(5)),
            '페이지수': _parse_int(_get(6)),
            '유입당페이지수': _parse_num(_get(7)),
            '결제수_라스트': _parse_num(_get(8)),
            '유입당결제율_라스트': _parse_num(_get(9)),
            '결제금액_라스트': _parse_num(_get(10)),
            '유입당결제금액_라스트': _parse_num(_get(11)),
            '결제수_14d': _parse_num(_get(12)),
            '유입당결제율_14d': _parse_num(_get(13)),
            '결제금액_14d': _parse_num(_get(14)),
            '유입당결제금액_14d': _parse_num(_get(15)),
        }

        # '전체' 요약 행 처리 (첫 번째만 totals로)
        if 채널속성 == '전체' and 채널그룹 == '전체' and 채널명 == '전체' and 키워드 == '전체':
            if not seen_total:
                totals = row
                seen_total = True
            # 이후 '전체' 행은 모두 스킵
            continue

        keywords.append(row)

    if totals is None:
        totals = {}

    return totals, keywords


# ── 유입 채널 TSV 파싱 ────────────────────────────────────────────────────────

# 헤더 컬럼 (12개)
REFERRAL_COLS = [
    '채널속성', '채널상세',
    '고객수', '유입수',
    '결제수_라스트', '유입당결제율_라스트', '결제금액_라스트', '유입당결제금액_라스트',
    '결제수_14d', '유입당결제율_14d', '결제금액_14d', '유입당결제금액_14d',
]

_REFERRAL_HEADER_MARKER = '채널속성'


def parse_referral_tsv(text: str) -> tuple[dict, list[dict]]:
    """
    스마트스토어 유입 채널 탭 구분 텍스트 파싱.

    Returns:
        (totals, referrals)
        - totals: '전체' 요약 행 dict
        - referrals: 개별 채널 행 dict 리스트
    """
    totals: Optional[dict] = None
    referrals: list[dict] = []
    seen_total = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split('\t')
        # 헤더 행 스킵
        if parts[0].strip() == _REFERRAL_HEADER_MARKER and (
            len(parts) > 2 and '고객수' in parts[2]
        ):
            continue

        if len(parts) < 2:
            continue

        채널속성 = parts[0].strip()
        채널상세 = parts[1].strip() if len(parts) > 1 else ''

        def _get(idx: int) -> str:
            return parts[idx].strip() if len(parts) > idx else ''

        row = {
            '채널속성': 채널속성,
            '채널상세': 채널상세,
            '고객수': _parse_int(_get(2)),
            '유입수': _parse_int(_get(3)),
            '결제수_라스트': _parse_num(_get(4)),
            '유입당결제율_라스트': _parse_num(_get(5)),
            '결제금액_라스트': _parse_num(_get(6)),
            '유입당결제금액_라스트': _parse_num(_get(7)),
            '결제수_14d': _parse_num(_get(8)),
            '유입당결제율_14d': _parse_num(_get(9)),
            '결제금액_14d': _parse_num(_get(10)),
            '유입당결제금액_14d': _parse_num(_get(11)),
        }

        # '전체' 요약 행 처리
        if 채널속성 == '전체':
            if not seen_total:
                totals = row
                seen_total = True
            continue

        referrals.append(row)

    if totals is None:
        totals = {}

    return totals, referrals


# ── Firebase 저장 헬퍼 ────────────────────────────────────────────────────────

def _delete_subcollection(col_ref, batch_size: int = 400):
    """서브컬렉션 전체 삭제 (재실행 시 중복 방지)"""
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
        logger.warning('[KEYWORD_STORAGE] 서브컬렉션 삭제 오류 (무시): %s', e)


def _batch_save_rows(client, col_ref, rows: list[dict], prefix: str, chunk: int = 400):
    """행 리스트를 batch write로 저장"""
    if not rows:
        return
    for start in range(0, len(rows), chunk):
        batch = client.batch()
        for idx, row in enumerate(rows[start:start + chunk], start=start):
            doc_id = f'{prefix}_{idx:04d}'
            ref = col_ref.document(doc_id)
            batch.set(ref, {'idx': idx, **row})
        batch.commit()
        logger.info('[KEYWORD_STORAGE] batch 저장: %s %d~%d', prefix, start, start + len(rows[start:start + chunk]) - 1)


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


# ── 메인 저장 함수 ────────────────────────────────────────────────────────────

def save_keyword_traffic(
    keywords_data: list[dict],
    referrals_data: list[dict],
    period_start: str,
    period_end: str,
    keywords_totals: Optional[dict] = None,
    referrals_totals: Optional[dict] = None,
) -> dict[str, str]:
    """
    키워드 트래픽 & 유입 채널 데이터를 Firebase에 저장.

    Args:
        keywords_data: parse_keyword_tsv()에서 반환된 keywords 리스트
        referrals_data: parse_referral_tsv()에서 반환된 referrals 리스트
        period_start: 기간 시작 (예: '2026-02-01')
        period_end: 기간 종료 (예: '2026-04-25')
        keywords_totals: 키워드 전체 합계 행 dict (선택)
        referrals_totals: 유입채널 전체 합계 행 dict (선택)

    Returns:
        {'keywords_doc_id': ..., 'referrals_doc_id': ...}
    """
    client = _get_db()
    if client is None:
        logger.error('[KEYWORD_STORAGE] Firebase 연결 실패 — 저장 중단')
        return {}

    result = {}
    saved_at = _now_str()

    # ── 키워드 트래픽 저장 ────────────────────────────────────────────────────
    if keywords_data is not None:
        kw_doc_id = f'keywords_{period_start}_{period_end}'
        kw_main = {
            'data_type': 'keyword_traffic',
            'period_start': period_start,
            'period_end': period_end,
            'keyword_count': len(keywords_data),
            'totals': keywords_totals or {},
            'saved_at': saved_at,
        }
        kw_ref = client.collection(FIREBASE_COLLECTION).document(kw_doc_id)
        kw_ref.set(kw_main)
        logger.info('[KEYWORD_STORAGE] 키워드 메인 문서 저장: %s/%s (키워드 %d개)',
                    FIREBASE_COLLECTION, kw_doc_id, len(keywords_data))

        # 서브컬렉션 keywords/
        kw_col = kw_ref.collection('keywords')
        _delete_subcollection(kw_col)
        _batch_save_rows(client, kw_col, keywords_data, prefix='kw')
        logger.info('[KEYWORD_STORAGE] keywords/ 서브컬렉션 저장 완료: %d개', len(keywords_data))

        result['keywords_doc_id'] = kw_doc_id

    # ── 유입 채널 저장 ────────────────────────────────────────────────────────
    if referrals_data is not None:
        ref_doc_id = f'referrals_{period_start}_{period_end}'
        ref_main = {
            'data_type': 'referral_channel',
            'period_start': period_start,
            'period_end': period_end,
            'referral_count': len(referrals_data),
            'totals': referrals_totals or {},
            'saved_at': saved_at,
        }
        ref_ref = client.collection(FIREBASE_COLLECTION).document(ref_doc_id)
        ref_ref.set(ref_main)
        logger.info('[KEYWORD_STORAGE] 유입채널 메인 문서 저장: %s/%s (채널 %d개)',
                    FIREBASE_COLLECTION, ref_doc_id, len(referrals_data))

        # 서브컬렉션 referrals/
        ref_col = ref_ref.collection('referrals')
        _delete_subcollection(ref_col)
        _batch_save_rows(client, ref_col, referrals_data, prefix='ref')
        logger.info('[KEYWORD_STORAGE] referrals/ 서브컬렉션 저장 완료: %d개', len(referrals_data))

        result['referrals_doc_id'] = ref_doc_id

    return result


# ── CLI 진입점 ────────────────────────────────────────────────────────────────

def _cli():
    """
    커맨드라인 실행:
      python save_keyword_data.py \\
          --keywords /tmp/keyword_data.txt \\
          --referrals /tmp/referral_data.txt \\
          --start 2026-02-01 \\
          --end 2026-04-25

    파일 인수 생략 시 해당 데이터 저장 건너뜀.
    --keywords - 또는 --referrals - 를 주면 stdin에서 읽음.
    """
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
    )

    parser = argparse.ArgumentParser(description='스마트스토어 키워드/유입 데이터 Firebase 저장')
    parser.add_argument('--keywords', '-k', default=None,
                        help='키워드 트래픽 TSV 파일 경로 (- 이면 stdin)')
    parser.add_argument('--referrals', '-r', default=None,
                        help='유입 채널 TSV 파일 경로 (- 이면 stdin)')
    parser.add_argument('--start', '-s', default='2026-02-01', help='기간 시작 (YYYY-MM-DD)')
    parser.add_argument('--end', '-e', default='2026-04-25', help='기간 종료 (YYYY-MM-DD)')
    args = parser.parse_args()

    keywords_data = None
    keywords_totals = None
    referrals_data = None
    referrals_totals = None

    # 키워드 파일 읽기
    if args.keywords:
        if args.keywords == '-':
            text = sys.stdin.read()
        else:
            with open(args.keywords, 'r', encoding='utf-8') as f:
                text = f.read()
        keywords_totals, keywords_data = parse_keyword_tsv(text)
        print(f'[파싱 완료] 키워드 {len(keywords_data)}개, 전체합계: {keywords_totals}')

    # 유입채널 파일 읽기
    if args.referrals:
        if args.referrals == '-':
            if args.keywords == '-':
                print('[ERROR] --keywords와 --referrals 둘 다 stdin(-) 사용 불가', file=sys.stderr)
                sys.exit(1)
            text = sys.stdin.read()
        else:
            with open(args.referrals, 'r', encoding='utf-8') as f:
                text = f.read()
        referrals_totals, referrals_data = parse_referral_tsv(text)
        print(f'[파싱 완료] 유입채널 {len(referrals_data)}개, 전체합계: {referrals_totals}')

    if keywords_data is None and referrals_data is None:
        print('[ERROR] --keywords 또는 --referrals 중 하나 이상 지정해야 합니다.', file=sys.stderr)
        sys.exit(1)

    # Firebase 저장
    result = save_keyword_traffic(
        keywords_data=keywords_data or [],
        referrals_data=referrals_data or [],
        period_start=args.start,
        period_end=args.end,
        keywords_totals=keywords_totals,
        referrals_totals=referrals_totals,
    )

    print('\n[저장 완료]')
    for k, v in result.items():
        print(f'  {k}: {FIREBASE_COLLECTION}/{v}')


if __name__ == '__main__':
    _cli()
