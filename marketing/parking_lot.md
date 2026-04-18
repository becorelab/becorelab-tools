# 마케팅 파킹랏

- [ ] 카페 바이럴 자동화 — 미오가 콘텐츠 생성 + 타겟 카페 리서치 + 반응 모니터링, 포스팅은 사람 (2026-04-17)
- [ ] 네이버 브랜드 커넥트 공구 + 미오 적용 검토
- [ ] **2026-04-27 (월)**: 쿠팡 파트너스 DAILY_SEND_LIMIT 10 → 15 조정 (`marketing/coupang_partners/config.py`)
- [ ] **2026-05-04 (월)**: DAILY_SEND_LIMIT 15 → 20
- [ ] **2026-05-11 (월)**: DAILY_SEND_LIMIT 20 → 30 (목표 도달)

## 두리/레나 모델 최적화 (2026-04-18 박제)
- [ ] **두리 모델 다운그레이드 검토** — 현재 `start-doori.ps1`은 `--model opus`(4.7)로 실행 중인데, 메모리 결정(`feedback_model_choice.md`)은 "두리는 Haiku"로 정리돼 있음. 불일치 해결 + 응답속도 ↑ + 비용 ↓. 복귀 후 처리.
- [ ] **레나 Opus 4.6 fast mode 적용 조사** — `/fast`는 세션 내부 토글 명령. 스크립트 기동 시 자동 활성화 옵션 존재 여부 확인 필요. 가능하면 `start-lena.ps1`에 적용.

## ✅ 쿠팡 파트너스 크론 안정화 (2026-04-19 완료)
- [x] Task Scheduler 옵션 보강 (StartWhenAvailable, WakeToRun, AllowStartIfOnBatteries, DontStopIfGoingOnBatteries)
- [x] 이벤트 로그 활성화 (`Microsoft-Windows-TaskScheduler/Operational`)
- [x] 어제 미실행 6명 오늘 수동 발송 완료 (13명 전원 contacted)
- [ ] 주간 모니터링 (`Get-ScheduledTaskInfo`로 LastRunTime 주 1회 확인)

## 카페 바이럴 v2.1 — 대표님 판단 대기 (2026-04-19 박제)
국내 바이럴 전문가 5인(송길영/이승윤/김난도/양승화/송인상) 기준 재설계 완료. 네이버 카페 ONLY 범위로 축소.
- [ ] 대표님 판단 3가지 후 PRD 박제:
  1. 시드 유저 범위 (쿠팡 Q&A only vs 자사몰 구매자 포함)
  2. 제휴 유형 초기 집중 (체험단+이벤트 샘플 조합 추천)
  3. 시작 시점 (2026-05-04 추천, 쿠팡 파트너스 파이프라인 2주 축적 후)
- 구조: Phase 0 카페 맵핑 → Phase 1 매니저 제휴(유튜버 파이프라인 포크) → Phase 2 시드 유저 후기 → Phase 3 모니터링
- NSM: 월간 카페 자발 언급 수 / AARRR 퍼널
