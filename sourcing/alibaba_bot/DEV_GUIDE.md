# 알리바바 자동 채팅봇 DEV_GUIDE (오퍼스 인계용)

> 2026-07-06 페이블 하치가 하루 만에 구축. **이 문서만 읽으면 이어서 개발/운영 가능하게 쓴 것.**
> 대표님 목표: "상대 답장을 감지하고 알아서 재답장하는 완전 자동 채팅봇" — 승인 모드(레나)로는 부족, 무인 신뢰 모드가 요구사항.

## 구조 (전부 이 폴더)
```
bot.py      메인. launchd가 5분마다 1회 실행 (스캔→감지→판단→전송→통지)
brain.py    headless Claude(claude -p) 협상 판단. reply/skip/escalate JSON
briefs.md   ★대표님이 직접 수정하는 협상 브리프. 여기 없는 숫자는 봇이 절대 제시 안 함
notify.py   텔레그램 (레나 봇 토큰 재사용: Channel_lena/.env, 대표님 chat_id 8708718261)
state.json  대화별 최신 메시지 해시 + 일일 전송 카운트 (자동 생성, git 제외)
logs/       일별 로그 + launchd 로그
```
launchd: `com.becorelab.alibaba-bot` (5분, DRY_RUN=0 라이브). 중지: `launchctl unload ~/Library/LaunchAgents/com.becorelab.alibaba-bot.plist`

## 크리티컬 노하우 (재발견에 하루 걸린 것들 — 꼭 읽기)
1. **로그인**: ChromeCDP 프로필(9222 헤드리스, launchd `com.becorelab.chrome-cdp`)에 알리바바 세션 저장됨 (7/6 QR 로그인).
   만료 시 봇이 텔레그램으로 알림 → 재로그인 방법: 9222는 헤드리스+launchd KeepAlive라 **헤디드 전환 불가**.
   `/tmp/alibaba_qr4.py` 방식(QR 캔버스 캡처→sips 확대→open→폰 앱 스캔) + `/tmp/alibaba_login_watch.py`(로그인 감지 폴링) 재사용.
   ⚠️ 9223 크롬은 서플라이허브 전용 — 절대 건드리지 말 것.
2. **번역 모드 입력창**: 채팅창 textarea가 2개. 위(`new-send-textarea`)는 **readOnly 번역 표시용** — 타이핑이 조용히 실패함(과거 alibaba_reply 버그 원인). 반드시 readOnly 아닌 쪽(placeholder "Type here to translate")에 입력. `mio/tools.py` alibaba_reply도 7/6 같은 로직으로 수정됨.
3. **메시지 버블 DOM 순서 ≠ 시간순** (버추얼 스크롤): `.message-item-wrapper`를 DOM 순서로 읽으면 3월 메시지가 마지막에 옴. **getBoundingClientRect().y로 정렬** 필수 (bot.py read_bubbles).
4. **발화자 구분**: 클래스 `item-right`=우리, `item-left*`=상대.
5. **인박스 셀렉터**: 대화목록 `.contact-item-container`, 미확인 배지 `.unread-num`. 목록 텍스트 구조: 이름 다음 줄이 시각(HH:MM 또는 YYYY-M-D), 그다음 회사, 그다음 미리보기.
6. **감지 로직**: 미리보기 해시 변경 OR unread>0 → 대화 열어 확인. 열면 알리바바가 읽음 처리하므로 unread 트리거는 자연 소멸(재처리 안 됨). 마지막 발화가 `us`면 무조건 스킵(루프 방지).

## 안전장치 (완화하려면 bot.py 상수)
- 첫 실행 = 베이스라인만(과거 메시지에 답장 폭탄 방지). state.json 지우면 베이스라인부터 다시.
- 대화당 3회/일, 전체 12회/일 (`MAX_PER_CONV_PER_DAY`, `MAX_TOTAL_PER_DAY`)
- 콰이어트아워 23:00~07:30
- brain 에스컬레이션 조건: 결제/주문확정/PI/주소/샘플비/브리프 밖 숫자/스펙확정/상대 항의 → 초안과 함께 텔레그램
- 락파일(.bot.lock)로 중복 실행 방지. DRY_RUN=1이면 전송 없이 초안만 텔레그램.

## 검증 이력 (2026-07-06)
- 인박스 읽기/대화 읽기/타이핑 검증/전송 확인 로직 전부 실측 통과
- brain: 콜드피치→skip, 목표가 미기입 프로젝트 가격질문→escalate(홀딩 초안 포함), 기존 문의 팔로업→reply 정상 판단
- 엔드투엔드 DRY_RUN: AYI Dai 해시 리셋→감지→초안 텔레그램 도착 확인
- **미검증 1개: 라이브 전송** (실거래 상대라 임의 발송 안 함). 첫 라이브 전송이 나가면 텔레그램 통지로 확인되고, 안 나가면 send_reply의 "전송 클릭됨(불확실)" 로그 확인할 것.

## 테스트 방법
- 특정 대화 강제 재처리: state.json에서 해당 대화 last_hash를 아무 값으로 바꾸고 `DRY_RUN=1 python bot.py`
- brain 단독: `python brain.py "이름" "회사" "[상대] 메시지"`
- 텔레그램 단독: `python notify.py "테스트"`

## 다음 개선 후보 (파킹)
- briefs.md 깔창 목표가 대표님 기입 대기 (기입 전까지 가격 협상은 전부 에스컬레이션됨 — 의도된 동작)
- 이미지/파일 첨부 메시지 대응 (현재 텍스트만)
- 전송 확인 로직 정밀화 (번역 발송 시 원문≠발송문 이슈)
- 새 프로젝트 시작 시 briefs.md에 섹션 추가하는 것만으로 봇이 협상 커버
