# 알리바바 유사상품 검색 — Claude in Chrome 가이드

## 사용 방법

1. `python test_server.py` 실행
2. 브라우저에서 `http://localhost:8095/` 접속
3. 판매 페이지 URL 또는 이미지 URL 입력
4. **프롬프트 생성** 클릭 → 복사
5. Claude in Chrome에 붙여넣기
6. 결과가 자동으로 페이지에 표시됨

## 지원 입력 형태

- 쿠팡 상품 페이지: `https://www.coupang.com/vp/products/...`
- 네이버 상품 페이지: `https://smartstore.naver.com/...`
- 이미지 URL: `https://...jpg`

## 알리바바 이미지 검색 작동 방식

1. 레퍼런스 페이지 방문 → 상품명/이미지/키워드 추출
2. 알리바바 이미지 검색 (`https://www.alibaba.com/`)
3. 카메라 아이콘 → 이미지 URL 붙여넣기 → 검색
4. 이미지 검색 실패 시 → 키워드 텍스트 검색으로 자동 전환
5. 상위 10개 공급업체 수집 (가격/MOQ/Gold/평점/URL)
6. `localhost:8095/api/result`로 전송

## 수집 데이터

| 항목 | 설명 |
|------|------|
| title | 알리바바 상품명 |
| price | 가격 범위 |
| moq | 최소주문수량 |
| supplier | 공급업체명 |
| isGold | Gold Supplier 여부 |
| rating | 거래건수/평점 |
| url | 상품 URL |
