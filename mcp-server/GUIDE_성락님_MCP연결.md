# 비코어랩 MCP 서버 연결 가이드 (성락님용)

## 이게 뭔가요?
사무실 맥미니에 메타 광고/물류/소싱 데이터를 조회할 수 있는 서버가 돌아가고 있어요.
Claude Code에서 이 서버를 연결하면 **캡처 없이 메타 광고 데이터를 직접 조회**할 수 있어요!

## 1단계: Tailscale 연결 확인

PC에 Tailscale이 설치되어 있으면 연결 상태를 확인해주세요.
```
tailscale status
```
`macmini`가 보이면 OK!

## 2단계: Claude Code에 MCP 서버 등록

Claude Code 터미널에서 아래 명령어를 실행해주세요:

```bash
claude mcp add becorelab --transport sse --url http://100.105.211.14:8500/sse
```

이게 끝이에요! 이제 Claude Code에서 메타 광고 데이터를 직접 조회할 수 있어요.

## 3단계: 연결 확인

Claude Code에서 이렇게 물어보면 돼요:
- "메타 광고 어제 성과 보여줘"
- "식세기 캠페인 오디언스 연령별 데이터 보여줘"
- "메타 캠페인 목록 보여줘"

## 사용 가능한 메타 광고 도구

| 도구 | 설명 | 주요 파라미터 |
|:--|:--|:--|
| `becorelab_meta_ad_insights` | 캠페인 성과 조회 (핵심!) | account, since/until, level, breakdowns |
| `becorelab_meta_ad_insights_all` | 일비아+세탁제품 한번에 조회 | since/until |
| `becorelab_meta_ad_campaigns` | 캠페인 목록 | account |
| `becorelab_meta_ad_accounts` | 계정 정보 | - |

### 오디언스 데이터 조회 예시

**연령/성별별 성과:**
```
meta_ad_insights(account="일비아", since="2026-05-15", until="2026-05-21", level="campaign", breakdowns="age,gender")
```

**노출 지면별 성과:**
```
meta_ad_insights(account="일비아", since="2026-05-15", until="2026-05-21", level="ad", breakdowns="publisher_platform,platform_position")
```

**소재(광고)별 성과:**
```
meta_ad_insights(account="일비아", date_preset="last_7d", level="ad")
```

### breakdowns 파라미터
- `age,gender` → 연령/성별별 분류
- `publisher_platform,platform_position` → 노출 지면별 분류
- 비워두면 → 캠페인/광고 단위 합산

### date_preset 옵션
- `today`, `yesterday`, `last_7d`, `last_14d`, `last_30d`
- 또는 `since`/`until`로 직접 날짜 지정 (YYYY-MM-DD)

### level 옵션
- `campaign` → 캠페인별
- `adset` → 광고세트별
- `ad` → 개별 광고(소재)별

## 기타 사용 가능한 도구
- **물류**: 모닝 브리핑, 일일 매출, 재고 현황
- **소싱**: 스캔 목록, 상세 분석, GO 상품
- **네이버 광고**: 캠페인 목록, 키워드 성과
- **옵시디언 볼트**: 보고서 읽기/쓰기

## 문제가 생기면?
- Tailscale 연결 확인 → `tailscale status`에서 macmini가 online인지
- 서버 상태 확인 → 브라우저에서 `http://100.105.211.14:8500/sse` 접속해보기
- 안 되면 대표님이나 하치한테 알려주세요!
