# Claude Design 프롬프트

## 사용법
1. https://claude.ai/design 접속
2. 아래 프롬프트를 입력창에 붙여넣기
3. `design-spec.json` 파일을 첨부(업로드)
4. Generate 클릭

---

## 프롬프트 (복사용)

```
첨부한 design-spec.json을 기반으로 ERP 웹앱 UI를 만들어줘.

요구사항:
- 다크모드 기반, 왼쪽 사이드바 레이아웃
- JSON에 정의된 6개 페이지 모두 구현 (대시보드, 거래처, 품목, 재고, 매출, 발주)
- 사이드바 클릭으로 페이지 전환 (SPA 방식)
- 데이터 테이블은 JSON의 sample_data 사용
- 모달, 토스트, 페이지네이션 등 공통 컴포넌트 포함
- 한국어 UI
- 반응형 (최소 1280px 기준)
- Vanilla HTML/CSS/JS (프레임워크 없이)

디자인 분위기: 고급스럽고 깔끔한 다크 테마. Claude 스타일의 모던한 느낌.
컬러: 배경 #1a1a2e, 포인트 #d4a574 (골드), 액센트 #7c9ae0 (블루)
폰트: Pretendard, Noto Sans KR
```
