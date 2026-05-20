# 소싱 파킹랏

- [ ] **미오(Managed Agent) API 키 복구** — Anthropic 콘솔에서 활성 키 확인 후 재발급 → `/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/.env`의 `ANTHROPIC_API_KEY` 교체. 교체 후 `python mio/run.py '테스트 요청'`으로 `client.beta.sessions.create` 성공 확인. (2026-04-23 대표님 확인 필요)
- [ ] **OneDrive 볼트 "항상 유지" 설정** — 사무실 Finder에서 `01. Becorelab AI Agent Team` 폴더 우클릭 → "이 장치에서 항상 유지" (2.1MB, 용량 무관) (2026-05-06)
- [ ] **크롬 확장 → 소싱앱 자동 연동** — background service worker로 소싱앱 작업 큐 폴링 → 자동 수집 → 결과 전송. 리뷰/상품/키워드 모두 확장 가능. Wing Akamai 차단 우회 (2026-05-20)
