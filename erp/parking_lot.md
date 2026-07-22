# ERP 작업 파킹랏

## 2026-07-22 저녁 ✅ 매출 ₩0 완전 해결 — 다운로드 방식으로 전환 성공 (7/15~7/21 복구완료)
**결론: ACG DS00 화면엔 금액컬럼이 아예 없음(B안 사망 확정). 금액은 '다운로드 양식'에만 → 다운로드 자동화로 최종 해결.**
- **reCAPTCHA "매번 뜬다"는 전 하치 오판**: `save_file_go()`가 `function.htm`에 `template=recaptcha&action=check_log_web&check_template=DS00` POST → 서버가 `{"error":0|1}` 반환. **error==1일 때만** 이미지캡차(`download_check_invisible.htm`). 정상 다운로드 빈도면 **error=0 = 캡차 없음**(실측 확인). JS: `if(obj.error==1){openwin25(캡차)}else{popup_download_info()→ins_download_worklist()}`.
- **다운로드 흐름(자동화)**: DS00 검색(주문일) → `download_field=DS00_file_13`('판매데이터 확인용', 금액포함) → `ins_download_worklist(work_template=DS00, work_func=save_file_DS00, par=$("#download_form").serialize())` → `main35_func.php?action=get_download_worklist` 폴링(status==2) → `file_name`(https://ga90.../*.xls, **HTML테이블 형식**) → `page.context.request.get(url)` 다운로드 → `pandas.read_html` 파싱.
- **파일 컬럼(헤더 row0)**: 주문번호·상품코드·공급처·상품명·판매처·주문수량·상품수량·판매가·상품별판매금액·**상품별정산금액**·결제금액·**정산금액**·**주문일**... **이미 주문단위 dedup됨**(화면 4~7배 중복 없음). 쿠팡은 정산금액=0(별도정산, 기존과 동일).
- **캡차 회피 설계**: 다운로드 1회당 error 판정 → 날짜별 개별(N회) 대신 **범위 1회 다운로드 후 주문일 그룹핑**. 일일롤링·배치 모두 다운로드 1회.
- **코드(`logistics/ezadmin_scraper.py`)**: 신설 `scrape_sales_range(page,from,to)`·`_queue_ds00_download`·`_parse_ds00_file`·`_summarize_day`·`CaptchaRequired`. `scrape_sales`·`batch_rescrape_sales`·`fetch_all_data` 전부 다운로드 방식으로 교체. 구 화면스크랩 = `_scrape_sales_screen_DEPRECATED`로 보존. `DS00_DOWNLOAD_FIELD="DS00_file_13"`(양식 바뀌면 이 상수만 갱신).
- **복구 실행완료**: 물류서버 재시작(새코드) → `POST 8082/api/batch-rescrape {7/15~7/21}`(7일 다운로드1회, Firestore저장 7일) → `POST 8085/api/sales/resync {7/15~7/21}`(313행 반영). **ERP 일간보고 7/21 = 정산₩2,252,676/139건 정상, 7월누적 ₩33,868,317 복구.**
- **검증값(주문일별 정산)**: 7/15=3,276,413 / 7/16=2,685,356 / 7/17=2,612,496 / 7/18=3,687,481 / 7/19=5,819,207(카카오기획전) / 7/20=3,273,083 / 7/21=2,252,676. 합 1,110건 23,606,712원.
- ⏳ **남은 것**: ①내일 아침 예약수집 크론(`run_scrape scheduled=True`, sales_days=7=1회다운로드)이 새코드로 정상 도는지 로그 확인. ②볼트 매출보고서 7/15~7/21 재생성(데이터는 이제 흐름, 매출하치 정기산출물). ③reCAPTCHA error=1 발생 시 폴백(현재 CaptchaRequired 발생+로그만 — 필요시 Vision/반자동 추가).

## 2026-07-22 🟡 매출 ₩0 복구 — 원인2개 확정, ①고침 ②대표님 컬럼세팅 대기 (↑위에서 해결됨)
어제(7/21) "이지어드민 이전이 원인"에서 더 파고들어 **진짜 원인 2개 실측 확정**:
- **원인① 서버주소 하드코딩 (✅ 고침, 커밋)**: 코드 `BASE=ka04`(bypl 서버) → ACG 실제 작업서버는 **ga69**. ka04로 DS00 열면 "mysqli 연결 불가"→0건. `ezadmin_login`이 **로그인 후 `location.origin`으로 BASE 자동갱신**하도록 수정(`logistics/ezadmin_scraper.py:59~`). 이제 화면 조회 **67행 정상**(대표님 "ACG 연동됨" 실증).
- **원인② DS00 화면에 금액 컬럼 없음 (⏳ 대표님 출근해 세팅 예정)**: ACG 계정 확장주문검색2 그리드 컬럼 = 주문/배송정보 위주(shop_id·order_id·name·qty·trans_no·o_options·수령자…). **판매가(amount)·정산금액(supply_price)·상품코드(product_id)·현재고 없음.** bypl엔 있었음(옛 코드가 읽던 컬럼: product_name_options·p_options·amount·supply_price·collect_date·product_id·stock).
- **A안(다운로드 양식) 폐기 — reCAPTCHA**: "판매데이터 확인용"(download_field=DS00_file_13) 양식 존재하나, `#download`(다운로드F6)→`download_check_invisible.htm` 팝업 `exe()` 실행 시 **이미지 reCAPTCHA("자전거 선택")** 뜸 → 자동크론 불가. 화면 조회는 캡차 없음(로그인만).
- ▶ **B안 확정(대표님 7/22 출근해 직접 세팅)**: ACG 이지어드민 항목설정(DS01)에서 **안 쓰는 조회항목(예:12번)에 판매가·정산금액·상품코드·옵션·현재고 컬럼 추가**(ACG 기존 조회항목1 등은 손대지 말 것). ⚠️ACG 공유계정이라 ACG 양해 후. 세팅되면 다음 하치가 `scrape_sales`에서 ①해당 조회항목 선택(select_field) ②컬럼 aria매핑을 ACG 헤더에 맞게 갱신 → `/api/sales/resync`로 7/15~ 재동기화. 볼트·ERP 동시 복구.
- 참고 aria(ACG 현재 화면): grid1_shop_id/order_id/name/order_products_qty/qty/trans_no/product_name/o_options/order_name/recv_name… (금액 붙으면 amount/supply_price 계열 추가될 것 — 세팅 후 재확인 필수)

## 2026-07-21 🔴 매출 ₩0 원인 확정 — 이지어드민 ACG 이전(7/15) DS00 스크랩 중단
**뿌리 하나:** 볼트 매출보고서·ERP sales가 **같은 우물**을 씀 → `물류서버:8082/api/sales-daily-orders`(=이지어드민 DS00 스크랩). `app.py:797` `_sync_sales_day`가 이 API 호출.
- **직접 검증(curl):** `/api/sales-daily-orders?date=` → 7/13 정상(by_option에 스스·G마켓·카페24 채널별 정산), **7/20 완전 빈 응답**. 7/15 ACG 이전 시점부터 끊김.
- **왜 ERP엔 매출이 남아보였나:** `_sync_sales_day` 멱등 보호장치("이지어드민이 이번에 준 채널만 삭제후 재삽입", 6/29 그로스 유실사고 대응)가 **빈 응답이면 아무것도 안 지우고 안 넣음** → 옛 데이터 화석처럼 잔존. 그로스(매일 100만대)는 별도 윙 크론(`coupang_gross_daily`)이 채워 살아있음. **볼트는 ₩0로 정직, ERP는 잔존+그로스라 덜 티남 — 실제론 둘 다 이지어드민 채널 7/15부터 누락.**
- **대표님 확인(7/21):** "실제 판매처는 ACG에 연동되어 있어. 그로스·로켓은 별개." → **채널 연동은 됨.** 즉 문제는 연동X, **`ezadmin_scraper.scrape_sales`의 DS00 조회조건이 ACG 화면과 안 맞음**(어제 "ACG 0건"과 동일 뿌리).
- ▶ **다음 세션 액션(대표님 확인 불필요, 하치가 고침):** ACG 이지어드민 로그인 → DS00(확장주문검색2) 화면 실제로 열어 그리드 구조/파라미터 확인 → `scrape_sales` 조회조건(날짜필드·검색버튼·컬럼매핑) ACG에 맞게 수정 → 7/15~ 재동기화(`/api/sales/resync`). 고치면 볼트·ERP 동시 복구.

## 2026-06-10 대표님 ERP 점검 — 진행상황
### ✅ 완료
- 쿠팡 대시보드 시트 키 교체 (삭제된 옛 시트 → 새 1bmN5H7lB...)
- 5월 그로스 일별 백필 (31일)
- 그로스 5·6월 → ERP sales 반영 (매출 화면에 그로스 표시, sync_to_sales). 매일 크론에도 추가됨.
- 발주 status 정정: 입고전 completed 3건 → confirmed. 입고일: 얼룩제거제 6/16, 섬유탈취제 6/30.
- 매출 채널 합산뷰: "합산 보기" 토글을 기간 전체 채널별 합산(날짜무시)으로 변경.
- **발주 데이터 SSOT 이관 (2026-07-02)**: Firestore `logistics/purchases`가 3/18 이후 죽어있던 원인 = 발주 관리가 구 발주대시보드→ERP로 이사(에러 아님). 물류서버 발주분석·재고보고서가 ERP SQLite를 읽기전용 직접 조회하도록 수정(`logistics_app.py` `_erp_pending_purchases`, 품명 텍스트 매칭 — ERP product_id는 절반 NULL+오연결 있어 불신). 재고보고서 "발주중" 태그 부활 검증 완료. ⚠️ERP 발주라인 product_id 정합성 정리는 별도 과제.

### ⬜ 남은 작업
- [x] **🔴 매출 발주일→주문일 버그 (2026-06-29 진단+검증+코드수정 완료, 6월 재동기화 실행 대기)** — DS00(이지어드민) 매출을 `collect_date`(발주일) 기준으로 집계해 **토요일 주문이 평일로 밀리고 누락**됨. 진짜 주문일 = `order_id` 앞 8자리. **정답지(대표님): 6월 스스 ~4,500만 / 카페24 2천만 초중반 / 11번가 ~180만.**
  - ⚠️ **이전 하치 함정 검증으로 적발 (그대로 옮기면 안 됨)**: ①인수인계 "고유행제거 supply=스스 4,370만(-3%)" 숫자는 맞지만, 같이 남긴 `_tmp_find_filter.py`의 **F모드 코드는 `(채널,주문번호)` 첫행만** 취해 멀티상품 주문(한 주문에 상품 여러개)을 통째로 버림 → 실제 돌리면 **스스 3,008만(-33%)**. 인수인계 숫자 ≠ 스크립트 코드. ②`status`(취소/환불) 컬럼은 DS00 그리드에서 **전부 빈값**으로 들어옴 → "취소/환불 제외"는 실제 미작동(송장유무로만 퉁쳤고 송장없음 91행뿐).
  - ✅ **검증 확정 정답 집계법 (SSOT)**: **완전동일행 dedup(주문번호+상품+옵션+금액+수량 → 그리드 4~7배 반복만 제거, 상품행은 보존) + 정산금액(supply_price) 합 + 주문일(order_id 8자리)**. _tmp 6월 17,190행 → 4,647행, 스스 4,370만(-3%)/카페24 2,391만(+4%) 정답지 일치.
  - ✅ **코드 수정 완료** (`ezadmin_scraper.py` `scrape_sales`): order_id 수집 추가 / 완전동일행 dedup 추가 / date를 order_id 8자리 주문일로 교정. 문법 OK.
  - ✅ **6월 재수집·재동기화 완료 (2026-06-29)**: batch-rescrape 6/1~28 → resync. 스스 4,384만(정답지 -2.6%)/카페24 2,411만 일치. 6월 총합 143,952,931. 상세 = 메모리 `project_erp_sales_fix`.
  - ✅ **11번가 -40% = 버그 아님** (대표님 확인 2026-06-29): 광고비가 정산금액에서 차감되는 11번가 정산 특성. 재점검 불필요. (G마켓 과소=스타배송, 무시)
  - ⚠️ 진짜 정확값은 정산하치 6월 정산서(`settlement_monthly`, 5/30 설계) — 위 이지어드민 수정은 "정산 전 임시 추정" 정확도 개선.
  - ✅ 임시파일(`logistics/_tmp_june_orders.json`, `_tmp_find_filter.py`) 정리 완료 (2026-07-02).
- [x] **재고 수불부 기간별 출고량 검색 (2026-06-29 완료)** — 재고탭에 기간 프리셋(이번달/저번달/최근1주/지정기간) + "기간 출고량" 컬럼. 데이터 = 재고수불부 I500(출고+배송) 최근 ~90일.
- [x] **재고 수불부 모달에 일별 재고+입고 표기 (2026-07-03 완료)** — 상품 클릭 수불부 모달(`stock_sales_outbound` daily)에 ①일별 추정재고 ②입고일 📦 표기. 재고=현재고(stock.qty_on_hand) 역산(마감재고 = 다음날마감 - 다음날입고 + 다음날출고). 입고=completed/partial PO의 delivery_date 기준 qty_received. ⚠️역산이 음수 되는 시점부터 재고 null('-')로 끊음 — 과거로 갈수록 재고sync(adjust) 조정·누락입고로 부정확(최근 ~1개월만 신뢰, "추정치" 명시). 근본해결책은 stock_transactions에 inbound/outbound tx를 실제로 쌓는 것(현재 adjust만 426건). receiving_records 테이블은 존재하나 0건(미사용).
  - 신설: logistics `GET /api/outbound-history?preset=|start=|end=` (orders=latest.orders 우선·logistics_daily 폴백, code별 합산) → ERP 프록시 `GET /api/stock/outbound` → 재고탭 UI(`static/js/app.js` loadStock/renderStockTable). 매칭키 = ezadmin_code. 검증완료(이번달 25,425/저번달 18,296).
- [x] **로켓배송(1P) 매출 크론 — 완료** — `rocket_daily.py`(launchd 8시, 입고상세→ERP sales 멱등 upsert, 40일 롤링) 가동 중. 2026-07-02: 세션 6일 만료 방치로 6/27~7/1 구멍 → 재로그인+백필 복구(36일 5,693만). **재발방지 = `supplyhub_keepalive.py` 신설**(launchd 3시간 주기, KEYCLOAK idle 만료 전 세션 연장 + 쿠키 재백업 + 만료 시 알림 1회). idle 가설 판정 = 7/3 아침 크론 생존 여부.
- [ ] **발주서 수정 → 일정/상태 자동반영** — 발주서에서 납품예정일·상태 수정 시 일정관리 캘린더 자동 갱신.
- [ ] **발주 품목라인 누락** — 로드에프 PO-20260529-1(2,114만)·-2(1,057만) 품목 라인 없음. ⚠️원본 발주서/이메일 확인 필요(임의생성 금지).
- [ ] **채널명 중복 정제** — "비코어랩 카페24 일비아" 등 미세하게 다른 채널명이 합산 시 중복 표시. 채널명 정규화 필요.
- [ ] 5월 그로스 vi-detail 과거조회 한도 점검 (5월도 31일 다 잡힘 확인됨, OK).

- [ ] **erp.db 일일백업 누락** — Claude-Setup/backups 일일백업에 erp.db가 안 들어감 (2026-07-02 발주서 오수정 복구 때 발견 — 세션 스냅샷 덕에 복원했지만 백업 있었으면 더 안전). daily_backup에 erp.db 추가 필요.
- [ ] **발주서 수정 이력/실행취소 부재** — 2026-07-02 대표님이 복사 대신 원본 수정하는 사고. audit log 테이블 or 수정 전 스냅샷 저장 검토.

## 이전 (보류)
- [ ] 노션 기능 ERP에 병합 (대표님 아이디어, 나중에)
- [ ] 네이버웍스 SMTP 인증 실패 — info@becorelab.kr 앱 비밀번호 3개 시도 전부 실패. 관리자 콘솔 IMAP/SMTP ON. 원인 미확인. (2026-05-29)
