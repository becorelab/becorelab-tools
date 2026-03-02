# Logistics Project Memory

## 프로젝트 구조
- `발주대시보드.html` — 메인 대시보드 (탭: 재고현황/발주분석/발주관리/설정)
- `ezadmin_scraper.py` — Playwright 이지어드민 스크래핑
- `logistics_app.py` — Flask 서버 (port 8090, waitress)
- `config.py` — 이지어드민 로그인 정보 (.gitignore)
- `.gitignore` — config.py, __pycache__, *.pyc

## 이지어드민 (EzAdmin) 핵심 정보
- Base URL: `https://ka04.ezadmin.co.kr`
- 로그인 URL: `https://www.ezadmin.co.kr/index.html`
- Domain: bypl / ID: qlzhdjfoq / PW: qlzhdjfoq12!@
- 보안코드(CAPTCHA): 매 로그인마다 수동 입력 필요

## 스크래핑 대상 페이지
### I100 (재고현황)
- URL: `template35.htm?template=I100`
- `grid1_key` = 상품코드 (바코드/SKU)
- `grid1_stock` = 정상재고

### I500 (재고수불부) ← 판매량 데이터 소스
- URL: `template35.htm?template=I500`
- `grid1_product_id` = 상품코드
- `grid1_crdate` = 일자
- `grid1_stockout` = 출고 (로켓배송 직송)
- `grid1_trans` = 배송 (일반 배송)
- **판매량 = 출고 + 배송** (둘 다 합산해야 정확)
- 날짜 필드: `start_date`, `end_date` (ID 기반)
- 90일 기간 설정 시 약 1,200건 (12페이지 정도)

### DS00 (주문내역) — 사용 중단
- 같은 주문이 상태별(접수/확인/출고/배송) 중복 표시되어 판매량 부정확
- I500 재고수불부가 훨씬 정확한 데이터 제공

## UI 셀렉터
- 검색 버튼: `span.flip` (텍스트 "검색")
- jqGrid 셀: `td[aria-describedby="grid1_xxx"]` 정확 매칭 필수
- 다음 페이지: `.ui-pg-button [class*="seek-next"]`
- 페이지 사이즈: `.ui-pg-selbox` (마지막 option = 최대)

## PRODUCTS 배열 (대시보드)
S10357(건조기시트 코튼블루), S10358(베이비크림), S13565(바이올렛머스크),
10892(식기세척기세제 하트), 10460(일반), 13208(얼룩제거제350), 13209(100),
S13591(섬유탈취제100), S13590(400), 10964(수세미36매)

## 검증 완료 (2026-03-02)
- 재고 50품목 + 출고+배송 1,207건 (89일) 수집 성공
- 코튼블루(S10357) 206.9개/일 = 1위 (대표님 확인 완료)
- 식기세척기세제(10892) 140.7개/일 = 2위

## 중요 교훈
- DS00 `aria-describedby$="_product_id"` 셀렉터: `shop_product_id`와 `product_id` 두 컬럼 모두 매칭됨 → 반드시 정확 매칭 사용
- DS00 주문내역은 상태별 중복행 문제로 판매량 부정확 → I500 재고수불부 사용
- I500 날짜 필드 탐색: yyyy-mm-dd 패턴 값이 있는 input 필드 자동 감지

## 구현 완료 기능
- 소진 예상일: 90일(분석기간) 기준 평균 판매량 계산
- 주간 자동 수집: localStorage `ilbia_last_fetch` 체크, 7일 경과 시 자동 실행
- 그래프 색상: 상위 3개 민트블루, 나머지 스틸블루 (#4a657d)
- Flask 캐시 방지: Cache-Control no-cache 헤더 추가
- 페이지네이션: seek-next 버튼 + disabled 체크, 최대 50페이지

## Windows PC 셋업 (2026-03-02)
- config.py는 .gitignore라 새 PC마다 수동 생성 필요
- config.py 키 이름: `url`, `domain`, `id`, `pw` (스크래퍼 코드 기준)
- Windows에서 `pkill`이 안 먹음 → `taskkill //F //PID {pid}` 사용
- 포트 충돌 시 `netstat -ano | grep {port}`로 PID 확인 후 kill
- Python 패키지: flask, waitress, playwright, apscheduler, requests
- Playwright 브라우저: `playwright install chromium` 필수

## Git
- Repo: becorelab/becorelab-tools (private)
- Branch: main
- Push: `export PATH="$HOME/bin:$PATH" && git push origin main`
