# 🛰️ 경쟁사 레이더 (Competitor Radar)

지정한 경쟁사 제품의 **가격 · 리뷰수 · 평점 · 순위 · 옵션 구성** 변화를 매일 추적하고
한 눈에 보는 대시보드. 알리 확장(1제품 가격그래프, 수동)을 넘어선 **다제품·다지표·자동·변동알림** 시스템.

## 무엇이 다른가
| | 알리 확장 | 경쟁사 레이더 |
|---|---|---|
| 추적 단위 | 상품 1개씩(페이지 열어야) | 지정 제품 여러 개 한 화면 |
| 지표 | 가격 그래프만 | 가격·리뷰수·평점·순위·옵션 |
| 방식 | 수동 | 매일 자동 크론 |
| 알림 | 없음 | 가격↓↑·리뷰급증·순위변동·옵션변경 |

## 실행
```bash
cd ~/ClaudeAITeam/price_tracker
python3 app.py          # http://localhost:8091
```
- 소싱콕 서버(localhost:8090)가 떠 있어야 쿠팡 데이터 수집됨.

## 데이터 소스
- **쿠팡**: 소싱콕(8090) 스캔 데이터 재활용 (Akamai 우회). 가격/리뷰수/순위/월매출/판매량.
  평점·옵션은 상세화면 '⭐ 평점·옵션 분석'으로 리뷰 다운로드 시 보강.
- **네이버**: NaverShoppingCollector 키워드 검색 → 상품명 매칭. 가격/리뷰수/순위.

## 제품 등록
대시보드 우상단 `+ 제품 추가`:
- **플랫폼**: 쿠팡 / 네이버
- **키워드**: 쿠팡=소싱콕 스캔 키워드, 네이버=검색어
- **상품명 매칭어**: 검색결과에서 제품 식별용 부분일치 키워드
- **URL**(선택): 쿠팡 productId 자동 인식
- **우리 제품 체크**: 일비아 제품 표시 → 경쟁사 평균가와 비교

## 매일 자동 수집
- launchd `com.becorelab.radar-daily` — 매일 **09:40** `snapshot.py` 실행.
- 로그: `~/ClaudeAITeam/automation/logs/radar_daily.log`
- 수동 실행: `python3 snapshot.py` (또는 `--reviews` 로 평점/옵션까지)

## 구조
```
price_tracker/
├── app.py            # FastAPI (8091)
├── db.py             # SQLite (data/radar.db): products / snapshots / alerts
├── snapshot.py       # 수집 + 변동 감지 엔진 (크론 진입점)
├── collectors/
│   ├── naver.py      # 네이버 쇼핑
│   └── coupang.py    # 쿠팡(소싱콕)
├── templates/index.html
└── static/css, static/js   # ERP 동일 디자인
```

## 변동 감지 임계치 (snapshot.py)
- 리뷰 급증: +3% 또는 +50건 이상
- 가격/순위/평점: 변동 시 즉시 알림
- 옵션: 신규/삭제 구성 감지
