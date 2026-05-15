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

                # 구매건수
                try:
                    purchase_count = int(d.get('purchaseCount') or 0)
                except (TypeError, ValueError):
                    purchase_count = 0

                results.append({
                    'rank': rank,
                    'product_name': _clean_text(d.get('productName') or ''),
                    'price': price,
                    'review_count': review_count,
                    'zzim_count': zzim_count,
                    'purchase_count': purchase_count,
                    'estimated_revenue': purchase_count * price if purchase_count and price else 0,
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

    def search_our_brand(self, product_keyword: str, brand_names: List[str] = None) -> List[Dict]:
        """우리 브랜드 상품만 검색하여 리뷰/구매 데이터 확보.

        "일비아 {keyword}" 등으로 검색 → 우리 몰 상품만 필터링.
        경쟁분석 시 우리 상품이 순위 밖이어도 정확한 데이터를 제공.
        """
        if brand_names is None:
            brand_names = ['일비아', 'ILBIA', 'ilbia', '비코어랩']

        search_queries = [f'일비아 {product_keyword}', f'iLBiA {product_keyword}']
        our_products: List[Dict] = []
        seen_urls = set()

        for query in search_queries:
            results = self.search(query, count=40)
            for item in results:
                mall = item.get('mall_name', '')
                if any(name.lower() in mall.lower() for name in brand_names):
                    url = item.get('url', '')
                    url_key = url.split('?')[0] if url else f"{item.get('product_name')}|{item.get('price')}"
                    if url_key not in seen_urls:
                        seen_urls.add(url_key)
                        our_products.append(item)

        our_products.sort(key=lambda x: (-x.get('review_count', 0), -x.get('purchase_count', 0)))
        logger.info('[브랜드 검색] "%s" → 우리 상품 %d개 발견', product_keyword, len(our_products))
        return our_products

    def search_multi(self, keywords: List[str], count_per_kw: int = 40) -> dict:
        """여러 키워드로 검색 → 중복 제거 → 통합 결과 반환.

        Returns:
            {
                'products': List[Dict],       # 중복 제거된 상품 목록
                'keyword_stats': List[Dict],   # 키워드별 수집 현황
                'total_unique': int,
                'total_before_dedup': int,
            }
        """
        all_raw: List[Dict] = []
        keyword_stats: List[Dict] = []

        for kw in keywords:
            results = self.search(kw, count=count_per_kw)
            keyword_stats.append({
                'keyword': kw,
                'count': len(results),
                'ad_count': sum(1 for r in results if r.get('is_ad')),
            })
            for r in results:
                r['source_keyword'] = kw
            all_raw.extend(results)
            logger.info('[멀티검색] %s: %d개 수집', kw, len(results))

        total_before = len(all_raw)

        # 중복 제거: URL 기준 → URL 없으면 (상품명+판매자+가격) 기준
        seen = set()
        unique: List[Dict] = []
        for item in all_raw:
            url = item.get('url', '')
            if url:
                key = url.split('?')[0]
            else:
                key = f"{item.get('product_name', '')}|{item.get('mall_name', '')}|{item.get('price', 0)}"

            if key not in seen:
                seen.add(key)
                unique.append(item)
            else:
                # 기존 상품에 키워드 정보 추가
                for existing in unique:
                    existing_url = existing.get('url', '')
                    existing_key = existing_url.split('?')[0] if existing_url else f"{existing.get('product_name', '')}|{existing.get('mall_name', '')}|{existing.get('price', 0)}"
                    if existing_key == key:
                        kws = existing.get('found_keywords', [existing.get('source_keyword', '')])
                        kws.append(item.get('source_keyword', ''))
                        existing['found_keywords'] = list(set(kws))
                        break

        # found_keywords 초기화 (단일 키워드만 나온 상품)
        for item in unique:
            if 'found_keywords' not in item:
                item['found_keywords'] = [item.get('source_keyword', '')]

        # 추정매출 기준 정렬 (매출 높은 순), 매출 없으면 rank 순
        unique.sort(key=lambda x: (-x.get('estimated_revenue', 0), x.get('rank', 999)))

        logger.info('[멀티검색] 총 %d개 → 중복제거 %d개 (키워드 %d개)', total_before, len(unique), len(keywords))

        return {
            'products': unique,
            'keyword_stats': keyword_stats,
            'total_unique': len(unique),
            'total_before_dedup': total_before,
        }
