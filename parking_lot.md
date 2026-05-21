# Parking Lot

## 마케팅
- [ ] 인스타 공구 최초 로그인 — `marketing/instagram_gonggu/login_manual.py` 실행 후 브라우저 로그인 (2026-04-25)
- [ ] 두리 모델 다운그레이드 검토 — start-doori.ps1은 opus인데 메모리는 "두리는 Haiku". 불일치 해결 (2026-04-18)

## 소싱
- [ ] 미오 API 키 복구 — Anthropic 콘솔에서 활성 키 확인 후 재발급 → analyzer/.env 교체 (2026-04-23)
- [ ] 크롬 확장 → 소싱앱 자동 연동 — background service worker로 작업 큐 폴링 → 자동 수집 (2026-05-20)

## ERP (이카운트 대체)
- [ ] 발주 데이터 import — 이카운트 Excel 내보내기 or API 활성화 (거래처/발주서 API Not Found 상태)
- [ ] 재고 단종 품목 정리 — 하나씩 확인하면서 비활성화 처리
- [ ] 디자인 고도화 — claude.ai/design 결과물 적용 (design-spec.json + claude-design-prompt.md 준비됨)
- [ ] 발주서 이메일 전송 (AWS SES/SendGrid)
- [ ] 발주서 PDF 생성
- [ ] 이카운트 API Key 갱신 — 만료일 2026-06-02
