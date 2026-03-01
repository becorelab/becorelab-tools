# Alibaba 소싱 자동화 세부 노트

## 파일 위치
- `/Users/kymac/Desktop/claude/alibaba_search.py`

## 핵심 구조
1. Google 검색으로 알리바바 제품 링크 수집
2. Contact Supplier 폼으로 문의 발송 (onetalk 아님)
3. Headless Chrome으로 백그라운드 실행

## 중요 기술 사항
- **Chrome CDP**: `p.chromium.connect_over_cdp('http://localhost:9222')` — 사용자 Chrome의 쿠키 추출용
- **헤드리스 실행**: 쿠키를 headless Chromium에 주입하여 로그인 상태 유지
- **Contact Supplier URL**: `message.alibaba.com/msgsend/contact.htm`
- **keyboard.type()**: fill() 대신 사용해야 Alibaba JS 검증 통과
- **onetalk 한계**: 새 업체와 첫 대화 시작 불가 → Contact Supplier 폼 사용

## 메시지 템플릿 (ALIBABA_MESSAGE_TEMPLATE)
- `{company}`, `{product_link}` 플레이스홀더 사용
- 제품 링크를 메시지에 포함 (업체들이 어떤 제품인지 재문의하는 문제 해결)

## Store URL 탐색 (3단계 폴백)
1. 제품 페이지에서 `.en.alibaba.com` 링크 추출
2. 회사명에서 slug 추측 (`condibe` → `condibe.en.alibaba.com`)
3. 알리바바 공급업체 검색

## 이메일 점수 시스템 (score_email)
- 회사 키워드 매칭: +3점
- 중국 도메인: +1점
- sales/info 접두사: +1점
- 소스 URL에 회사 키워드: +2점
- 점수 0 → 발송 안 함
