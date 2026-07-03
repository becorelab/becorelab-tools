# 카카오 선물 트렌드 — 개발 가이드 (오퍼스/다음 개발자용)

> 2026-07-03 하치(Fable) 최초 구축. **페이블 없이도 이어서 개발할 수 있게** 아키텍처·철학·다음 단계를 정리.
> 코드만 보면 "무엇"은 알아도 "왜"를 놓치니, 이 문서를 먼저 읽고 손대세요.

## 왜 만들었나 (목적)
카카오 선물하기 베스트 랭킹을 매일 수집·누적해서 **"무슨 제품이 잘 팔리나 → 비코어랩이 만들 신제품 빈자리"**를 도출한다. 비코어랩은 생활·리빙(세제/생필품) 브랜드 + 하반기 선물용 신제품 기획 중. ERP "선물 트렌드" 탭에서 직원과 공유(대표님 요청).

## 판매량 측정의 진실 ⭐ (가장 중요 — 실호출로 검증한 사실)
카카오는 **주문수를 대놓고 안 준다.** 그래서 판매 신호를 다중으로 잡는다(정확도순):
1. **리뷰 증분** (reviewTotal Δ) — 실제 산 사람이 남김. 주문수 대체 최선. 상품 상세 API 필요.
2. **찜 증분** (wishCount Δ) — 관심(안 사도 찜). 표본 큼.
3. **순위 변동** (rank Δ) — 종합 결과.
4. **주문수** (orderCount) — 트렌딩 탭 일부 상품만 fomoBadge에 노출(마케팅 배지). 보너스.
- **절대량 아닌 증분 추세**로 봐야. 리뷰는 구매 며칠 뒤 일부만 작성 → "추세 방향"이지 정확한 판매량 아님.
- **캘리브레이션 계획**: 자사 에어밤(고체탈취제, 7/13 카카오 런칭) 실판매(판매자센터)↔리뷰증분 대조 → "리뷰 1 = 실판매 N" 보정 → 경쟁사 리뷰증분으로 실판매량 추정. (소싱 하치 6/17 전략)

## 아키텍처 (데이터 흐름)
```
rank_track.py (매일 9:50 크론)
  ├ 랭킹 API(무인증 POST): 16탭 × TOP40 랭킹 수집
  ├ 상세 API(무인증 GET): 각 탭 TOP20 리뷰수(reviewTotal) 수집 — 판매신호
  └ → rank_snapshots/YYYY-MM-DD.json (날짜별 누적 = 이력)
                    │
ERP erp/app.py (FastAPI :8085)
  ├ GET /api/kakao/rank      : 탭별 랭킹 + 전일 대비 변동(move/wishDelta/reviewDelta/orderDelta)
  ├ GET /api/kakao/insights  : 카테고리 활발도·검증베스트·판매급상승(리뷰증분) 분석
  └ GET /api/kakao/dates     : 수집된 날짜 목록
                    │
ERP erp/static/js/app.js (SPA)
  └ '선물 트렌드' 탭: [🏆 랭킹] 카드뷰 + [📊 인사이트] 분석뷰 (loadKakao/loadKakaoInsight)
```

## 파일 지도
| 파일 | 역할 |
|---|---|
| `kakao_gift_tracker/rank_track.py` | ⭐ 랭킹+리뷰 수집기. TARGETS(수집 카테고리), REVIEW_DETAIL_TOPN 여기서 조정 |
| `kakao_gift_tracker/track.py` | (기존) 재고차분 추적기 — 별개 목적(탈취제 재고감소=판매추정) |
| `kakao_gift_tracker/run_tracking.sh` | 크론 러너(track.py + rank_track.py 둘 다) |
| `kakao_gift_tracker/rank_snapshots/*.json` | 날짜별 스냅샷(이력) |
| `erp/app.py` (KAKAO_SNAPDIR 검색) | 백엔드 3개 API. JSON 직접 서빙(DB 안 씀) |
| `erp/static/js/app.js` (loadKakao 검색) | 프론트 카드뷰 + 인사이트뷰 |
| `erp/templates/index.html` (page-kakao 검색) | 탭 HTML + `.kakao-*` CSS |

## 수집 카테고리 (대표님 확정 2026-07-03)
리빙(navId 5) 전체 12개 하위 + 유아동 물티슈(3,142) + 트렌딩 3개(위시TOP/신상/단독) = 16탭.
**향(캔들디퓨저)에 한정 안 함** — 비코어랩=생활/리빙 브랜드라 리빙 전체가 본진. navId는 `required-data`(GET)에서 실시간 확인 가능. `rank_track.py`의 TARGETS 수정으로 가감.

## 개발 시 주의 (함정)
- **ERP 정적파일 수정 시 캐시버전 필수**: `templates/index.html`의 `app.js?v=YYYYMMDDx` 올려야 브라우저 반영(안 올리면 옛 화면 고착 — 실제로 겪은 버그).
- **ERP 코드 수정 후 서버 재시작**: `launchctl kickstart -k "gui/$(id -u)/com.becorelab.erp-web"`. FastAPI 상주라 재시작 안 하면 반영 안 됨.
- **리뷰 상세 호출 부하**: 16탭 × TOP20 = 최대 320호출(중복캐시로 실제 적음), ~2.5분. REVIEW_DETAIL_TOPN 늘리면 시간·차단위험 증가.
- **화면 검증은 Playwright 스크린샷으로 눈으로** (`/tmp/kakao_verify.py`, `/tmp/kakao_insight.py` 참고). 직원 계정 srhwang/staff로 권한도 확인.

## 다음 단계 (미완/후보)
- **[데이터 2~4주 후] 판매 급상승 정확도↑**: 리뷰증분이 며칠 쌓이면 인사이트 '판매 급상승'이 진짜 강력해짐. 지금은 첫날이라 비어있음.
- **빈자리 분석(Phase 2)**: 카테고리별 가격대 밀집도 히스토그램 → 비어있는 가격 구간 = 우리 진입점. insights API에 priceBands 추가 여지(코드에 자리 있음).
- **자사 제품 매칭**: 우리 향자산(코튼블루 등) 이식 후보 카테고리에 우리가 진입 시 예상 순위 시뮬.
- **에어밤 캘리브레이션**: 7/13 런칭 후 실판매 입력받아 리뷰증분 계수 산출.
- **경쟁사 레이더(:8091) 연계**: project_competitor_radar와 카카오 채널 통합 여지.

## 관련 메모리
`project_kakao_gift_tracker`(전체 맥락·API 상세), `project_competitor_radar`, `infra_obsidian_vault_path`.
