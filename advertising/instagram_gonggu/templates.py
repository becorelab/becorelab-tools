"""인스타 공동구매 DM 템플릿 — 수백 가지 조합 생성.

기존 instagram_bot.py 방식 계승: opener + reason + hook + closer 블록 랜덤 조합.
페르소나: "패밀리케어 브랜드 일비아"
"""
import random

# ── 1차 DM — 블록 조합 ──────────────────────────────────────

DM_OPENERS = [
    "안녕하세요, 패밀리케어 브랜드 일비아입니다 😊",
    "안녕하세요! 생활세제 브랜드 일비아(iLBiA)예요 🙂",
    "안녕하세요, 일비아(iLBiA) 마케팅팀입니다 😊",
    "안녕하세요! 패밀리케어 브랜드 iLBiA 일비아예요 🙂",
]

DM_REASONS = [
    "{username}님 피드 보다가 저희 브랜드랑 분위기가 너무 잘 맞아서 연락드려요.",
    "{username}님 계정 구경하다가 생활용품 공구하시면 반응 좋을 것 같아서 용기 내서 연락드려요.",
    "{username}님 피드 분위기가 저희 브랜드 감성이랑 정말 잘 어울려서 연락드리게 됐어요.",
    "{username}님 게시물 보다가 팔로워분들이 좋아하실 제품이 있어서 연락드려요.",
    "{username}님 피드 보면서 저희 세제 브랜드랑 톤이 딱 맞는다 싶어서요.",
    "{username}님 계정 우연히 발견했는데 살림 감성이 너무 좋아서 연락드려요.",
]

DM_HOOKS = [
    "혹시 공동구매 해보신 적 있으신가요?",
    "공동구매 경험 있으세요? 저희 건조기 시트가 공구로 반응이 좋아서요.",
    "생활세제 공동구매 혹시 관심 있으실까요?",
    "혹시 공구에 관심 있으실지 여쭤보고 싶었어요.",
    "저희 건조기 시트, 식기세척기 세제 등 공구 관심 있으실까 해서요.",
    "생활용품 공구 관심 있으시면 좋은 조건으로 제안드리고 싶어요.",
]

DM_CLOSERS = [
    "관심 있으시면 편하게 답장 주세요 😊",
    "관심 있으시면 말씀해 주세요, 자세한 조건 안내드릴게요 🙂",
    "혹시 관심 있으시면 편하게 DM 주세요 😊",
    "관심 있으시면 답장 주시면 자세히 안내드릴게요 🙂",
]

DM_EXTRA_EMOJIS = ["", " ☁️", " 🧺", " 🫧", " ✨", ""]

# ── 2차 DM (관심 응답 시) — 대표님이 직접 사용할 참고용 ─────

FOLLOWUP_TEMPLATE = """관심 가져주셔서 감사해요!
저희 iLBiA는 건조기시트, 캡슐세제, 식기세척기세제 등 생활세제 브랜드예요.

공구 조건 간단히 안내드릴게요 👇
- 샘플: 무료 발송 (직접 써보신 후 진행)
- 공구 기간: 3~5일
- 수수료: 판매가의 15~20% (성과형)
- 상세 이미지/링크 모두 저희가 준비해드려요

진행 방식이나 일정은 {username}님 편하신 대로 맞출게요.
궁금하신 점 있으시면 편하게 물어봐주세요 😊"""


def generate_dm(username: str, personal_hook: str = "") -> str:
    """1차 DM 메시지 생성 — 블록 랜덤 조합."""
    opener = random.choice(DM_OPENERS)
    reason = random.choice(DM_REASONS).replace("{username}", f"@{username}")
    hook = random.choice(DM_HOOKS)
    closer = random.choice(DM_CLOSERS) + random.choice(DM_EXTRA_EMOJIS)

    parts = [opener, reason]
    if personal_hook:
        parts.append(personal_hook)
    parts.extend([hook, closer])

    return "\n".join(parts)


def generate_followup(username: str) -> str:
    """2차 DM (참고용)."""
    return FOLLOWUP_TEMPLATE.format(username=username)
