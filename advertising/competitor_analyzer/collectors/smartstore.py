"""
스마트스토어 셀러센터 유입/전환 데이터 수집기

네이버 로그인 방식 선택 가이드
================================
네이버는 자동화 봇 감지가 매우 강력합니다.
직접 Playwright 로그인(ID/PW 입력) 시도 시 캡챠가 발생합니다.

권장 방식: 쿠키 재사용 (COOKIE_FILE 저장 후 재사용)

  1단계: python3 smartstore.py --save-cookies
         브라우저가 열리면 대표님이 수동 로그인
         세션 쿠키가 smartstore_cookies.json에 저장됨

  2단계: 이후 자동 실행 시 저장된 쿠키로 세션 복원
         매일 접속 중인 맥미니는 쿠키 유효기간이 길어 재로그인 불필요

대안 방식:
  - 스마트스토어 커머스 API (API Key 발급 후 사용)
  - Chrome 프로필 직접 경로 지정
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# config import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from competitor_analyzer.config import SMARTSTORE_ID, SMARTSTORE_PW

# ── 경로 설정 ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
COOKIE_FILE = BASE_DIR / 'smartstore_cookies.json'

# ── 로깅 설정 ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('smartstore_collector')

# ── 셀러센터 URL 상수 ──────────────────────────────────────────────────
SELLER_CENTER_URL = 'https://sell.smartstore.naver.com/'
NAVER_LOGIN_URL = 'https://nid.naver.com/nidlogin.login'
STATS_INFLOW_URL = 'https://sell.smartstore.naver.com/#/analytics/inflow'

# ── User-Agent ─────────────────────────────────────────────────────────
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)


# ======================================================================
# SmartstoreCollector
# ======================================================================

class SmartstoreCollector:
    """
    네이버 스마트스토어 셀러센터 유입/전환 데이터 수집기.

    사용 예시:
        collector = SmartstoreCollector()
        await collector.init()
        ok = await collector.login()
        if ok:
            data = await collector.get_keyword_traffic(days=14)
        await collector.close()
    """

    def __init__(self, headless: bool = False, slow_mo: int = 50):
        """
        Args:
            headless: True면 백그라운드 실행. 봇 감지 위험 있음. 기본 False.
            slow_mo: Playwright 동작 간 지연(ms). 봇 감지 우회용.
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._logged_in = False

    # ------------------------------------------------------------------
    # 초기화 / 정리
    # ------------------------------------------------------------------

    async def init(self):
        """Playwright 초기화. login() 전에 반드시 호출."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-infobars',
                '--window-size=1280,800',
            ]
        )

        # 봇 감지 우회: 저장된 쿠키가 있으면 로드
        if COOKIE_FILE.exists():
            logger.info(f'저장된 쿠키 발견: {COOKIE_FILE}')
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            self._context = await self._browser.new_context(
                user_agent=USER_AGENT,
                viewport={'width': 1280, 'height': 800},
                locale='ko-KR',
                timezone_id='Asia/Seoul',
            )
            await self._context.add_cookies(cookies)
        else:
            logger.info('저장된 쿠키 없음 — 신규 컨텍스트 생성')
            self._context = await self._browser.new_context(
                user_agent=USER_AGENT,
                viewport={'width': 1280, 'height': 800},
                locale='ko-KR',
                timezone_id='Asia/Seoul',
            )

        # 봇 감지 우회: navigator.webdriver 숨기기
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko'] });
            window.chrome = { runtime: {} };
        """)

        self._page = await self._context.new_page()

    async def close(self):
        """브라우저 및 Playwright 리소스 정리."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f'close() 중 오류: {e}')
        finally:
            self._logged_in = False
            logger.info('브라우저 종료 완료')

    # ------------------------------------------------------------------
    # 로그인
    # ------------------------------------------------------------------

    async def login(self) -> bool:
        """
        네이버 로그인 후 셀러센터 접근.

        전략:
          1) 저장된 쿠키로 셀러센터 바로 접근 (가장 빠름)
          2) 쿠키 만료/없음 → 자동 로그인 시도 (캡챠 발생 가능)
          3) 캡챠 감지 시 → 수동 로그인 대기 모드

        Returns:
            True: 로그인 성공, False: 실패
        """
        if not self._page:
            raise RuntimeError('init()을 먼저 호출하세요.')

        # ── 1단계: 저장된 쿠키로 셀러센터 접근 ──────────────────────
        if COOKIE_FILE.exists():
            logger.info('쿠키로 셀러센터 접근 시도...')
            try:
                await self._page.goto(SELLER_CENTER_URL, timeout=20000)
                await self._page.wait_for_timeout(3000)

                if await self._is_logged_in():
                    logger.info('쿠키 세션 유효 — 로그인 성공')
                    self._logged_in = True
                    return True
                else:
                    logger.info('쿠키 세션 만료 — 재로그인 필요')
            except Exception as e:
                logger.warning(f'쿠키 접근 실패: {e}')

        # ── 2단계: 자동 로그인 시도 ──────────────────────────────────
        logger.info('자동 로그인 시도 중...')
        result = await self._auto_login()
        if result:
            return True

        # ── 3단계: 수동 로그인 대기 (headless=False 일 때) ──────────
        if not self.headless:
            logger.warning('자동 로그인 실패 — 수동 로그인 대기 모드 (120초)')
            logger.warning('브라우저에서 직접 로그인 후 셀러센터까지 이동해 주세요.')
            return await self._wait_for_manual_login(timeout_sec=120)

        logger.error('로그인 실패 (headless 모드에서는 수동 로그인 불가)')
        return False

    async def _auto_login(self) -> bool:
        """Playwright로 자동 로그인 시도. 캡챠 발생 시 False 반환."""
        try:
            await self._page.goto(NAVER_LOGIN_URL, timeout=15000)
            await self._page.wait_for_timeout(2000)

            # ID 입력
            await self._page.click('#id')
            await self._page.wait_for_timeout(300)
            await self._page.type('#id', SMARTSTORE_ID, delay=80)
            await self._page.wait_for_timeout(300)

            # PW 입력
            await self._page.click('#pw')
            await self._page.wait_for_timeout(300)
            await self._page.type('#pw', SMARTSTORE_PW, delay=80)
            await self._page.wait_for_timeout(500)

            # 로그인 버튼
            await self._page.click('.btn_login')
            await self._page.wait_for_timeout(5000)

            current_url = self._page.url

            # 캡챠 감지
            if await self._is_captcha():
                logger.warning('캡챠 감지 — 자동 로그인 불가')
                await self._page.screenshot(path='/tmp/smartstore_captcha.png')
                logger.info('캡챠 스크린샷: /tmp/smartstore_captcha.png')
                return False

            # 2차 인증 감지
            if 'auth' in current_url and 'nid.naver.com' in current_url:
                logger.warning('2차 인증 페이지 감지 — 수동 처리 필요')
                return False

            # 셀러센터 이동
            if 'nidlogin' not in current_url:
                await self._page.goto(SELLER_CENTER_URL, timeout=20000)
                await self._page.wait_for_timeout(3000)
                if await self._is_logged_in():
                    await self._save_cookies()
                    logger.info('자동 로그인 성공 + 쿠키 저장')
                    self._logged_in = True
                    return True

        except Exception as e:
            logger.error(f'자동 로그인 오류: {e}')

        return False

    async def _wait_for_manual_login(self, timeout_sec: int = 120) -> bool:
        """
        headless=False 모드에서 수동 로그인 대기.
        대표님이 브라우저에서 직접 로그인하면 세션 감지 후 쿠키 저장.
        """
        logger.info(f'수동 로그인 대기 중... ({timeout_sec}초)')
        await self._page.goto(NAVER_LOGIN_URL, timeout=15000)

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            await asyncio.sleep(2)
            if await self._is_logged_in():
                await self._save_cookies()
                logger.info('수동 로그인 감지 + 쿠키 저장 완료')
                self._logged_in = True
                return True

        logger.error(f'{timeout_sec}초 내 로그인 미완료')
        return False

    async def _is_logged_in(self) -> bool:
        """현재 페이지가 셀러센터 대시보드인지 확인."""
        url = self._page.url
        # 셀러센터 대시보드 URL 패턴
        if 'sell.smartstore.naver.com' in url and 'nidlogin' not in url:
            # 로그인 유지 여부: 셀러 메뉴 존재 확인
            try:
                el = await self._page.query_selector('.snb-nav, .gnb-nav, [class*="NavBar"], [class*="sidebar"]')
                return el is not None
            except Exception:
                pass
            # URL만으로도 판단
            return '#/home/dashboard' in url or '#/analytics' in url
        return False

    async def _is_captcha(self) -> bool:
        """캡챠 발생 여부 확인."""
        try:
            # 이미지 캡챠
            captcha_el = await self._page.query_selector('.captcha_wrap, #captchaimg, [class*=captcha]')
            if captcha_el:
                return True
            # 텍스트 기반 감지
            body = await self._page.inner_text('body')
            return '자동입력 방지문자' in body or 'captcha' in body.lower()
        except Exception:
            return False

    async def _save_cookies(self):
        """현재 세션 쿠키를 파일에 저장."""
        cookies = await self._context.cookies()
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info(f'쿠키 저장 완료: {COOKIE_FILE} ({len(cookies)}개)')

    # ------------------------------------------------------------------
    # 데이터 수집
    # ------------------------------------------------------------------

    async def get_keyword_traffic(self, days: int = 14) -> list[dict]:
        """
        키워드별 유입/전환 데이터 수집.

        Args:
            days: 조회 기간 (14 또는 30)

        Returns:
            list of dict:
            [
              {
                'keyword': str,       # 검색 키워드
                'channel': str,       # 유입 채널
                'visits': int,        # 방문수
                'orders': int,        # 결제건수
                'revenue': int,       # 결제금액
                'conversion_rate': float,  # 전환율 (%)
                'collected_at': str,  # 수집 시각 ISO
              }, ...
            ]
        """
        if not self._logged_in:
            logger.error('로그인 필요. login()을 먼저 호출하세요.')
            return []

        logger.info(f'키워드 유입 데이터 수집 시작 (최근 {days}일)')

        try:
            # 유입분석 페이지 이동
            await self._navigate_to_inflow_page()

            # 기간 설정
            await self._set_date_range(days)

            # 키워드별 탭 전환
            keyword_data = await self._extract_keyword_table()

            logger.info(f'키워드 데이터 수집 완료: {len(keyword_data)}건')
            return keyword_data

        except Exception as e:
            logger.error(f'키워드 유입 수집 오류: {e}')
            await self._page.screenshot(path='/tmp/smartstore_error.png')
            logger.info('오류 스크린샷: /tmp/smartstore_error.png')
            return []

    async def get_channel_summary(self, days: int = 14) -> list[dict]:
        """
        채널별 유입/전환 요약 수집.

        Args:
            days: 조회 기간 (14 또는 30)

        Returns:
            list of dict:
            [
              {
                'channel': str,       # 채널명 (오가닉쇼핑, 검색광고, ADBoost 등)
                'visits': int,
                'orders': int,
                'revenue': int,
                'conversion_rate': float,
                'collected_at': str,
              }, ...
            ]
        """
        if not self._logged_in:
            logger.error('로그인 필요. login()을 먼저 호출하세요.')
            return []

        logger.info(f'채널 요약 데이터 수집 시작 (최근 {days}일)')

        try:
            await self._navigate_to_inflow_page()
            await self._set_date_range(days)
            channel_data = await self._extract_channel_table()
            logger.info(f'채널 데이터 수집 완료: {len(channel_data)}건')
            return channel_data

        except Exception as e:
            logger.error(f'채널 요약 수집 오류: {e}')
            await self._page.screenshot(path='/tmp/smartstore_channel_error.png')
            return []

    # ------------------------------------------------------------------
    # 내부: 페이지 탐색 / 데이터 추출
    # ------------------------------------------------------------------

    async def _navigate_to_inflow_page(self):
        """셀러센터 유입분석 페이지로 이동."""
        logger.info('유입분석 페이지 이동 중...')

        # 직접 URL 이동 시도
        await self._page.goto(STATS_INFLOW_URL, timeout=20000)
        await self._page.wait_for_timeout(4000)

        current_url = self._page.url
        logger.info(f'현재 URL: {current_url}')

        # SPA 라우팅 확인 (Angular/Vue 기반 셀러센터)
        # analytics 탭이 제대로 로드됐는지 확인
        if 'analytics' not in current_url and 'inflow' not in current_url:
            # 사이드바에서 통계 > 유입분석 메뉴 클릭 시도
            logger.info('사이드바에서 유입분석 메뉴 탐색...')
            await self._click_inflow_menu()

        # 페이지 로드 대기
        await self._page.wait_for_timeout(3000)

    async def _click_inflow_menu(self):
        """셀러센터 사이드바에서 유입분석 메뉴를 찾아 클릭."""
        # 셀러센터는 SPA(Angular)로 구성됨
        # 메뉴 셀렉터 후보들 (실제 DOM 확인 필요)
        menu_candidates = [
            # 텍스트 기반 탐색
            'text=유입분석',
            'text=통계',
            '[data-menu="analytics"]',
            'a[href*="analytics"]',
            'a[href*="inflow"]',
            '.snb-nav li:has-text("유입분석")',
            '.side-nav-item:has-text("유입")',
        ]

        for selector in menu_candidates:
            try:
                el = await self._page.query_selector(selector)
                if el:
                    logger.info(f'메뉴 발견: {selector}')
                    await el.click()
                    await self._page.wait_for_timeout(2000)
                    return
            except Exception:
                continue

        # 메뉴를 못 찾으면 현재 DOM 구조 로깅
        logger.warning('유입분석 메뉴를 찾지 못함. 현재 페이지 DOM 분석...')
        await self._log_page_structure()

    async def _set_date_range(self, days: int):
        """유입분석 기간을 days일로 설정."""
        logger.info(f'기간 설정: 최근 {days}일')

        # 기간 선택 버튼 셀렉터 후보들
        if days == 7:
            period_text = '7일'
        elif days == 14:
            period_text = '14일'
        elif days == 30:
            period_text = '30일'
        else:
            period_text = str(days)

        period_candidates = [
            f'button:has-text("{period_text}")',
            f'[data-period="{days}"]',
            f'.period-btn:has-text("{period_text}")',
            f'label:has-text("{period_text}")',
        ]

        for selector in period_candidates:
            try:
                el = await self._page.query_selector(selector)
                if el:
                    await el.click()
                    await self._page.wait_for_timeout(2000)
                    logger.info(f'기간 설정 완료: {period_text}')
                    return
            except Exception:
                continue

        logger.warning(f'기간 버튼 "{period_text}"을 찾지 못함 — 기본 기간 사용')

    async def _extract_keyword_table(self) -> list[dict]:
        """키워드별 유입 테이블에서 데이터 추출."""
        collected_at = datetime.now().isoformat()
        results = []

        # 키워드 탭 클릭 시도
        keyword_tab_candidates = [
            'text=검색 키워드',
            'text=키워드',
            '[data-tab="keyword"]',
            '.tab-item:has-text("키워드")',
        ]
        for selector in keyword_tab_candidates:
            try:
                el = await self._page.query_selector(selector)
                if el:
                    await el.click()
                    await self._page.wait_for_timeout(2000)
                    break
            except Exception:
                continue

        # 테이블 행 추출 시도
        try:
            # 테이블 셀렉터 (실제 DOM 확인 후 수정 필요)
            table_rows = await self._page.query_selector_all(
                'table tbody tr, .data-table tbody tr, [class*="table"] [class*="row"]'
            )

            if not table_rows:
                logger.warning('테이블 행을 찾지 못함 — 페이지 구조 로깅')
                await self._log_page_structure()
                # 페이지 HTML 저장 (디버깅용)
                html = await self._page.content()
                with open('/tmp/smartstore_inflow_page.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                logger.info('페이지 HTML 저장: /tmp/smartstore_inflow_page.html')
                return []

            for row in table_rows:
                try:
                    cells = await row.query_selector_all('td, th')
                    if len(cells) < 3:
                        continue

                    cell_texts = []
                    for cell in cells:
                        txt = await cell.inner_text()
                        cell_texts.append(txt.strip())

                    # 컬럼 파싱 (실제 셀러센터 컬럼 순서에 맞게 조정 필요)
                    # 예상 컬럼: 키워드 | 채널 | 방문수 | 결제건수 | 결제금액 | 전환율
                    if len(cell_texts) >= 4:
                        row_data = self._parse_traffic_row(cell_texts, include_keyword=True)
                        if row_data:
                            row_data['collected_at'] = collected_at
                            results.append(row_data)

                except Exception as e:
                    logger.debug(f'행 파싱 오류: {e}')
                    continue

        except Exception as e:
            logger.error(f'테이블 추출 오류: {e}')

        return results

    async def _extract_channel_table(self) -> list[dict]:
        """채널별 요약 테이블에서 데이터 추출."""
        collected_at = datetime.now().isoformat()
        results = []

        # 채널 탭 클릭 시도
        channel_tab_candidates = [
            'text=채널',
            'text=유입채널',
            '[data-tab="channel"]',
            '.tab-item:has-text("채널")',
        ]
        for selector in channel_tab_candidates:
            try:
                el = await self._page.query_selector(selector)
                if el:
                    await el.click()
                    await self._page.wait_for_timeout(2000)
                    break
            except Exception:
                continue

        # 테이블 추출
        try:
            table_rows = await self._page.query_selector_all(
                'table tbody tr, .data-table tbody tr, [class*="table"] [class*="row"]'
            )

            for row in table_rows:
                try:
                    cells = await row.query_selector_all('td')
                    if len(cells) < 3:
                        continue

                    cell_texts = []
                    for cell in cells:
                        txt = await cell.inner_text()
                        cell_texts.append(txt.strip())

                    row_data = self._parse_traffic_row(cell_texts, include_keyword=False)
                    if row_data:
                        row_data['collected_at'] = collected_at
                        results.append(row_data)

                except Exception as e:
                    logger.debug(f'행 파싱 오류: {e}')
                    continue

        except Exception as e:
            logger.error(f'채널 테이블 추출 오류: {e}')

        return results

    def _parse_traffic_row(self, cells: list[str], include_keyword: bool = False) -> Optional[dict]:
        """
        테이블 행 텍스트를 파싱해 딕셔너리로 변환.

        실제 셀러센터 컬럼 순서:
          - 키워드 포함: [키워드, 채널, 방문수, 결제건수, 결제금액, 전환율]
          - 채널 전용:   [채널, 방문수, 결제건수, 결제금액, 전환율]
        """
        try:
            if include_keyword:
                if len(cells) < 5:
                    return None
                return {
                    'keyword': cells[0],
                    'channel': cells[1] if len(cells) > 5 else '',
                    'visits': self._parse_int(cells[2] if len(cells) > 5 else cells[1]),
                    'orders': self._parse_int(cells[3] if len(cells) > 5 else cells[2]),
                    'revenue': self._parse_int(cells[4] if len(cells) > 5 else cells[3]),
                    'conversion_rate': self._parse_float(cells[5] if len(cells) > 5 else cells[4]),
                }
            else:
                if len(cells) < 4:
                    return None
                return {
                    'channel': cells[0],
                    'visits': self._parse_int(cells[1]),
                    'orders': self._parse_int(cells[2]),
                    'revenue': self._parse_int(cells[3]),
                    'conversion_rate': self._parse_float(cells[4]) if len(cells) > 4 else 0.0,
                }
        except (IndexError, ValueError) as e:
            logger.debug(f'행 파싱 실패: {cells} — {e}')
            return None

    @staticmethod
    def _parse_int(text: str) -> int:
        """숫자 문자열 파싱 (쉼표, 원 기호 제거)."""
        try:
            return int(text.replace(',', '').replace('원', '').replace('%', '').strip() or '0')
        except ValueError:
            return 0

    @staticmethod
    def _parse_float(text: str) -> float:
        """퍼센트 문자열 파싱."""
        try:
            return float(text.replace('%', '').replace(',', '').strip() or '0')
        except ValueError:
            return 0.0

    # ------------------------------------------------------------------
    # 디버깅 유틸
    # ------------------------------------------------------------------

    async def _log_page_structure(self):
        """현재 페이지의 주요 DOM 구조를 로깅 (디버깅용)."""
        try:
            url = self._page.url
            title = await self._page.title()
            logger.info(f'[DOM 분석] URL: {url} | 타이틀: {title}')

            # 네비게이션 메뉴 탐색
            nav_items = await self._page.query_selector_all('nav a, .nav-item, .menu-item, li a')
            menu_texts = []
            for item in nav_items[:20]:
                txt = (await item.inner_text()).strip()
                href = await item.get_attribute('href') or ''
                if txt:
                    menu_texts.append(f'{txt}({href})')
            if menu_texts:
                logger.info(f'[DOM 분석] 메뉴 항목: {" | ".join(menu_texts)}')

            # 테이블 탐색
            tables = await self._page.query_selector_all('table')
            logger.info(f'[DOM 분석] 테이블 수: {len(tables)}')

            # 스크린샷
            await self._page.screenshot(path='/tmp/smartstore_page_debug.png')
            logger.info('[DOM 분석] 스크린샷: /tmp/smartstore_page_debug.png')

        except Exception as e:
            logger.warning(f'DOM 분석 오류: {e}')


# ======================================================================
# 쿠키 저장 전용 함수 (최초 1회 수동 로그인용)
# ======================================================================

async def save_cookies_interactive():
    """
    headless=False 모드로 브라우저 열고 대표님이 수동 로그인 후 쿠키 저장.

    실행:
        python3 -m competitor_analyzer.collectors.smartstore --save-cookies
    또는:
        python3 /path/to/smartstore.py --save-cookies
    """
    print('\n' + '='*60)
    print(' 스마트스토어 쿠키 저장 모드')
    print('='*60)
    print('브라우저가 열리면 네이버 로그인 후 셀러센터까지 이동해 주세요.')
    print('셀러센터 대시보드가 뜨면 자동으로 쿠키가 저장됩니다.')
    print('='*60 + '\n')

    collector = SmartstoreCollector(headless=False, slow_mo=100)
    await collector.init()

    try:
        await collector._page.goto(NAVER_LOGIN_URL, timeout=15000)
        print('>> 브라우저에서 직접 로그인 후 셀러센터로 이동해 주세요.')
        print('>> 최대 3분 대기...\n')

        deadline = time.time() + 180
        while time.time() < deadline:
            await asyncio.sleep(3)
            url = collector._page.url
            if 'sell.smartstore.naver.com' in url and 'nidlogin' not in url:
                # 셀러센터 진입 확인 (대시보드 또는 어떤 페이지든)
                await collector._save_cookies()
                print(f'\n쿠키 저장 완료: {COOKIE_FILE}')
                print('이제 자동 수집이 가능합니다.\n')
                await asyncio.sleep(2)
                break
        else:
            print('타임아웃: 로그인이 완료되지 않았습니다.')

    finally:
        await collector.close()


# ======================================================================
# CLI 진입점
# ======================================================================

async def _main():
    """테스트 실행."""
    import argparse
    parser = argparse.ArgumentParser(description='스마트스토어 유입/전환 데이터 수집기')
    parser.add_argument('--save-cookies', action='store_true', help='수동 로그인 후 쿠키 저장')
    parser.add_argument('--days', type=int, default=14, help='조회 기간 (기본: 14일)')
    parser.add_argument('--headless', action='store_true', help='헤드리스 모드 실행')
    parser.add_argument('--channel', action='store_true', help='채널별 요약만 수집')
    args = parser.parse_args()

    if args.save_cookies:
        await save_cookies_interactive()
        return

    # 일반 수집 모드
    collector = SmartstoreCollector(headless=args.headless)
    await collector.init()

    try:
        ok = await collector.login()
        if not ok:
            print('\n로그인 실패.')
            print('해결 방법:')
            print('  1) python3 smartstore.py --save-cookies  # 수동 로그인 후 쿠키 저장')
            print('  2) .env 파일의 SMARTSTORE_ID / SMARTSTORE_PW 확인')
            return

        print(f'\n로그인 성공! 데이터 수집 시작 (최근 {args.days}일)\n')

        if args.channel:
            data = await collector.get_channel_summary(days=args.days)
            print('\n=== 채널별 유입/전환 요약 ===')
        else:
            data = await collector.get_keyword_traffic(days=args.days)
            print('\n=== 키워드별 유입/전환 데이터 ===')

        if data:
            for row in data[:20]:  # 최대 20건 출력
                print(row)
            print(f'\n총 {len(data)}건 수집됨')

            # JSON 저장
            output_path = Path('/tmp/smartstore_traffic_data.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f'데이터 저장: {output_path}')
        else:
            print('수집된 데이터 없음.')
            print('셀러센터 유입분석 페이지 구조 탐색 중... (스크린샷 확인)')
            print('  /tmp/smartstore_page_debug.png')
            print('  /tmp/smartstore_inflow_page.html')

    finally:
        await collector.close()


if __name__ == '__main__':
    asyncio.run(_main())
