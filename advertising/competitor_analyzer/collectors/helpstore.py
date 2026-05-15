"""헬프스토어 데이터 수집기 — 키워드 분석 API + 순위 추적 HTML 파싱"""

from __future__ import annotations

import logging
from typing import Optional, Union
import requests
from bs4 import BeautifulSoup

from competitor_analyzer.config import HELPSTORE_ID, HELPSTORE_PW, HELPSTORE_BASE

logger = logging.getLogger(__name__)


class HelpstoreCollector:
    """헬프스토어 키워드 분석 및 순위 추적 수집기"""

    def __init__(self):
        self.base = HELPSTORE_BASE
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': self.base,
        })
        self._login()

    def _login(self):
        try:
            resp = self.session.post(
                f'{self.base}/login/',
                data={'loginId': HELPSTORE_ID, 'loginPw': HELPSTORE_PW},
                timeout=15,
                allow_redirects=True,
            )
            resp.raise_for_status()
            logger.info('헬프스토어 로그인 완료 (status=%d)', resp.status_code)
        except Exception as e:
            logger.error('헬프스토어 로그인 실패: %s', e)

    def _get_json(self, path: str) -> Optional[Union[dict, list]]:
        try:
            resp = self.session.get(f'{self.base}{path}', timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error('API 호출 실패 %s: %s', path, e)
            return None

    def get_keyword_analysis(self, keyword: str) -> dict:
        """키워드 분석 종합 반환.

        반환 구조:
            keyword, total_search, product_count, competition,
            related_keywords (list), sections (dict), content_count (dict)
        """
        result = {
            'keyword': keyword,
            'total_search': 0,
            'product_count': 0,
            'competition': '',
            'related_keywords': [],
            'sections': {},
            'content_count': {},
        }

        # 연관 키워드 / 검색량 / 경쟁도 / 상품수
        # 응답: {data: {sumCount, shoppingCount, rate, keyword, list: [...]}, success, overQuater}
        rel = self._get_json(f'/api/relKeyword/{keyword}')
        if rel:
            inner = rel.get('data', rel) if isinstance(rel, dict) else {}
            result['total_search'] = inner.get('sumCount', inner.get('totalSearch', 0))
            result['product_count'] = inner.get('shoppingCount', inner.get('productCount', 0))
            # 연관 키워드 리스트에서 대표 경쟁도 추출
            kw_list = inner.get('list', inner.get('relKeywords', []))
            result['related_keywords'] = kw_list if isinstance(kw_list, list) else []
            if kw_list:
                # 첫번째 항목의 comp 필드로 경쟁도 표현
                first = kw_list[0] if isinstance(kw_list[0], dict) else {}
                result['competition'] = first.get('comp', inner.get('competition', ''))

        # 검색결과 섹션 / 쇼핑 노출 순위
        # 응답: {data: {mobilelist, pclist, mobileranking, pcranking, ...}, success, overQuater}
        section = self._get_json(f'/api/keywordSection/{keyword}')
        if section:
            result['sections'] = section.get('data', section) if isinstance(section, dict) else {}

        # 블로그/카페 콘텐츠 발행량
        # 응답: {data: {keywordCount: {cafeCount, blogCount, kinCount, webCount}}, success, overQuater}
        count = self._get_json(f'/api/keywordCount/{keyword}')
        if count:
            inner_cnt = count.get('data', count) if isinstance(count, dict) else {}
            result['content_count'] = inner_cnt.get('keywordCount', inner_cnt)

        return result

    def get_keyword_trend(self, cat_code: str, keyword: str) -> dict:
        """1년 트렌드 데이터 반환"""
        trend = self._get_json(f'/api/keywordTrend/{cat_code}/{keyword}')
        return trend if isinstance(trend, dict) else {}

    def get_ranking_data(self, product_id: int) -> dict:
        """순위 추적 페이지 HTML 파싱 후 반환"""
        result: dict = {'product_id': product_id, 'dates': [], 'keywords': []}

        try:
            resp = self.session.get(
                f'{self.base}/fast/ranking/{product_id}',
                timeout=20,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error('순위 페이지 요청 실패 (product_id=%d): %s', product_id, e)
            return result

        soup = BeautifulSoup(resp.text, 'lxml')

        # 날짜 헤더 파싱
        # th[scope=col] 중 첫번째는 "키워드" 헤더이므로 건너뜀
        header_ths = soup.select('th[scope="col"]')
        date_list: list = []
        for th in header_ths[1:]:  # 첫 th("키워드") 제외
            # a 태그([삭제] 링크) 제거 후 날짜 텍스트 추출
            th_copy = BeautifulSoup(str(th), 'lxml').find('th')
            if th_copy:
                for a in th_copy.find_all('a'):
                    a.decompose()
                date_text = th_copy.get_text(strip=True)
                if date_text:
                    date_list.append(date_text)
        result['dates'] = date_list

        # 키워드 행 파싱
        keyword_inputs = soup.select('input.keyword-input')
        for kw_input in keyword_inputs:
            kw_str = kw_input.get('data-keyword', '')
            kw_id = kw_input.get('data-keyword-id', '')
            if not kw_str:
                continue

            row = kw_input.find_parent('tr')
            if not row:
                continue

            # td 전체에서 첫번째(키워드 셀) 건너뛰고 순위 셀 파싱
            rank_cells = row.select('td')
            ranks: list = []
            for i, cell in enumerate(rank_cells[1:]):  # td[0] = 키워드 셀 건너뜀
                date_str = date_list[i] if i < len(date_list) else ''

                pflow = cell.select_one('p.flow')
                if not pflow:
                    ranks.append({
                        'date': date_str, 'rank': 0, 'page': 0,
                        'position': 0, 'change': 0, 'direction': None,
                    })
                    continue

                # 페이지·위치: small 태그 → "(1p 8)" — strong 내부에 있으므로 먼저 처리
                page_int, pos_int = 0, 0
                small_tag = pflow.select_one('strong small')
                if small_tag:
                    small_text = small_tag.get_text(strip=True).strip('()')
                    parts = small_text.replace('p', '').split()
                    if len(parts) >= 2:
                        try:
                            page_int = int(parts[0])
                            pos_int = int(parts[1])
                        except ValueError:
                            pass
                    small_tag.extract()  # small 제거 후 strong 텍스트만 남김

                # 순위: strong 내 small 제거 후 텍스트 → "8위"
                strong_tag = pflow.select_one('strong')
                rank_int = 0
                if strong_tag:
                    rank_text = strong_tag.get_text(strip=True).replace('위', '').strip()
                    try:
                        rank_int = int(rank_text)
                    except ValueError:
                        pass

                # 순위 변동: span.up / span.down
                change_int = 0
                direction = 'same'
                up_span = pflow.select_one('span.up')
                down_span = pflow.select_one('span.down')
                if up_span:
                    direction = 'up'
                    try:
                        change_int = int(up_span.get_text(strip=True))
                    except ValueError:
                        pass
                elif down_span:
                    direction = 'down'
                    try:
                        change_int = int(down_span.get_text(strip=True))
                    except ValueError:
                        pass

                ranks.append({
                    'date': date_str,
                    'rank': rank_int,
                    'page': page_int,
                    'position': pos_int,
                    'change': change_int,
                    'direction': direction,
                })

            result['keywords'].append({
                'keyword': kw_str,
                'keyword_id': kw_id,
                'ranks': ranks,
            })

        return result
