"""미오 파트너스 에이전트 1회 생성 스크립트.
실행:  python setup.py
"""
import os
import sys
import anthropic
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_dir, "..", "..", "..", "sourcing", "analyzer", ".env"))

MIO_ENV_PATH = os.path.join(_dir, "mio.env")


SYSTEM_PROMPT = """You are 미오 파트너스 (Mio Partners), a YouTube influencer outreach specialist for Becorelab (비코어랩), a Korean e-commerce brand.

## Brand context
- **iLBiA (일비아)**: 생활세제 브랜드. 건조기시트(코튼블루/베이비크림/바이올렛 머스크), 식기세척기 세제, 캡슐 세제, 얼룩 제거제, 섬유 탈취제
- **Omomo (오모모)**: 아이디어 유통 브랜드
- 쿠팡에 등록된 제품들을 마이크로 유튜버에게 **쿠팡 파트너스 링크 기반 협업**으로 제안

## Your mission
마이크로 유튜버(1만~10만 구독자)에게 협업을 제안하고 관계 전 과정을 관리한다.
답장 분류, 단순 협상, 영상 검수는 자율 처리. 단가·계약 조건은 대표님 승인 필요.

## Persona & tone
- 발송 명의: **비코어랩 마케팅팀** (info@becorelab.kr, 네이버웍스)
- 한국어 존댓말, 전문적이면서 친근하게
- 이모지는 절제 (이메일 본문 기준 0~2개)
- AI 티 안 나게 — 채널 영상 구체 레퍼런스 1개 이상 포함

## 🔴 Subject line rule (절대 지킬 것)
모든 outbound 메일 제목은 반드시 **`[iLBiA 쿠팡 파트너스]`** 로 시작한다.
예) `[iLBiA 쿠팡 파트너스] OOO님 채널과의 협업 제안`
→ 답장도 `Re: [iLBiA 쿠팡 파트너스] ...` 형태로 돌아와 네이버웍스 웹메일
필터 규칙이 자동으로 "유튜브 협찬 메일" 폴더로 라우팅한다.

## Tool strategy
- 툴은 I/O 포트다. LLM 텍스트 작성은 네가 직접 한다.
- yt_discover: 키워드로 대량 탐색 → Haiku 1차 스크리닝 (저비용).
  다수 후보가 필요할 때 시작점.
- yt_channel_enrich: 특정 채널 상세 조회 (이메일 초안 작성 직전)
- yt_pitch_write: 작성한 초안 저장 + (dry_run=False일 때만) 네이버웍스 SMTP로 실발송
  - 기본은 dry_run=True (안전). 실발송이 필요할 때만 dry_run=False 명시.
  - to_email 생략 시 candidate.email 자동 조회
- yt_conversation: 답장 초안 저장 + (approved=True일 때만) 실발송
  - 단순 답장(auto 분류)만 approved=True 허용. 단가·조건은 항상 False.
- yt_video_review: 업로드 영상 체크리스트
- yt_reply_classify: 분류 결과 Firestore 기록
- yt_ghost_report: 잠수 큐 조회 + 주간 리포트 조립

## Escalation rules (중요)
즉시 텔레그램 에스컬 (대표님에게):
- 대형 채널(10만+) 관심 표명
- 단가·고정비 협상 요청
- 법무/컴플레인 이슈
- 경쟁사 제품 동시 노출 의심

## Output
- 대표님께는 항상 한국어로 보고
- 툴 호출 전 한 줄로 "무엇을 왜 하는지" 설명
- 최종 결과는 마크다운 요약표"""


TOOLS = [
    {
        "type": "custom",
        "name": "yt_channel_enrich",
        "description": (
            "YouTube Data API로 특정 채널 stats + 최근 영상 5개 + 설명 이메일 수집. "
            "Firestore candidates에 저장. 이메일 초안 작성 전 필수."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "YouTube 채널 ID (UC로 시작)"},
            },
            "required": ["channel_id"],
        },
    },
    {
        "type": "custom",
        "name": "yt_discover",
        "description": (
            "키워드로 유튜버 탐색 → 구독자 tier 필터(1만~10만) → "
            "Haiku 1차 스크리닝 → Firestore 저장. "
            "approved/maybe/rejected 분류된 채널 목록 반환. "
            "예: keyword='주부 살림', target_approved=5."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "한국어 검색 키워드 (예: '주부 살림', '자취 살림', '건조기 팁')",
                },
                "target_approved": {
                    "type": "integer",
                    "description": "approved 목표 수. 달성 시 조기 종료. 기본 5",
                    "default": 5,
                },
                "max_candidates": {
                    "type": "integer",
                    "description": "enrich/스크리닝 최대 채널 수 (YouTube 쿼터 보호). 기본 30",
                    "default": 30,
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "type": "custom",
        "name": "yt_pitch_write",
        "description": (
            "미오가 작성한 아웃리치 이메일 초안을 Firestore에 저장. "
            "dry_run=False이면 네이버웍스 SMTP(info@becorelab.kr)로 실발송 후 message_id 반환. "
            "제목은 반드시 '[iLBiA 쿠팡 파트너스]' 접두사로 시작해야 한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "matched_products": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "채널 성격에 맞는 iLBiA·Omomo 제품명 1~2개",
                },
                "subject": {
                    "type": "string",
                    "description": "이메일 제목 (한국어). 반드시 '[iLBiA 쿠팡 파트너스]' 로 시작",
                },
                "body_ko": {"type": "string", "description": "이메일 본문 (한국어, 평문)"},
                "to_email": {
                    "type": "string",
                    "description": "수신자 이메일. 생략 시 candidate.email 자동 조회",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "True=초안만 저장, False=네이버웍스로 실발송. 기본 True",
                    "default": True,
                },
                "references": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "본문에서 언급한 채널 영상 제목/URL (AI 티 방지용 근거)",
                },
            },
            "required": ["channel_id", "matched_products", "subject", "body_ko"],
        },
    },
    {
        "type": "custom",
        "name": "yt_reply_classify",
        "description": (
            "유튜버 답장 이메일을 3분류(auto/approval/escalate)하고 Firestore에 기록. "
            "category=auto면 미오가 yt_conversation으로 즉시 답장, approval이면 대표님 결재함, "
            "escalate면 텔레그램 즉시 알림."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "email_body": {"type": "string", "description": "수신 메일 원문"},
                "category": {
                    "type": "string",
                    "enum": ["auto", "approval", "escalate"],
                    "description": "auto=단순응답 / approval=단가·조건 협상 / escalate=즉시 대표님",
                },
                "summary_ko": {"type": "string", "description": "한국어 2~3문장 요약"},
                "suggested_action": {"type": "string", "description": "권장 다음 액션"},
            },
            "required": ["thread_id", "email_body", "category", "summary_ko", "suggested_action"],
        },
    },
    {
        "type": "custom",
        "name": "yt_conversation",
        "description": (
            "미오가 작성한 답장 초안을 Firestore 스레드에 추가. "
            "approved=True면 네이버웍스로 즉시 발송 (In-Reply-To 자동 연결), "
            "False면 대표님 결재함 대기. 단순 답장(auto)만 approved=True 허용."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "subject": {
                    "type": "string",
                    "description": "보통 'Re: ' + 원본 제목. 접두사 [iLBiA 쿠팡 파트너스] 유지",
                },
                "body_ko": {"type": "string"},
                "approved": {
                    "type": "boolean",
                    "description": "True면 즉시 발송, False면 대표님 결재 대기 큐로",
                    "default": False,
                },
                "to_email": {
                    "type": "string",
                    "description": "수신자 (보통 마지막 inbound 발신자로 자동 결정, 생략 가능)",
                },
            },
            "required": ["thread_id", "subject", "body_ko"],
        },
    },
    {
        "type": "custom",
        "name": "yt_video_review",
        "description": (
            "업로드된 협업 영상을 검수. YouTube 영상 메타(제목·설명·태그) 수집 후 "
            "체크리스트 기록: #광고 고지 / 제품명 정확성 / 쿠팡 파트너스 링크 / 경쟁사 노출."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "video_url": {"type": "string"},
                "channel_id": {"type": "string"},
                "ad_disclosure_ok": {"type": "boolean"},
                "product_name_ok": {"type": "boolean"},
                "partners_link_ok": {"type": "boolean"},
                "competitor_exposure": {"type": "boolean"},
                "issues_ko": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "발견된 이슈 (수정 요청 근거)",
                },
            },
            "required": ["video_url", "channel_id",
                         "ad_disclosure_ok", "product_name_ok", "partners_link_ok"],
        },
    },
    {
        "type": "custom",
        "name": "yt_ghost_report",
        "description": (
            "Firestore 잠수 대기함(coupang_partners_ghost_queue)을 조회하여 "
            "주간 결재 리포트 본문을 조립하고 저장. 월요일 09:00 텔레그램 발송용."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "week_start_iso": {
                    "type": "string",
                    "description": "주 시작일 ISO (예: 2026-04-20)",
                },
                "notes_ko": {
                    "type": "string",
                    "description": "미오가 추가할 주간 관전 포인트 (선택)",
                },
            },
            "required": ["week_start_iso"],
        },
    },
]


def main():
    if os.path.exists(MIO_ENV_PATH):
        print("mio.env 이미 존재. 새로 만들려면 mio.env 삭제 후 재실행하세요.")
        sys.exit(0)

    client = anthropic.Anthropic()

    print("미오 파트너스 에이전트 설정 시작\n")

    print("1) 환경 생성 중...")
    env = client.beta.environments.create(
        name="mio-partners-env",
        config={
            "type": "cloud",
            "networking": {"type": "unrestricted"},
        },
    )
    print(f"   env: {env.id}\n")

    print("2) 에이전트 생성 중...")
    agent = client.beta.agents.create(
        name="미오 파트너스 에이전트",
        model="claude-opus-4-6",
        system=SYSTEM_PROMPT,
        tools=TOOLS,
    )
    print(f"   agent: {agent.id} (v{agent.version})\n")

    with open(MIO_ENV_PATH, "w", encoding="utf-8") as f:
        f.write(f"MIO_PARTNERS_AGENT_ID={agent.id}\n")
        f.write(f"MIO_PARTNERS_AGENT_VERSION={agent.version}\n")
        f.write(f"MIO_PARTNERS_ENVIRONMENT_ID={env.id}\n")

    print("3) mio.env 저장 완료\n")
    print("=" * 52)
    print("미오 파트너스 세팅 완료")
    print(f"  Agent       : {agent.id}")
    print(f"  Environment : {env.id}")
    print("=" * 52)
    print("\n실행:  python run.py '채널 UCxxxx 아웃리치 초안 써줘'")


if __name__ == "__main__":
    main()
