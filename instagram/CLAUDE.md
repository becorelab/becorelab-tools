# CLAUDE.md — 인스타그램 공동구매 프로젝트

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
iLBiA 생활세제 공동구매 제안 DM 자동화 앱

## 실행
```bash
cd ~/claude/instagram
python3 instagram_app.py
# → http://localhost:8081
```

## 아키텍처
- **계정 탐색**: instagrapi (HTTP API) — `AccountDiscovery` 클래스
- **DM 발송**: Playwright (브라우저) — `DMSender` 클래스
- **서버**: Flask + APScheduler (1시간 간격, 9시~22시만)
- **DB**: SQLite (`instagram.db`) — accounts, dm_log, settings 테이블
- **대시보드**: 다크 테마, 퍼플~오렌지 그라데이션

## 주요 파일
- `instagram_app.py` — Flask 서버 + 스케줄러 + REST API
- `instagram_bot.py` — 탐색/발송 로직 + DM 조합 생성
- `templates/dashboard.html` — 대시보드 UI
- `login_manual.py` — 최초 로그인 (브라우저 창)

## 민감 파일 (절대 커밋 금지)
- `session.json`, `api_session.json`, `instagram.db`
