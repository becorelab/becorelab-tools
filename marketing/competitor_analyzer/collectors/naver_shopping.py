"""네이버 쇼핑 검색 결과 수집기 — 모바일 검색 페이지 _INITIAL_STATE 파싱"""

from __future__ import annotations

import re
import time
import logging
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_SEARCH_URL = 'https://m.search.naver.com/search.naver'
_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
        'AppleWebKit/605.1.15 (KHTML, like Gecko) '
        'Version/17.0 Mobile/15E148 Safari/604.1'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9',
}


def _extract_initial_state(html: str) -> dict:
    """HTML에서 newshopping _INITIAL_STATE JSON 추출"""
    m = re.search(r'newshopping\[.shopping.\]\._INITIAL_STATE\s*=\s*', html)
    if not m:
        return {}
    raw = html[m.end():]

    # JS 전용 이스케이프 → JSON 호환으로 변환
    raw = raw.replace("\\'", "'")
    raw = re.sub(r':undefined', ':null', raw)
    raw = re.sub(r',undefined', ',null', raw)
    raw = re.sub(r':new Date\([^)]*\)', ':null', raw)

    # 중괄호 균형으로 JSON 경계 찾기
    depth, end = 0, 0
    for i, ch in enumerate(raw):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if not end:
        return {}

    import json
    try:
        return json.loads(raw[:end])
    except Exception as e:
        logger.error('_INITIAL_STATE JSON 파싱 실패: %s', e)
        return {}


def _clean_text(text: str) -> str:
    """<mark> 태그 등 HTML 제거"""
    return re.sub(r'<[^>]+>', '', text or '').strip()


class NaverShoppingCollector:
    """네이버 쇼핑 검색 결과 수집기"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    def search(self, keyword: str, count: int = 40) -> List[Dict]:
        """네이버 쇼핑 검색 상위 count개 상품 반환.

        반환 필드:
            rank, product_name, price, review_count, zzim_count,
            mall_name, mall_grade, category, url, is_ad
        """
        try:
            resp = self.session.get(
                _SEARCH_URL,
                params={'where': 'm_shop', 'query': keyword, 'display': count},
                timeout=20,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error('네이버 쇼핑 요청 실패 (keyword=%s): %s', keyword, e)
            return []

        state = _extract_initial_state(resp.text)
        if not state:
            logger.error('_INITIAL_STATE 추출 실패 (keyword=%s)', keyword)
            return []

        paged_slots = state.get('initProps', {}).get('pagedSlot', [])
        results: List[Dict] = []

        for page in paged_slots:
            for slot in page.get('slots', []):
                if len(results) >= count:
                    break
                d = slot.get('data', {})
                if not d:
                    continue

                rank = d.get('rank', 0)
                if not rank:
                    continue

                is_ad = d.get('sourceType') == 'AD'

                # 가격: 할인가 우선, 없으면 판매가
                price = d.get('discountedSalePrice') or d.get('salePrice') or 0
                try:
                    price = int(price)
                except (TypeError, ValueError):
                    price = 0

                # 리뷰수
                try:
                    review_count = int(d.get('totalReviewCount') or 0)
                except (TypeError, ValueError):
                    review_count = 0

                # 찜수 (keepCount)
                try:
                    zzim_count = int(d.get('keepCount') or 0)
                except (TypeError, ValueError):
                    zzim_count = 0

                # 몰 등급 (mallDescription: '공식', '파워', '빅파워', '프리미엄' 등)
                mall_grade = d.get('mallDescription') or ''

                # 카테고리 ID → 이름 (여기선 ID만, 필요시 카테고리 API 연동)
                category = str(d.get('leafCategoryId') or d.get('ssCatId') or '')

                # 상품 URL
                url_data = d.get('productUrl') or {}
                url = url_data.get('pcUrl') or url_data.get('mobileUrl') or ''

                results.append({
                    'rank': rank,
                    'product_name': _clean_text(d.get('productName') or ''),
                    'price': price,
                    'review_count': review_count,
                    'zzim_count': zzim_count,
                    'mall_name': d.get('mallName') or '',
                    'mall_grade': mall_grade,
                    'category': category,
                    'url': url,
                    'is_ad': is_ad,
                })

            if len(results) >= count:
                break

        # rank 기준 정렬
        results.sort(key=lambda x: x['rank'])

        time.sleep(0.5)
        return results[:count]
