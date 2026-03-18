# 이지어드민 데이터 수집 — 클로드 인 크롬 프롬프트 가이드

## 전체 흐름

1. **재고현황 (I100)** — 상품별 현재 재고 수집
2. **재고수불부 (I500)** — 최근 90일 상품별 출고량 수집
3. **확장주문검색2 (DS00)** — 어제 날짜 채널별 매출 수집
4. 수집 완료 후 `localhost:8082/api/chrome-upload`로 한 번에 전송

> 이지어드민에 미리 로그인된 상태에서 사용하세요.

---

## 전체 프롬프트 (복붙용)

아래 프롬프트를 클로드 인 크롬에 그대로 복사해서 사용하세요.

---

```
아래 3개 페이지를 순서대로 방문하여 테이블 데이터를 수집한 뒤, 마지막에 localhost:8082 API로 한 번에 전송해줘.

수집할 데이터를 각각 inventory, outbound, sales 변수에 저장해.

────────────────────────────
[1단계] 재고현황 (I100)
────────────────────────────

URL: https://ka04.ezadmin.co.kr/template35.htm?template=I100

1) 페이지 이동 후 4초 대기
2) blockUI 팝업이 있으면 제거: document.querySelectorAll('.blockUI').forEach(el => el.remove())
3) "검색" 버튼 클릭 (span.flip 텍스트가 "검색"인 요소)
4) 6초 대기 후 다시 팝업 제거
5) 페이지 크기를 최대로 변경: .ui-pg-selbox 셀렉트 박스에서 마지막 옵션 선택 후 change 이벤트 발생
6) 3초 대기

테이블 데이터 추출:
- 테이블: #grid1 또는 .ui-jqgrid-btable
- 각 행(tr)에서:
  - 상품코드: td[aria-describedby$="_key"] 의 텍스트
  - 정상재고: td[aria-describedby$="_stock"] 의 텍스트 (숫자, 콤마 제거)
- 상품코드가 3자 이상인 행만 수집
- 결과를 inventory 배열에 저장: [{code: "상품코드", stock: 정상재고수량}, ...]

────────────────────────────
[2단계] 재고수불부 (I500)
────────────────────────────

URL: https://ka04.ezadmin.co.kr/template35.htm?template=I500

1) 페이지 이동 후 5초 대기
2) blockUI 팝업 제거
3) 날짜 필드 설정:
   - 모든 input 중 yyyy-mm-dd 형식 값을 가진 필드를 찾아서
   - 첫 번째(시작일) = 오늘 기준 90일 전 날짜
   - 두 번째(종료일) = 오늘 날짜
4) "검색" 버튼 클릭
5) 8초 대기 후 팝업 제거
6) 페이지 크기 최대로 변경
7) 5초 대기

테이블 데이터 추출 (페이지네이션 포함):
- 테이블: #grid1 또는 .ui-jqgrid-btable
- 각 행(tr)에서:
  - 상품코드: td[aria-describedby="grid1_product_id"]
  - 상품명: td[aria-describedby="grid1_name"]
  - 일자: td[aria-describedby="grid1_crdate"] (앞 10자만, yyyy-mm-dd)
  - 출고수량: td[aria-describedby="grid1_stockout"] (숫자)
  - 배송수량: td[aria-describedby="grid1_trans"] (숫자)
  - 판매량 = 출고수량 + 배송수량
- 상품코드 3자 이상 & 날짜 10자 & 판매량 > 0 인 행만 수집

페이지네이션:
- .ui-pg-button 안의 [class*="seek-next"] 버튼이 있고 ui-state-disabled가 아니면 클릭
- 다음 페이지로 이동 후 4초 대기, 팝업 제거
- 데이터가 없거나 다음 버튼이 비활성화되면 중단
- 최대 50페이지까지

날짜+상품코드별로 중복 집계하여 outbound 배열에 저장:
[{date: "2025-01-15", code: "상품코드", qty: 합계수량}, ...]

────────────────────────────
[3단계] 확장주문검색2 (DS00)
────────────────────────────

URL: https://ka04.ezadmin.co.kr/template35.htm?template=DS00

1) 페이지 이동 후 5초 대기
2) blockUI 팝업 제거
3) 날짜 설정:
   - #start_date 값 = 어제 날짜
   - #end_date 값 = 어제 날짜
4) "검색" 버튼 클릭 → 8초 대기 → 팝업 제거
5) 페이지 크기 최대로 변경 → 2초 대기 → 다시 "검색" 클릭 → 6초 대기 → 팝업 제거

테이블 데이터 추출 (페이지네이션 포함):
- 테이블: #grid1 또는 .ui-jqgrid-btable
- 행 선택: tr.jqgrow (헤더 제외)
- 각 행에서:
  - 판매처(shop): td[aria-describedby="grid1_shop_id"]
  - 발주일(date): td[aria-describedby="grid1_collect_date"]
  - 상품코드(code): td[aria-describedby="grid1_product_id"]
  - 상품명(name): td[aria-describedby="grid1_name"]
  - 상품명+옵션(nameOpt): td[aria-describedby="grid1_product_name_options"]
  - 옵션(option): td[aria-describedby="grid1_p_options"]
  - 주문수량(orderQty): td[aria-describedby="grid1_qty"] (숫자)
  - 상품수량(productQty): td[aria-describedby="grid1_order_products_qty"] (숫자)
  - 판매가(amount): td[aria-describedby="grid1_amount"] (숫자)
  - 정산금액(settlement): td[aria-describedby="grid1_supply_price"] (숫자)
  - 현재고(stock): td[aria-describedby="grid1_stock"] (숫자)
- 상품코드가 있는 행만 수집

페이지네이션: 2단계와 동일 방식 (최대 20페이지)

채널별 집계:
- by_channel: {판매처명: {count, qty, amount, settlement}}
- by_product: {상품코드: {name, qty, amount, settlement}}
- total_amount, total_settlement, total_count 계산

sales 객체에 저장:
{
  date: "어제날짜",
  total_amount: 총판매금액,
  total_settlement: 총정산금액,
  total_count: 총건수,
  by_channel: {...},
  by_product: {...},
  orders: [전체 주문 배열]
}

────────────────────────────
[4단계] 데이터 전송
────────────────────────────

3개 페이지 수집이 모두 끝나면 아래 fetch로 전송:

fetch('http://localhost:8082/api/chrome-upload', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({inventory, outbound, sales})
})

전송 결과(성공/실패)를 알려줘.
각 데이터 건수도 요약해줘:
- 재고: N개 상품
- 출고: N건 (90일)
- 매출: N건 (어제)
```

---

## 간편 버전 프롬프트 (매일 복붙용)

매일 빠르게 사용할 때는 아래 짧은 버전을 쓰세요.

```
이지어드민에서 3개 데이터를 수집해서 로컬 서버로 보내줘.

1) https://ka04.ezadmin.co.kr/template35.htm?template=I100 에서 재고현황 수집
   - 검색 버튼 클릭 후 #grid1 테이블에서 상품코드(td[aria-describedby$="_key"])와 정상재고(td[aria-describedby$="_stock"]) 추출
   - 페이지 크기 최대로(.ui-pg-selbox 마지막 옵션)
   - blockUI 팝업은 항상 제거

2) https://ka04.ezadmin.co.kr/template35.htm?template=I500 에서 90일 출고량 수집
   - 날짜 input에 90일 전~오늘 설정 후 검색
   - td[aria-describedby="grid1_product_id"], grid1_crdate, grid1_stockout, grid1_trans 추출
   - 판매량 = stockout + trans, 페이지네이션 처리

3) https://ka04.ezadmin.co.kr/template35.htm?template=DS00 에서 어제 매출 수집
   - #start_date, #end_date에 어제 날짜 설정 후 검색
   - grid1_shop_id, grid1_product_id, grid1_name, grid1_qty, grid1_order_products_qty, grid1_amount, grid1_supply_price 추출
   - 채널별/상품별 집계

전부 수집 후 아래로 전송:
fetch('http://localhost:8082/api/chrome-upload', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({inventory, outbound, sales})
})

건수 요약도 알려줘.
```

---

## 참고사항

- **팝업 제거**: 이지어드민은 페이지마다 blockUI 팝업을 띄움. 매 단계에서 `.blockUI` 요소를 전부 제거해야 함
- **검색 버튼**: `span.flip` 중 텍스트가 "검색"인 요소를 클릭
- **페이지 크기**: `.ui-pg-selbox` 셀렉트박스의 마지막 옵션을 선택하고 `change` 이벤트 발생
- **페이지네이션**: `.ui-pg-button [class*="seek-next"]`의 부모가 `ui-state-disabled`가 아니면 클릭
- **숫자 파싱**: 모든 숫자 컬럼은 콤마(,)를 제거하고 parseInt 처리
- **로그인 필요**: 프롬프트 실행 전에 이지어드민에 로그인 상태여야 함
