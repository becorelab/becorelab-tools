# CLAUDE.md — 비코어랩 소싱 파이프라인

## 프로젝트 개요
쿠팡 시장 분석 → 소싱 기회 발굴 → 1688 공급업체 탐색 → 견적 비교 → 발주까지의 **이커머스 소싱 풀 파이프라인**.

대표님의 소싱 업무 흐름:
1. **키워드 스캔** — 쿠팡에서 키워드별 상위 40개 상품 데이터 수집
2. **기회점수 분석** — 매출 분포, 진입 기대매출, 신상품 가중치 등으로 기회 평가
3. **리뷰 분석** — 상위 상품 리뷰에서 소비자 불만/니즈 추출
4. **상세 분석** — Claude AI로 시장 진입 전략 리포트 생성
5. **RFQ 발송** — 1688 공급업체에 견적 요청
6. **견적 비교** — 공급업체 응답 비교 → 발주 결정

## 앱 구성

### 소싱박스 (메인 앱) — `analyzer/`
- **포트**: 8090
- **실행**: `python analyzer/app.py` (프로젝트 루트에서)
- **기능**: 키워드 스캔, 기회점수, 리뷰 분석, RFQ, 골드박스 크롤링
- **DB**: Firebase Firestore (`becorelab-tools`)
- **프론트엔드**: `analyzer/templates/index.html` (SPA)

### 알리바바 문의 발송 — `sourcing_app.py`
- **포트**: 8080
- **기능**: 알리바바 업체 자동 문의 발송 + 히스토리 관리
- **DB**: SQLite (`sourcing.db`)
- **자동화**: Playwright + Chrome CDP 쿠키 추출

### 미오 (AI 소싱 에이전트) — `mio/`
- Claude API 기반 자율 소싱 에이전트
- 1688 검색, 상품 비교, 견적 요청을 자연어로 수행

## 주요 모듈

### analyzer/ (소싱박스 백엔드)
| 파일 | 역할 |
|:---|:---|
| `app.py` | Flask 메인 앱, 모든 API 라우트 |
| `wing.py` | 쿠팡윙 로그인 + 헬프스토어 연동 (Playwright persistent context) |
| `helpstore.py` | 헬프스토어 API/브라우저 스캔, 상품·키워드 데이터 모델 |
| `scoring.py` | 기회점수 산출 엔진 (매출 분산도, 진입 기대매출, 신상품 가중치) |
| `reviews.py` | 리뷰 수집 + Gemini/Claude AI 분석 |
| `firestore_db.py` | Firestore CRUD (스캔, 상품, 키워드, RFQ, 견적) |
| `categories.py` | 쿠팡 카테고리 매핑 |
| `notebooklm.py` | NotebookLM 연동 |

### 1688 연동 스크립트
| 파일 | 역할 |
|:---|:---|
| `search_1688.py` | Elimapi로 1688 키워드 검색 |
| `find_1688.py` | 1688 상품 상세 조회 |
| `compare_1688.py` | 유사 제품 비교 → 구글 시트 업로드 |
| `imgsearch_1688.py` | 이미지 검색으로 1688 상품 찾기 |
| `sheet_1688.py` | 1688 검색 결과 시트 정리 |
| `chat_1688.py` | CDP로 1688 판매자 채팅 |
| `cdp_1688_detail.py` | CDP로 1688 상품 상세 크롤링 |

## 핵심 기술 사항

### 쿠팡윙 (`wing.py`)
- Playwright **persistent context** — `.wing_profile/`에 세션 저장
- macOS: `sys.platform == 'darwin'`이면 headed 모드, 확장 경로 `~/Library/Application Support/Google/Chrome/Default/Extensions/`
- 헬프스토어 확장 ID: `nfbjgieajobfohijlkaaplipbiofblef`
- 크리덴셜: `WING_ID`, `WING_PW`, `HELPSTORE_ID`, `HELPSTORE_PW` (파일 내 하드코딩)

### 기회점수 (`scoring.py`)
대표님 핵심 기준:
- 매출 분포가 고른 시장 (상위3 독식 X)
- 300만원+ 판매자가 40~50% 이상
- 4~10등 평균매출 = 진입 시 기대매출
- 신상품 가중치 (매출/리뷰/1000) — 리뷰 적은데 잘 팔리면 수요 신호

### 헬프스토어 (`helpstore.py`)
- API 모드: 헬프스토어 REST API 직접 호출 (빠르지만 일부 데이터 제한)
- CDP 모드: Chrome DevTools Protocol로 브라우저 자동화 (느리지만 풀 데이터)
- `keyboard.type()` 사용 — `fill()` 대신 써야 Alibaba JS 검증 통과

### Firestore (`firestore_db.py`)
- 프로젝트: `becorelab-tools`
- 서비스 계정 키: `analyzer/becorelab-tools-firebase-adminsdk-*.json` (절대 커밋 금지)
- 컬렉션: scans, products, inflow_keywords, keyword_variants, goldbox, rfqs, quotations

## API 주요 엔드포인트

### 스캔
- `POST /api/scan/manual` — 수동 키워드 스캔 (API 모드)
- `POST /api/scan/wing` — 윙 연동 스캔 (판매량 데이터 포함)
- `GET /api/scan/<id>/poll` — 스캔 진행 상태 폴링
- `GET /api/scans` — 전체 스캔 목록

### 분석
- `GET /api/scan/<id>` — 스캔 상세 (상품 + 점수)
- `POST /api/scan/<id>/reviews` — 리뷰 수집 시작
- `POST /api/scan/<id>/detail-analysis` — AI 상세 분석
- `POST /api/scan/<id>/detail-chat` — 분석 결과 기반 대화

### 골드박스
- `POST /api/goldbox/start` — 골드박스 크롤링 시작
- `POST /api/goldbox/auto-scan` — 골드박스 상품 자동 스캔

### RFQ/견적
- `POST /api/rfq` — 견적 요청서 생성
- `POST /api/scan/<id>/rfq/generate` — 스캔 결과에서 RFQ 자동 생성
- `POST /api/quotation` — 견적 응답 등록
- `GET /api/rfq/<id>/compare` — 견적 비교

### 자동 탐색
- `POST /api/autoscan/start` — 시드 키워드에서 연관 키워드 자동 탐색
- `POST /api/autoscan/explore` — 카테고리 기반 자동 탐색
- `GET /api/opportunities` — GO 판정된 기회 상품 목록

## 실행 환경
- Python 3.9+ (맥미니: system python 3.9)
- venv: `../../.venv/` (ClaudeAITeam 루트의 공유 venv)
- 필수 패키지: flask, playwright, firebase-admin, requests, openpyxl
- Playwright chromium: `playwright install chromium`

## 배포/백업
- GitHub: `becorelab/becorelab-tools` (private)
- 민감 파일 커밋 금지: Firebase 키, .env, config.py, .wing_profile/
