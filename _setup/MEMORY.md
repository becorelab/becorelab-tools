# 하치 메모리 파일

## 대표님 정보
- 이름: Kyle Chung (정건양)
- 직책: CEO
- 회사: 주식회사 비코어랩 (Becorelab Co., Ltd.)
- 브랜드: iLBiA (일비아)
- 이메일: kychung@becorelab.kr
- 웹사이트: www.ilbia.co.kr
- 국가: 한국

## 하치 페르소나
- 세부 내용은 `/Users/kymac/Desktop/claude/CLAUDE.md` 참조
- 핵심: 대표님을 "대표님"으로 호칭, 상냥하고 애교스럽게, 확인 질문 없이 바로 실행

## iLBiA 주력 제품군
- 건조기 시트 (코튼블루 / 베이비크림 / 바이올렛 머스크)
- 식기세척기 세제
- 캡슐 세제
- 얼룩 제거제
- 섬유 탈취제 (준비 중)
- 고체형 실내 탈취제 (준비 중)

## 유통 채널
- 자사몰 (카페24), 네이버 스마트스토어, 쿠팡, 11번가, G마켓, 옥션, 오늘의집

## 폴더 구조 (프로젝트 중심)
- `~/claude/sourcing/` — 소싱매니저 코드 + `output/` (결과물) + `alibaba_profile/`
- `~/claude/rocket/` — 로켓배송 코드 + `output/` (로그) + `data/` (엑셀 원본)
- `~/claude/instagram/` — 인스타 공동구매 DM 자동화
- `~/claude/accounting/` — 회계 (매출정산.html + 2026.01/ 월별 데이터)
- `~/claude/logistics/` — 물류 (발주대시보드.html, 발주분석.html)
- `~/claude/tools/` — 일반 도구 (calculator.html, ilbia.html)
- Git 레포: `~/claude/.git` (origin: becorelab/becorelab-tools, private: becorelab/ilbia-private)
- 모노레포 방식으로 관리

## 주요 프로젝트

### sourcing_app.py — iLBiA 소싱 매니저 (Flask 웹앱)
- 실행: `python3 sourcing_app.py` → http://localhost:8080
- 기능: 알리바바 업체 문의 발송 + 히스토리 관리
- DB: `sourcing.db` (SQLite) — inquiries 테이블
- 상태 흐름: pending → sent → replied → ordered / failed / cancelled
- API: `/api/send`, `/api/history`, `/api/status/<id>`, `/api/update_status`, `/api/export/csv`
- alibaba_search.py에서 `_get_headless_page_with_cookies`, `_find_storefront_url`, `_send_alibaba_inquiry` import
- 메시지 템플릿: Kyle Chung / Becorelab / iLBiA 서명 포함, {company}/{product_link}/{target_price}/{quantity}/{spec} 플레이스홀더

### alibaba_search.py — 알리바바 소싱 자동화 (Playwright, headless Chrome)
- headless 모드로 실행 (창 없이 백그라운드)
- Contact Supplier 폼 방식으로 문의 발송
- 문의 메시지에 제품 링크 포함
- 세부사항: [alibaba_notes.md](alibaba_notes.md) 참조

### rocket_main.py / rocket_config.py — 쿠팡 로켓배송 자동화
- 쿠팡 어드민 ID: becorelab
- 이지어드민 도메인: bypl
- WORK_DIR: /Users/kymac/claude/

### instagram_app.py — 인스타 공동구매 DM 자동화 (Flask 웹앱)
- 실행: `python3 instagram_app.py` → http://localhost:8081
- 기능: 인스타그램 공동구매 제안 DM 자동 발송 + 대시보드
- 구성: instagram_app.py (서버) + instagram_bot.py (Playwright 봇) + templates/dashboard.html (UI)
- DB: `instagram.db` (SQLite) — accounts, dm_log, settings 테이블
- 봇 로직: 해시태그 탐색 → 진성 계정 필터링 (팔로워 1만~10만, 좋아요율 1%, 댓글율 0.5%) → DM 발송
- 발송량: 하루 20~30개 (랜덤), 1~5분 간격 딜레이 (봇 차단 방지)
- DM 템플릿 4종 랜덤 선택
- APScheduler 1시간 간격 자동 실행
- 민감 파일: session.json (인스타 로그인 세션) — .gitignore 관리

### HTML 툴들 (Desktop/claude/)
- `calculator.html` — 계산기
- `ilbia.html` — iLBiA 관련
- `매출정산.html`, `발주대시보드.html`, `발주분석.html` — 매출/발주 관리

## 해결된 이슈
- **IP 문제 (해결)**: 소싱 매니저 앱을 여러 PC에서 공유 사용하려 했으나 단일 IP만 지원 → **각 PC에 개별 설치·실행하는 방식으로 결정**

## GitHub 워크플로우
- 앱/스크립트 작업 완료 후 반드시 GitHub에 커밋 & 푸시
- 레포: https://github.com/becorelab/becorelab-tools (비공개)
- gh CLI: `~/bin/gh` (실행 전 `export PATH="$HOME/bin:$PATH"` 필요)
- 민감 파일(rocket_config.py 등 비밀번호 포함)은 절대 커밋 금지 — .gitignore로 관리
