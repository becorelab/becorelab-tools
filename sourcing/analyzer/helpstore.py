"""
헬프스토어(helpstore.shop) 연동 모듈
- Layer 1: requests 세션으로 서버 API 직접 호출 (키워드 데이터)
- Layer 2: Playwright CDP로 브라우저 자동화 (쿠팡 상품 데이터)
"""

import re
import json
import time
import logging
import requests
from typing import Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

HELPSTORE_BASE = 'https://helpstore.shop'
HELPSTORE_ID = 'becorelab'
HELPSTORE_PW = 'qlzhdjfoq2023!!'


# ─────────────────────────────────────────────
# 데이터 클래스
# ─────────────────────────────────────────────
@dataclass
class RelatedKeyword:
    """연관 키워드 데이터"""
    keyword: str = ''
    pc_search: int = 0          # PC 조회수
    mobile_search: int = 0      # 모바일 조회수
    total_search: int = 0       # 합계 조회수
    pc_click_rate: float = 0    # PC 클릭율
    mobile_click_rate: float = 0  # 모바일 클릭율
    product_count: int = 0      # 상품수
    competition: str = ''       # 경쟁도 (높음/보통/낮음)
    avg_depth: int = 0          # 평균 노출광고수
    is_brand: bool = False      # 브랜드 키워드 여부
    category: str = ''          # 카테고리


@dataclass
class CoupangProduct:
    """쿠팡 상품 데이터"""
    ranking: int = 0
    product_name: str = ''
    brand: str = ''
    manufacturer: str = ''
    price: int = 0
    sales_monthly: int = 0      # 월 판매량
    revenue_monthly: int = 0    # 월 매출
    review_count: int = 0
    click_count: int = 0
    conversion_rate: float = 0  # 전환율
    page_views: int = 0         # PV
    category: str = ''
    category_code: str = ''
    product_url: str = ''
    is_rocket: bool = False     # 로켓배송 여부
    is_ad: bool = False         # 광고 여부


@dataclass
class InflowKeyword:
    """유입 키워드 데이터"""
    keyword: str = ''
    search_volume: int = 0      # 조회수
    click_count: int = 0        # 클릭수
    click_rate: float = 0       # 클릭율
    impression_increase: float = 0  # 노출증가
    ad_weight: float = 0        # 광고비중


@dataclass
class ScanResult:
    """스캔 결과 통합"""
    keyword: str = ''
    related_keywords: list = field(default_factory=list)  # List[RelatedKeyword]
    products: list = field(default_factory=list)            # List[CoupangProduct]
    inflow_keywords: list = field(default_factory=list)     # List[InflowKeyword]
    main_category: str = ''
    main_category_code: str = ''
    total_search_volume: int = 0
    product_count: int = 0
    competition: str = ''


# ─────────────────────────────────────────────
# Layer 1: 서버 API (requests)
# ─────────────────────────────────────────────
class HelpstoreAPI:
    """헬프스토어 서버 API 클라이언트"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'X-ajax-call': 'true',
            'Accept': 'application/json, text/plain, */*',
            'Referer': f'{HELPSTORE_BASE}/keyword/keyword_analyze_coupang/',
        })
        self.logged_in = False
        self.token = None

    def login(self) -> bool:
        """헬프스토어 로그인"""
        try:
            # 로그인 페이지 GET (세션 쿠키 획득)
            self.session.get(f'{HELPSTORE_BASE}/login')

            # POST 로그인 (필드명: loginId, loginPw)
            res = self.session.post(f'{HELPSTORE_BASE}/login/', data={
                'loginId': HELPSTORE_ID,
                'loginPw': HELPSTORE_PW,
            }, allow_redirects=True)

            data = res.json()
            if data.get('success'):
                self.logged_in = True
                logger.info('헬프스토어 로그인 성공')
                return True

            logger.warning(f'헬프스토어 로그인 실패: {data}')
            return False

        except Exception as e:
            logger.error(f'로그인 에러: {e}')
            return False

    def get_token(self) -> Optional[str]:
        """키워드 검색용 토큰 발급"""
        try:
            res = self.session.get(f'{HELPSTORE_BASE}/token/keyword')
            data = res.json()
            if data.get('success'):
                self.token = data['data']['token']
                return self.token
        except Exception as e:
            logger.error(f'토큰 발급 에러: {e}')
        return None

    def get_related_keywords(self, keyword: str) -> list:
        """
        연관 키워드 조회
        /api/relKeyword/{keyword}
        → 검색량, 클릭수, 경쟁도, 상품수 등
        """
        if not self.logged_in:
            self.login()

        try:
            res = self.session.get(
                f'{HELPSTORE_BASE}/api/relKeyword/{keyword}',
                timeout=30
            )
            data = res.json()

            if not data.get('success', True):
                logger.warning(f'연관키워드 API 실패: {keyword}')
                return []

            api_data = data.get('data', {})
            items = api_data.get('list', [])

            keywords = []
            for item in items:
                kw = RelatedKeyword(
                    keyword=item.get('keyword', ''),
                    pc_search=item.get('p_click_count', 0),
                    mobile_search=item.get('m_click_count', 0),
                    total_search=item.get('sum_click_count', 0),
                    pc_click_rate=item.get('p_ave_ctr', 0),
                    mobile_click_rate=item.get('m_ave_ctr', 0),
                    product_count=item.get('shopping_count', 0),
                    competition=item.get('comp', ''),
                    avg_depth=item.get('avg_depth', 0),
                    is_brand=bool(item.get('is_brand_keyword', 0)),
                    category=item.get('category', '')
                )
                keywords.append(kw)

            logger.info(f'연관키워드 {len(keywords)}개 수집: {keyword}')
            return keywords

        except Exception as e:
            logger.error(f'연관키워드 에러: {e}')
            return []

    def get_keyword_trend(self, keyword: str, category_code: str = '') -> dict:
        """
        키워드 트렌드 조회
        /api/keywordTrend/{categoryCode}/{keyword}
        """
        if not self.logged_in:
            self.login()

        try:
            url = f'{HELPSTORE_BASE}/api/keywordTrend/{category_code}/{keyword}'
            res = self.session.get(url, timeout=30)
            return res.json()
        except Exception as e:
            logger.error(f'트렌드 에러: {e}')
            return {}

    def get_shopping_keywords(self, keyword: str) -> list:
        """
        쇼핑 자동완성 키워드
        /api/shoppingKeyword/{keyword}
        """
        if not self.logged_in:
            self.login()

        try:
            res = self.session.get(
                f'{HELPSTORE_BASE}/api/shoppingKeyword/{keyword}',
                timeout=15
            )
            data = res.json()
            return data.get('data', {}).get('list', [])
        except Exception as e:
            logger.error(f'자동완성 에러: {e}')
            return []

    def search_keyword(self, keyword: str) -> ScanResult:
        """
        키워드 종합 검색
        서버 API만으로 가능한 데이터 수집
        """
        if not self.logged_in:
            self.login()

        # 토큰 발급
        self.get_token()

        result = ScanResult(keyword=keyword)

        # 1. 연관 키워드
        related = self.get_related_keywords(keyword)
        result.related_keywords = related

        # 메인 키워드 정보 추출 (띄어쓰기 변형도 매칭)
        keyword_nospace = keyword.replace(' ', '')
        for kw in related:
            kw_nospace = kw.keyword.replace(' ', '')
            if kw.keyword == keyword or kw_nospace == keyword_nospace:
                result.total_search_volume = kw.total_search
                result.product_count = kw.product_count
                result.competition = kw.competition
                result.main_category = kw.category
                break

        # 2. 자동완성 키워드 (변형 후보)
        # shopping_kws = self.get_shopping_keywords(keyword)

        logger.info(f'키워드 검색 완료: {keyword} (연관 {len(related)}개)')
        return result


# ─────────────────────────────────────────────
# Layer 2: 브라우저 자동화 (Playwright CDP)
# ─────────────────────────────────────────────
class HelpstoreBrowser:
    """
    Playwright CDP로 헬프스토어 쿠팡 분석 페이지 자동화
    - Chrome --remote-debugging-port=9222 로 실행 필요
    - 헬프스토어 확장 프로그램 설치 필요 (쿠팡윙 데이터 수집)
    - 쿠팡윙 로그인 필요 (다른 탭에서 미리 로그인)

    페이지 구조:
    1. 검색: #keyword 입력 → #btnSearch 클릭
    2. 확장프로그램이 쿠팡윙 API 호출 → parseCoupangWingProductResult 처리
    3. 상품 리스트: .keyword_analyze_coupang .listProducts li
    4. WebSocket으로 topProductList (PV/CTR/광고비중) 수신 → #topProductDIV에 렌더
    5. 키워드 버튼 (.btnShowKeyword) → #keywordListPopup 팝업
    """

    COUPANG_PAGE = f'{HELPSTORE_BASE}/keyword/keyword_analyze_coupang/'

    def __init__(self, cdp_url: str = 'http://localhost:9222'):
        self.cdp_url = cdp_url
        self.browser = None
        self.context = None
        self.page = None
        self._pw = None

    async def connect(self):
        """CDP로 Chrome 연결"""
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.connect_over_cdp(self.cdp_url)
        self.context = self.browser.contexts[0]
        logger.info('Chrome CDP 연결 성공')

    async def login_if_needed(self):
        """로그인 상태 확인 및 로그인"""
        self.page = await self.context.new_page()
        await self.page.goto(self.COUPANG_PAGE)
        await self.page.wait_for_load_state('networkidle')

        # 로그인 상태 확인 (페이지 내 isLogin 변수)
        content = await self.page.content()
        if 'isLogin = false' in content or '/login' in self.page.url:
            logger.info('로그인 필요 — 자동 로그인 진행')
            await self.page.goto(f'{HELPSTORE_BASE}/login')
            await self.page.wait_for_load_state('networkidle')

            # 로그인 폼 작성
            # 필드: #loginId, #loginPw / 버튼: #btnLogin (type="button")
            await self.page.fill('#loginId', HELPSTORE_ID)
            await self.page.fill('#loginPw', HELPSTORE_PW)
            await self.page.click('#btnLogin')
            await self.page.wait_for_load_state('networkidle')
            # 로그인 후 추가 대기
            await self.page.wait_for_timeout(2000)

            await self.page.goto(self.COUPANG_PAGE)
            await self.page.wait_for_load_state('networkidle')
            logger.info('로그인 완료')

    async def search_coupang_products(self, keyword: str) -> list:
        """
        쿠팡 키워드 분석 페이지에서 상위 상품 데이터 수집

        Flow:
        1. #keyword 입력 → #btnSearch 클릭
        2. 확장 프로그램이 쿠팡윙 API 호출 (sendReceiveProcess)
        3. parseCoupangWingProductResult로 상위 40개 상품 파싱
        4. keyword_analyze_coupang 템플릿으로 .listProducts li 렌더링
        5. WebSocket으로 topProductList 수신 → #topProductDIV 렌더
        """
        if not self.page:
            await self.login_if_needed()

        # 쿠팡 분석 탭이 활성화되어 있는지 확인
        coupang_tab = self.page.locator('.btnKeyword[data-target="keyword_analyze_coupang"]')
        if await coupang_tab.count() > 0:
            await coupang_tab.click()
            await self.page.wait_for_timeout(500)

        # 키워드 입력
        search_input = self.page.locator('#keyword')
        await search_input.fill('')
        await search_input.type(keyword, delay=50)

        # 검색 버튼 클릭
        await self.page.locator('#btnSearch').click()

        # 오버레이(로딩) 표시 대기 → 사라짐 대기
        try:
            await self.page.wait_for_selector('.overlay:visible', timeout=5000)
        except Exception:
            pass  # 이미 사라졌을 수 있음

        # 결과 로딩 대기 (확장 프로그램 + WebSocket 완료)
        # .listProducts li 가 렌더링될 때까지 대기
        try:
            await self.page.wait_for_selector(
                '.keyword_analyze_coupang .listProducts li',
                timeout=45000
            )
            logger.info(f'상품 리스트 렌더링 감지: {keyword}')
        except Exception:
            logger.warning(f'상품 목록 로딩 타임아웃: {keyword}')
            return []

        # WebSocket topProductList 로딩 대기 (#topProductDIV 채워질 때까지)
        try:
            await self.page.wait_for_selector(
                '#topProductDIV .listProducts li',
                timeout=30000
            )
            logger.info(f'상위 상품 데이터(PV/CTR) 로딩 완료: {keyword}')
        except Exception:
            logger.info(f'상위 상품 추가 데이터 없음 (기본 데이터만 사용): {keyword}')

        # 오버레이 사라질 때까지 대기
        try:
            await self.page.wait_for_selector('.overlay', state='hidden', timeout=10000)
        except Exception:
            pass

        # 추가 안정화 대기
        await self.page.wait_for_timeout(2000)

        # 상품 데이터 파싱
        products = await self._parse_product_list()
        logger.info(f'쿠팡 상품 {len(products)}개 수집: {keyword}')
        return products

    async def _parse_product_list(self) -> list:
        """
        페이지에서 상품 목록 파싱

        HTML 구조 (keyword_analyze_coupang 템플릿):
        <li>
          <em>{ranking}</em>
          <span>{category}</span>
          <strong><a href="{link}">{productName}</a></strong>
          <dl class="type1">
            <dt>브랜드</dt><dd>{brandName}</dd>
            <dt>제조사</dt><dd>{manufacture}</dd>
            <dt>가격</dt><dd>{salePrice}원</dd>
          </dl>
          <dl class="type2">
            <dt>리뷰</dt><dd>{ratingCount}</dd>
            <dt>클릭수</dt><dd>{pvLast28Day}</dd>
            <dt>판매량</dt><dd>{salesLast28d}</dd>
            <dt>전환율</dt><dd>{cvr}%</dd>
            <dt>1개월 판매금액</dt><dd>{salesLast28dAmount}</dd>
          </dl>
          <a class="primaryMedium btnShowKeyword" data-category-id="{categoryCode}" data-id="{itemId}">키워드</a>
        </li>
        """
        products = []

        # 첫 번째 리스트 (쿠팡 랭킹순 — 상위 40개)
        items = await self.page.query_selector_all(
            '.keyword_analyze_coupang .listProducts li'
        )

        for i, item in enumerate(items):
            try:
                product = CoupangProduct(ranking=i + 1)

                # 상품명 + URL
                title_el = await item.query_selector('strong a')
                if title_el:
                    product.product_name = (await title_el.inner_text()).strip()
                    product.product_url = await title_el.get_attribute('href') or ''

                # 카테고리 (li > span — 첫번째 span)
                cat_el = await item.query_selector(':scope > span')
                if cat_el:
                    product.category = (await cat_el.inner_text()).strip()

                # 랭킹 (li > em)
                rank_el = await item.query_selector(':scope > em')
                if rank_el:
                    rank_text = (await rank_el.inner_text()).strip()
                    product.ranking = _parse_number(rank_text) or (i + 1)

                # dl.type1: 브랜드, 제조사, 가격
                # dl.type2: 리뷰, 클릭수, 판매량, 전환율, 판매금액
                dls = await item.query_selector_all('dl')
                for dl in dls:
                    dts = await dl.query_selector_all('dt')
                    dds = await dl.query_selector_all('dd')
                    for dt, dd in zip(dts, dds):
                        dt_text = (await dt.inner_text()).strip()
                        dd_text = (await dd.inner_text()).strip()

                        if dt_text == '브랜드':
                            product.brand = dd_text
                        elif dt_text == '제조사':
                            product.manufacturer = dd_text
                        elif dt_text == '가격':
                            product.price = _parse_number(dd_text)
                        elif dt_text == '리뷰':
                            product.review_count = _parse_number(dd_text)
                        elif dt_text == '클릭수':
                            product.click_count = _parse_number(dd_text)
                            product.page_views = product.click_count
                        elif dt_text == '판매량':
                            product.sales_monthly = _parse_number(dd_text)
                        elif dt_text == '전환율':
                            product.conversion_rate = _parse_float(dd_text)
                        elif '판매금액' in dt_text:
                            product.revenue_monthly = _parse_number(dd_text)

                # 카테고리 코드 (btnShowKeyword에서 추출)
                kw_btn = await item.query_selector('.btnShowKeyword')
                if kw_btn:
                    product.category_code = await kw_btn.get_attribute('data-category-id') or ''

                # 광고 여부 (em에 "광고" 텍스트 포함)
                rank_text = ''
                if rank_el:
                    rank_text = (await rank_el.inner_text()).strip()
                product.is_ad = '광고' in rank_text

                # 판매금액이 없으면 계산
                if product.revenue_monthly == 0 and product.sales_monthly > 0 and product.price > 0:
                    product.revenue_monthly = product.sales_monthly * product.price

                products.append(product)

            except Exception as e:
                logger.debug(f'상품 파싱 에러 #{i+1}: {e}')
                continue

        # #topProductDIV에 있는 추가 데이터(PV/CTR/광고비중) 보강
        await self._enrich_with_top_product_data(products)

        return products

    async def _enrich_with_top_product_data(self, products: list):
        """
        #topProductDIV의 상위 상품 데이터(노출증가/클릭수/클릭율/광고비중)를
        기존 products 리스트에 보강

        topProduct 템플릿 구조:
        <li>
          <em>{index+1}</em>
          <strong><a href="...products/{pid}?vendorItemId={vid}">{name} {option}</a></strong>
          <dl class="type1"><dt>가격</dt><dd>..원</dd><dt>리뷰</dt><dd>..(score)</dd></dl>
          <dl class="type2">
            <dt>노출증가</dt><dd>{impressionRate}%</dd>
            <dt>클릭수</dt><dd>{pv}({pvRate}%)</dd>
            <dt>클릭율</dt><dd>{ctr}%</dd>
            <dt>광고비중</dt><dd>{adImpressionWeight}%</dd>
          </dl>
        </li>
        """
        top_items = await self.page.query_selector_all('#topProductDIV .listProducts li')
        if not top_items:
            return

        # topProductList 데이터 수집 (pid 기준으로 매칭)
        top_data = {}
        for item in top_items:
            try:
                link_el = await item.query_selector('strong a')
                if not link_el:
                    continue
                href = await link_el.get_attribute('href') or ''
                name = (await link_el.inner_text()).strip()

                data = {'name': name, 'href': href}

                dls = await item.query_selector_all('dl.type2')
                for dl in dls:
                    dts = await dl.query_selector_all('dt')
                    dds = await dl.query_selector_all('dd')
                    for dt, dd in zip(dts, dds):
                        dt_text = (await dt.inner_text()).strip()
                        dd_text = (await dd.inner_text()).strip()
                        if '노출증가' in dt_text:
                            data['impression_rate'] = _parse_float(dd_text)
                        elif '클릭율' in dt_text:
                            data['ctr'] = _parse_float(dd_text)
                        elif '광고비중' in dt_text:
                            data['ad_weight'] = _parse_float(dd_text)

                # pid 추출
                import re as _re
                pid_match = _re.search(r'products/(\d+)', href)
                if pid_match:
                    top_data[pid_match.group(1)] = data

            except Exception:
                continue

        # 기존 products에 매칭하여 보강
        for product in products:
            if not product.product_url:
                continue
            import re as _re
            pid_match = _re.search(r'products/(\d+)', product.product_url)
            if pid_match and pid_match.group(1) in top_data:
                extra = top_data[pid_match.group(1)]
                # ad_weight는 CoupangProduct에 없으므로 is_ad 판단에 활용
                if extra.get('ad_weight', 0) > 50:
                    product.is_ad = True

    async def get_inflow_keywords(self, product_index: int = 0) -> list:
        """
        특정 상품의 유입 키워드 수집
        .btnShowKeyword 클릭 → #keywordListPopup 팝업 열림
        → .coupangTOPgrid table tbody tr 파싱

        팝업 컬럼 (keyword_coupang_top10 템플릿):
        키워드 | 조회수(qc) | 클릭수(pv) | 클릭율(ctr) | 노출증가(impressionRate) | 광고비중(adImpressionWeight)
        """
        inflow_keywords = []

        try:
            # 키워드 버튼 클릭 (.btnShowKeyword)
            kw_buttons = await self.page.query_selector_all(
                '.keyword_analyze_coupang .btnShowKeyword'
            )
            if product_index >= len(kw_buttons):
                return inflow_keywords

            await kw_buttons[product_index].click()

            # 팝업 표시 대기
            try:
                await self.page.wait_for_selector(
                    '#keywordListPopup[style*="block"], #keywordListPopup:visible',
                    timeout=10000
                )
            except Exception:
                # 대안: 팝업 내 테이블이 나타날 때까지 대기
                await self.page.wait_for_timeout(3000)

            # 테이블 데이터 로딩 대기
            await self.page.wait_for_timeout(2000)

            # 팝업 내 테이블 행 파싱
            rows = await self.page.query_selector_all(
                '#keywordListPopup .coupangTOPgrid table tbody tr'
            )

            for row in rows:
                tds = await row.query_selector_all('td')
                if len(tds) >= 3:
                    kw = InflowKeyword(
                        keyword=(await tds[0].inner_text()).strip(),
                        search_volume=_parse_number(await tds[1].inner_text()),
                        click_count=_parse_number(await tds[2].inner_text()),
                    )
                    if len(tds) >= 4:
                        kw.click_rate = _parse_float(await tds[3].inner_text())
                    if len(tds) >= 5:
                        kw.impression_increase = _parse_float(await tds[4].inner_text())
                    if len(tds) >= 6:
                        kw.ad_weight = _parse_float(await tds[5].inner_text())
                    if kw.keyword:  # 빈 키워드 제외
                        inflow_keywords.append(kw)

            logger.info(f'유입 키워드 {len(inflow_keywords)}개 수집 (상품 #{product_index + 1})')

            # 팝업 닫기
            close_btn = await self.page.query_selector(
                '#keywordListPopup .close, #keywordListPopup button.close'
            )
            if close_btn:
                await close_btn.click()
                await self.page.wait_for_timeout(500)

        except Exception as e:
            logger.error(f'유입 키워드 수집 에러 (상품 #{product_index + 1}): {e}')

        return inflow_keywords

    async def full_scan(self, keyword: str) -> ScanResult:
        """
        전체 스캔 (브라우저 자동화)
        1. 상품 목록 수집 (상위 40개, 쿠팡윙 데이터 포함)
        2. 상위 5개 상품의 유입 키워드 수집
        """
        result = ScanResult(keyword=keyword)

        # 상품 목록 수집
        products = await self.search_coupang_products(keyword)
        result.products = products

        if not products:
            return result

        # 상위 5개 상품의 유입 키워드 수집
        for i in range(min(5, len(products))):
            try:
                inflow_kws = await self.get_inflow_keywords(i)
                result.inflow_keywords.extend(inflow_kws)
                await self.page.wait_for_timeout(1000)  # 요청 간격
            except Exception as e:
                logger.debug(f'유입 키워드 수집 스킵 #{i}: {e}')

        # 중복 제거
        seen = set()
        unique_inflow = []
        for kw in result.inflow_keywords:
            if kw.keyword not in seen:
                seen.add(kw.keyword)
                unique_inflow.append(kw)
        result.inflow_keywords = unique_inflow

        # 카테고리 정보 추출
        if products:
            cats = {}
            for p in products:
                if p.category:
                    cats[p.category] = cats.get(p.category, 0) + 1
            if cats:
                result.main_category = max(cats, key=cats.get)
            if products[0].category_code:
                result.main_category_code = products[0].category_code

        return result

    async def close(self):
        """브라우저 연결 종료"""
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass
        if self._pw:
            await self._pw.stop()


# ─────────────────────────────────────────────
# 통합 스캔 함수
# ─────────────────────────────────────────────
def scan_keyword_api_only(keyword: str) -> ScanResult:
    """
    서버 API만으로 키워드 분석 (빠름, 확장 프로그램 불필요)
    → 연관 키워드, 검색량, 경쟁도, 상품수
    """
    api = HelpstoreAPI()
    return api.search_keyword(keyword)


async def scan_keyword_full(keyword: str, cdp_url: str = 'http://localhost:9222') -> ScanResult:
    """
    전체 스캔 (서버 API + 브라우저 자동화)
    → 연관 키워드 + 쿠팡 상위 상품 + 유입 키워드
    """
    # 1. 서버 API로 키워드 데이터 (네이버 연관키워드 + 검색량)
    api = HelpstoreAPI()
    result = api.search_keyword(keyword)

    # 2. 브라우저로 쿠팡 상품 데이터 (매출/판매량/클릭수/전환율)
    browser = HelpstoreBrowser(cdp_url)
    try:
        await browser.connect()
        await browser.login_if_needed()
        browser_result = await browser.full_scan(keyword)

        # 병합
        result.products = browser_result.products
        result.inflow_keywords = browser_result.inflow_keywords

        # 카테고리 보강
        if browser_result.main_category and not result.main_category:
            result.main_category = browser_result.main_category
            result.main_category_code = browser_result.main_category_code

    except Exception as e:
        logger.error(f'브라우저 스캔 에러: {e}')
    finally:
        await browser.close()

    return result


def scan_keyword_full_sync(keyword: str, cdp_url: str = 'http://localhost:9222') -> ScanResult:
    """
    전체 스캔의 동기 래퍼 (threading에서 호출용)
    asyncio 이벤트 루프를 새로 생성하여 실행
    """
    import asyncio

    # CDP 서버 확인, 없으면 Chrome 자동 시작
    ensure_chrome_debug()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(scan_keyword_full(keyword, cdp_url))
    finally:
        loop.close()


def ensure_chrome_debug(port: int = 9222):
    """
    Chrome이 디버그 모드(CDP)로 실행 중인지 확인.
    미실행 시 헬프스토어 확장 프로그램을 로드한 새 프로필로 자동 시작.
    """
    import socket, subprocess, os

    # 이미 열려있는지 확인
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = s.connect_ex(('127.0.0.1', port))
    s.close()
    if result == 0:
        logger.info(f'Chrome CDP 이미 실행중 (port {port})')
        return True

    logger.info(f'Chrome CDP 미실행 — 자동 시작합니다')

    # 헬프스토어 확장 프로그램 경로 찾기
    ext_base = os.path.join(
        os.environ.get('LOCALAPPDATA', ''),
        'Google', 'Chrome', 'User Data', 'Default', 'Extensions',
        'nfbjgieajobfohijlkaaplipbiofblef'  # 헬프스토어 확장 ID
    )

    ext_path = ''
    if os.path.isdir(ext_base):
        versions = [d for d in os.listdir(ext_base) if os.path.isdir(os.path.join(ext_base, d))]
        if versions:
            ext_path = os.path.join(ext_base, versions[0])

    # 디버그 전용 프로필 디렉토리
    debug_profile = os.path.join(os.environ.get('TEMP', '/tmp'), 'chrome-debug-helpstore')
    os.makedirs(debug_profile, exist_ok=True)

    chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    if not os.path.exists(chrome_path):
        chrome_path = r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'

    args = [
        chrome_path,
        f'--remote-debugging-port={port}',
        '--remote-allow-origins=*',
        f'--user-data-dir={debug_profile}',
    ]

    if ext_path:
        args.extend([
            f'--load-extension={ext_path}',
            f'--disable-extensions-except={ext_path}',
        ])
        logger.info(f'헬프스토어 확장 로드: {ext_path}')

    args.append(f'{HELPSTORE_BASE}/keyword/keyword_analyze_coupang/')

    subprocess.Popen(args)

    # Chrome 시작 대기
    import time
    for i in range(15):
        time.sleep(1)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = s.connect_ex(('127.0.0.1', port))
        s.close()
        if result == 0:
            logger.info(f'Chrome CDP 시작 완료 ({i+1}초)')
            return True

    logger.error('Chrome CDP 시작 실패 (15초 타임아웃)')
    raise ConnectionError(
        'Chrome CDP 연결 실패. Chrome을 닫고 다시 시도해주세요.'
    )


# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────
def _parse_number(text: str) -> int:
    """텍스트에서 숫자 추출 (쉼표, 한글 단위 처리)"""
    if not text:
        return 0
    text = text.strip().replace(',', '').replace(' ', '')

    # ~100, 100~ 처리
    text = text.replace('~', '')

    # 만 단위 처리
    match = re.search(r'([\d.]+)만', text)
    if match:
        return int(float(match.group(1)) * 10000)

    # 숫자만 추출
    match = re.search(r'[\d]+', text)
    if match:
        return int(match.group())
    return 0


def _parse_float(text: str) -> float:
    """텍스트에서 실수 추출"""
    if not text:
        return 0.0
    text = text.strip().replace(',', '').replace('%', '')
    match = re.search(r'[\d.]+', text)
    if match:
        return float(match.group())
    return 0.0


# ─────────────────────────────────────────────
# 테스트
# ─────────────────────────────────────────────
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print('\n[TEST] 헬프스토어 API 테스트\n')

    result = scan_keyword_api_only('건조기시트')
    print(f'키워드: {result.keyword}')
    print(f'총 검색량: {result.total_search_volume:,}')
    print(f'상품수: {result.product_count:,}')
    print(f'경쟁도: {result.competition}')
    print(f'연관키워드: {len(result.related_keywords)}개')

    if result.related_keywords:
        print('\n상위 5개 연관키워드:')
        for kw in sorted(result.related_keywords, key=lambda x: x.total_search, reverse=True)[:5]:
            print(f'  {kw.keyword}: 검색량 {kw.total_search:,} | 상품수 {kw.product_count:,} | 경쟁도 {kw.competition}')
