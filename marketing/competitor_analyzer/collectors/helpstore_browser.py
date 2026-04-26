"""
헬프스토어 확장 프로그램을 이용한 네이버 쇼핑 상품 데이터 수집기
- CDP 9222로 Chrome에 연결 (확장 프로그램 포함)
- 헬프스토어 "상위 노출상품 분석" 탭(네이버) 자동화
"""

import re
import os
import time
import socket
import logging
import subprocess
import argparse
import asyncio
from typing import Optional

from competitor_analyzer.config import HELPSTORE_ID, HELPSTORE_PW, HELPSTORE_BASE

logger = logging.getLogger(__name__)

NAVER_PAGE = f'{HELPSTORE_BASE}/keyword/keyword_analyze/'


def _parse_number(text: str) -> int:
    if not text:
        return 0
    text = text.strip().replace(',', '').replace(' ', '').replace('~', '')
    match = re.search(r'([\d.]+)만', text)
    if match:
        return int(float(match.group(1)) * 10000)
    match = re.search(r'\d+', text)
    if match:
        return int(match.group())
    return 0


def _parse_float(text: str) -> float:
    if not text:
        return 0.0
    text = text.strip().replace(',', '').replace('%', '')
    match = re.search(r'[\d.]+', text)
    if match:
        return float(match.group())
    return 0.0


class HelpstoreNaverBrowser:
    """헬프스토어 확장 프로그램을 이용한 네이버 쇼핑 상품 데이터 수집기"""

    NAVER_PAGE = NAVER_PAGE

    def __init__(self, cdp_url: str = 'http://localhost:9222'):
        self.cdp_url = cdp_url
        self.browser = None
        self.context = None
        self.page = None
        self._pw = None

    async def connect(self):
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.connect_over_cdp(self.cdp_url)
        self.context = self.browser.contexts[0]
        logger.info('Chrome CDP 연결 성공')

    async def login_if_needed(self):
        self.page = await self.context.new_page()
        await self.page.goto(self.NAVER_PAGE)
        await self.page.wait_for_load_state('networkidle')

        content = await self.page.content()
        if 'isLogin = false' in content or '/login' in self.page.url:
            logger.info('로그인 필요 — 자동 로그인 진행')
            await self.page.goto(f'{HELPSTORE_BASE}/login')
            await self.page.wait_for_load_state('networkidle')

            await self.page.fill('#loginId', HELPSTORE_ID)
            await self.page.fill('#loginPw', HELPSTORE_PW)
            await self.page.click('#btnLogin')
            await self.page.wait_for_load_state('networkidle')
            await self.page.wait_for_timeout(2000)

            await self.page.goto(self.NAVER_PAGE)
            await self.page.wait_for_load_state('networkidle')
            logger.info('로그인 완료')

    async def search_naver_products(self, keyword: str) -> list[dict]:
        """
        네이버 키워드 분석에서 상위 상품 데이터 수집

        Returns: list of dict with keys:
            rank, product_name, product_url, mall_name, brand,
            price, review_count, sales_monthly, revenue_monthly,
            click_count, conversion_rate, category, is_ad, mall_grade
        """
        if not self.page:
            await self.login_if_needed()

        naver_tab = self.page.locator('.btnKeyword[data-target="keyword_analyze"]')
        if await naver_tab.count() > 0:
            await naver_tab.click()
            await self.page.wait_for_timeout(500)

        search_input = self.page.locator('#keyword')
        await search_input.fill('')
        await search_input.type(keyword, delay=50)

        await self.page.locator('#btnSearch').click()

        try:
            await self.page.wait_for_selector('.overlay:visible', timeout=5000)
        except Exception:
            pass

        try:
            await self.page.wait_for_selector(
                '.keyword_analyze .listProducts li',
                timeout=45000
            )
            logger.info(f'상품 리스트 렌더링 감지: {keyword}')
        except Exception:
            logger.warning(f'상품 목록 로딩 타임아웃: {keyword}')
            return []

        try:
            await self.page.wait_for_selector('.overlay', state='hidden', timeout=10000)
        except Exception:
            pass

        await self.page.wait_for_timeout(2000)

        products = await self._parse_naver_product_list()
        logger.info(f'네이버 상품 {len(products)}개 수집: {keyword}')
        return products

    async def _parse_naver_product_list(self) -> list[dict]:
        """
        .keyword_analyze .listProducts li 파싱

        HTML 구조는 쿠팡과 유사하다고 가정하되, 네이버 전용 필드(몰명/몰등급)를 추가로 파싱.
        실제 구조는 dump_html()로 확인 후 이 메서드를 보정할 것.

        예상 구조:
        <li>
          <em>{rank}</em>                       <!-- 순위, "광고" 포함 시 광고 -->
          <span>{category}</span>
          <strong><a href="{url}">{name}</a></strong>
          <dl class="type1">
            <dt>쇼핑몰</dt><dd>{mall_name}</dd>
            <dt>브랜드</dt><dd>{brand}</dd>
            <dt>가격</dt><dd>{price}원</dd>
          </dl>
          <dl class="type2">
            <dt>리뷰</dt><dd>{review_count}</dd>
            <dt>클릭수</dt><dd>{click_count}</dd>
            <dt>판매량</dt><dd>{sales_monthly}</dd>
            <dt>전환율</dt><dd>{conversion_rate}%</dd>
            <dt>1개월 판매금액</dt><dd>{revenue_monthly}</dd>
          </dl>
        </li>
        """
        products = []

        items = await self.page.query_selector_all('.keyword_analyze .listProducts li')

        for i, item in enumerate(items):
            try:
                product: dict = {
                    'rank': i + 1,
                    'product_name': '',
                    'product_url': '',
                    'mall_name': '',
                    'brand': '',
                    'price': 0,
                    'review_count': 0,
                    'sales_monthly': 0,
                    'revenue_monthly': 0,
                    'click_count': 0,
                    'conversion_rate': 0.0,
                    'category': '',
                    'is_ad': False,
                    'mall_grade': '',
                }

                title_el = await item.query_selector('strong a')
                if title_el:
                    product['product_name'] = (await title_el.inner_text()).strip()
                    product['product_url'] = await title_el.get_attribute('href') or ''

                cat_el = await item.query_selector(':scope > span')
                if cat_el:
                    product['category'] = (await cat_el.inner_text()).strip()

                rank_el = await item.query_selector(':scope > em')
                rank_text = ''
                if rank_el:
                    rank_text = (await rank_el.inner_text()).strip()
                    parsed_rank = _parse_number(rank_text)
                    if parsed_rank:
                        product['rank'] = parsed_rank

                product['is_ad'] = '광고' in rank_text

                dls = await item.query_selector_all('dl')
                for dl in dls:
                    dts = await dl.query_selector_all('dt')
                    dds = await dl.query_selector_all('dd')
                    for dt, dd in zip(dts, dds):
                        dt_text = (await dt.inner_text()).strip()
                        dd_text = (await dd.inner_text()).strip()

                        if dt_text == '쇼핑몰' or dt_text == '몰명':
                            product['mall_name'] = dd_text
                        elif dt_text == '브랜드':
                            product['brand'] = dd_text
                        elif dt_text == '가격':
                            product['price'] = _parse_number(dd_text)
                        elif dt_text == '리뷰':
                            product['review_count'] = _parse_number(dd_text)
                        elif dt_text == '클릭수':
                            product['click_count'] = _parse_number(dd_text)
                        elif dt_text == '판매량':
                            product['sales_monthly'] = _parse_number(dd_text)
                        elif dt_text == '전환율':
                            product['conversion_rate'] = _parse_float(dd_text)
                        elif '판매금액' in dt_text:
                            product['revenue_monthly'] = _parse_number(dd_text)
                        elif dt_text == '몰등급':
                            product['mall_grade'] = dd_text

                if (
                    product['revenue_monthly'] == 0
                    and product['sales_monthly'] > 0
                    and product['price'] > 0
                ):
                    product['revenue_monthly'] = product['sales_monthly'] * product['price']

                products.append(product)

            except Exception as e:
                logger.debug(f'상품 파싱 에러 #{i+1}: {e}')
                continue

        return products

    async def dump_html(
        self,
        keyword: str,
        save_path: str = '/tmp/helpstore_naver_dump.html'
    ):
        """디버깅용: 네이버 탭 HTML을 파일로 저장해서 실제 구조 파악에 사용"""
        if not self.page:
            await self.login_if_needed()

        naver_tab = self.page.locator('.btnKeyword[data-target="keyword_analyze"]')
        if await naver_tab.count() > 0:
            await naver_tab.click()
            await self.page.wait_for_timeout(500)

        search_input = self.page.locator('#keyword')
        await search_input.fill('')
        await search_input.type(keyword, delay=50)
        await self.page.locator('#btnSearch').click()

        try:
            await self.page.wait_for_selector(
                '.keyword_analyze .listProducts li',
                timeout=45000
            )
        except Exception:
            logger.warning('로딩 타임아웃 — 현재 HTML 덤프')

        await self.page.wait_for_timeout(2000)

        html = await self.page.content()
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f'HTML 덤프 저장: {save_path} ({len(html):,} bytes)')
        print(f'[dump] 저장 완료: {save_path}')
        return save_path

    async def close(self):
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass
        if self._pw:
            await self._pw.stop()


def ensure_chrome_debug(port: int = 9222) -> bool:
    """
    Chrome이 CDP 디버그 모드로 실행 중인지 확인.
    미실행 시 헬프스토어 확장 포함해서 자동 시작 (macOS 전용).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    already_running = s.connect_ex(('127.0.0.1', port)) == 0
    s.close()

    if already_running:
        logger.info(f'Chrome CDP 이미 실행 중 (port {port})')
        return True

    logger.info('Chrome CDP 미실행 — 자동 시작합니다')

    chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    ext_path = os.path.expanduser(
        '~/Library/Application Support/Google/Chrome/Default/Extensions/'
        'nfbjgieajobfohijlkaaplipbiofblef/1.3.3_0'
    )
    debug_profile = '/tmp/chrome-debug-helpstore'
    os.makedirs(debug_profile, exist_ok=True)

    args = [
        chrome_path,
        f'--remote-debugging-port={port}',
        '--remote-allow-origins=*',
        f'--user-data-dir={debug_profile}',
    ]

    if os.path.isdir(ext_path):
        args += [
            f'--load-extension={ext_path}',
            f'--disable-extensions-except={ext_path}',
        ]
        logger.info(f'헬프스토어 확장 로드: {ext_path}')
    else:
        logger.warning(f'확장 경로 없음: {ext_path}')

    args.append(NAVER_PAGE)

    subprocess.Popen(args)

    for i in range(15):
        time.sleep(1)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ok = s.connect_ex(('127.0.0.1', port)) == 0
        s.close()
        if ok:
            logger.info(f'Chrome CDP 시작 완료 ({i+1}초)')
            return True

    logger.error('Chrome CDP 시작 실패 (15초 타임아웃)')
    raise ConnectionError('Chrome CDP 연결 실패. Chrome을 닫고 다시 시도해주세요.')


async def _run_search(keyword: str):
    ensure_chrome_debug()
    browser = HelpstoreNaverBrowser()
    try:
        await browser.connect()
        await browser.login_if_needed()
        products = await browser.search_naver_products(keyword)
        print(f'\n[네이버 상위 상품] 키워드: {keyword} — {len(products)}개\n')
        for p in products:
            ad_mark = '[광고] ' if p['is_ad'] else ''
            print(
                f"  {p['rank']:>2}위 {ad_mark}{p['product_name'][:30]}"
                f"  가격:{p['price']:,}원"
                f"  월판매:{p['sales_monthly']:,}"
                f"  월매출:{p['revenue_monthly']:,}원"
                f"  리뷰:{p['review_count']:,}"
            )
    finally:
        await browser.close()


async def _run_dump(keyword: str):
    ensure_chrome_debug()
    browser = HelpstoreNaverBrowser()
    try:
        await browser.connect()
        await browser.login_if_needed()
        path = await browser.dump_html(keyword)
        print(f'HTML 덤프 완료: {path}')
    finally:
        await browser.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    parser = argparse.ArgumentParser(description='헬프스토어 네이버 상품 수집기')
    parser.add_argument('--keyword', '-k', help='검색 키워드')
    parser.add_argument('--dump', '-d', help='HTML 덤프용 키워드')
    args = parser.parse_args()

    if args.dump:
        asyncio.run(_run_dump(args.dump))
    elif args.keyword:
        asyncio.run(_run_search(args.keyword))
    else:
        parser.print_help()
