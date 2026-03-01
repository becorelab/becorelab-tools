# CLAUDE.md — 비코어랩 소싱 매니저

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
알리바바 업체 문의 자동 발송 + 소싱 히스토리 관리 웹앱

## 실행 방법
```bash
python3 sourcing_app.py
# 브라우저 → http://localhost:8080
```

## 주요 파일
- `sourcing_app.py` — Flask 웹앱 (포트 8080), UI + API + DB 포함
- `alibaba_search.py` — Playwright headless Chrome 자동화 엔진
- `sourcing.db` — SQLite DB (inquiries 테이블)

## 아키텍처
- `sourcing_app.py`가 `alibaba_search.py`에서 3개 함수 import:
  - `_get_headless_page_with_cookies` — Chrome CDP로 쿠키 추출 후 headless에 주입
  - `_find_storefront_url` — 3단계 폴백으로 업체 스토어 URL 탐색
  - `_send_alibaba_inquiry` — Contact Supplier 폼으로 메시지 발송
- 문의 발송은 백그라운드 스레드로 처리 (threading.Thread)
- 상태 흐름: pending → sent → replied → ordered / failed / cancelled

## 주요 기술 사항
- Chrome CDP: `http://localhost:9222` (사용자 Chrome 쿠키 추출용)
- `keyboard.type()` 사용 — `fill()` 대신 써야 Alibaba JS 검증 통과
- Contact Supplier URL: `message.alibaba.com/msgsend/contact.htm`
- 각 PC에 개별 설치·실행 (멀티 IP 공유 불가)

## 배포 방식
- 각 PC에서 독립 실행 (IP 공유 방식 미사용)
- 작업 완료 후 GitHub 푸시: `becorelab/becorelab-tools`
