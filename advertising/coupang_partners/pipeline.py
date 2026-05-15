"""쿠팡 파트너스 유튜버 컨택 파이프라인 — 중앙 오케스트레이터.

macOS crontab에서 서브커맨드별 호출:
  python pipeline.py crawl    — YouTube 크롤 + Haiku 스크리닝 + 구글 시트 추가
  python pipeline.py send     — 승인된 유튜버에게 메일 발송
  python pipeline.py check    — 이메일 답장 확인
  python pipeline.py status   — 파이프라인 현황 요약
"""
import sys
import os
import argparse
import json
import time
import requests
from datetime import datetime, timezone

# ── 경로 설정 ────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── .env 로드 (YOUTUBE_API_KEY 등) ───────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(_DIR, "..", "..", "sourcing", "analyzer", ".env"))

# ── 내부 모듈 ────────────────────────────────────────────────────
from config import DAILY_SEND_LIMIT, PARTNERS_SUBJECT_PREFIX
from youtube_crawler import search_coupang_partners_channels, enrich_full
from screener import screen_channel
from naverworks_mail import send_mail
from auto_reply import process_replies

# ── 구글 시트 설정 ───────────────────────────────────────────────
import gspread
from google.oauth2.service_account import Credentials

KEY_PATH = "/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json"
SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"
CANDIDATE_SHEET_NAME = "후보 리스트"

_gc = None


def _sheets_client():
    """gspread 클라이언트 싱글턴."""
    global _gc
    if _gc is None:
        creds = Credentials.from_service_account_file(KEY_PATH, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
        ])
        _gc = gspread.authorize(creds)
    return _gc


def _get_candidate_sheet():
    """후보 리스트 워크시트 반환."""
    gc = _sheets_client()
    sh = gc.open_by_key(SHEET_ID)
    try:
        return sh.worksheet(CANDIDATE_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        # 시트가 없으면 헤더와 함께 생성
        ws = sh.add_worksheet(title=CANDIDATE_SHEET_NAME, rows=500, cols=15)
        headers = [
            "channel_id", "채널명", "구독자", "카테고리", "이메일",
            "채널URL", "선정이유", "추천제품", "AI점수", "승인",
            "상태", "발송일", "message_id", "비고", "등록일",
        ]
        ws.update(values=[headers], range_name="A1:O1")
        return ws


# ── 시트 동기화 함수들 (sheet_sync) ──────────────────────────────

def sheet_get_existing_channel_ids() -> set:
    """시트에 이미 등록된 channel_id 집합."""
    ws = _get_candidate_sheet()
    col_values = ws.col_values(12)  # L열(12번째) = channel_id
    return set(col_values[1:])  # 헤더 제외


def sheet_append_candidates(candidates: list[dict]):
    """새 후보를 시트 하단에 추가."""
    if not candidates:
        return
    ws = _get_candidate_sheet()
    rows = []
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    for c in candidates:
        channel_url = f"https://www.youtube.com/channel/{c['channel_id']}"
        screen = c.get("screen", {})
        last_upload = c.get("last_upload_date", "")[:10] if c.get("last_upload_date") else ""
        # 실제 시트 컬럼: A=채널명 B=채널URL C=구독자수 D=카테고리 E=최근영상일
        #                 F=추천제품 G=선정이유 H=이메일 I=상태 J=승인 K=메모 L=channel_id M=발견일 N=개인화훅
        rows.append([
            c.get("title", ""),                                      # A 채널명
            channel_url,                                             # B 채널URL
            c.get("subscriber_count", 0),                            # C 구독자수
            c.get("category", ""),                                   # D 카테고리
            last_upload,                                             # E 최근영상일
            ", ".join(screen.get("matched_products", [])),           # F 추천제품
            screen.get("rationale", ""),                             # G 선정이유
            c.get("contact_email", ""),                              # H 이메일
            "screened",                                              # I 상태
            "",                                                      # J 승인 — 대표님이 수동 입력
            "",                                                      # K 메모
            c.get("channel_id", ""),                                 # L channel_id
            now_str,                                                 # M 발견일
            screen.get("personal_hook", ""),                         # N 개인화훅
        ])
    ws.append_rows(rows, value_input_option="USER_ENTERED")


def sheet_get_approved_unsent() -> list[dict]:
    """승인(J열=idx9)됐지만 아직 미발송(I열=idx8 != contacted)인 행 반환.
    실제 시트 칼럼: A(0)=채널명 B(1)=채널URL C(2)=구독자수 D(3)=카테고리 E(4)=최근영상일
                   F(5)=추천제품 G(6)=선정이유 H(7)=이메일 I(8)=상태 J(9)=승인
                   K(10)=메모 L(11)=channel_id M(12)=발견일"""
    ws = _get_candidate_sheet()
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return []
    results = []
    for i, row in enumerate(all_rows[1:], start=2):
        if len(row) < 9 or not row[0]:
            continue
        approval = (row[9] if len(row) > 9 else "").strip()
        status = (row[8] if len(row) > 8 else "").strip()
        if approval in ("승인", "approved") and status not in ("contacted", "replied", "sample_sent", "uploaded"):
            results.append({
                "row_number": i,
                "channel_id": row[11] if len(row) > 11 else "",
                "name": row[0],
                "subscriber_count": row[2],
                "category": row[3],
                "email": row[7],
                "channel_url": row[1],
                "personal_hook": row[13] if len(row) > 13 else "",
            })
    return results


def sheet_update_sent(row_number: int, message_id: str, sent_date: str):
    """발송 완료 후 시트 업데이트: I열=상태, K열=메모(발송일+msg_id)."""
    ws = _get_candidate_sheet()
    ws.update(values=[["contacted"]], range_name=f"I{row_number}")
    ws.update(values=[[f"발송완료 {sent_date}"]], range_name=f"K{row_number}")


def sheet_update_replied(row_number: int):
    """답장 수신 시 상태 업데이트 (I열)."""
    ws = _get_candidate_sheet()
    ws.update(values=[["replied"]], range_name=f"I{row_number}")


def sheet_get_status_counts() -> dict:
    """상태별 카운트."""
    ws = _get_candidate_sheet()
    all_rows = ws.get_all_values()
    counts = {}
    for row in all_rows[1:]:
        if len(row) < 9 or not row[0]:
            continue
        status = (row[8] or "screened").strip()  # I열(idx8) = 상태
        counts[status] = counts.get(status, 0) + 1
    # 승인 컬럼도 집계
    approval_counts = {}
    for row in all_rows[1:]:
        if len(row) < 10 or not row[0]:
            continue
        approval = (row[9] or "미검토").strip()  # J열(idx9) = 승인
        approval_counts[approval] = approval_counts.get(approval, 0) + 1
    return {"status": counts, "approval": approval_counts}


# ── 크롤 키워드 ──────────────────────────────────────────────────
KEYWORDS = [
    # 핵심 — 살림/육아
    "쿠팡 추천템 살림",
    "쿠팡 살림템 리뷰",
    "육아템 추천 쿠팡",
    # 확장 — 세탁/빨래/청소
    "세탁 꿀팁 추천",
    "빨래 루틴 브이로그",
    "청소 꿀템 추천",
    # 확장 — 자취/원룸/신혼
    "자취템 추천 생활용품",
    "신혼살림 필수템",
    "원룸 살림 꿀템",
    # 니치 — 주방/홈인테리어/반려동물
    "주방용품 추천 리뷰",
    "홈인테리어 살림",
    "반려동물 살림 꿀팁",
]


# ── 메일 템플릿 ──────────────────────────────────────────────────
# 쿠팡 파트너스 연결 상품 링크 (캡슐 표백제)
_CAPSULE_URL = "https://www.coupang.com/vp/products/9454938820"

# 공통 브랜드 소개 블록 (3개 템플릿 동일)
_BRAND_INTRO = (
    "저희는 패밀리케어 브랜드 iLBiA(일비아)예요.\n"
    "건조기 시트로 시작해서 지금은 식기세척기 세제, 캡슐 세제까지 라인업을 넓혀왔어요.\n"
    "저희 브랜드와 전체 제품 라인업은 자사몰 www.ilbia.co.kr 에서 확인하실 수 있어요."
)

_OFFER_BLOCK = (
    "기본 협업 범위는 영상 1편 + 설명란에 쿠팡 파트너스 링크 1개예요.\n"
    "제품 풀세트(건조기 시트, 캡슐 표백제, 식기세척기 세제, 얼룩 제거제)는 기본으로 보내드리고,\n"
    "원고료나 쿠팡 파트너스 수수료 등 세부 조건은 {name}님 채널 상황에 맞춰 편하게 협의드려요."
)

_CTA_BLOCK = (
    "관심 있으시면 이번 주 내로 편하게 답장 주세요.\n"
    "받으실 주소만 알려주시면 바로 발송 시작할게요.\n\n"
    "감사합니다.\n\n"
    "비코어랩 마케팅팀\n"
    "www.ilbia.co.kr"
)

TEMPLATES = {
    "A": {
        "subject": "{name}님, 살림 채널에 어울릴 신제품 제안드려요",
        "body": (
            "{name}님 안녕하세요, 비코어랩 마케팅팀이에요.\n\n"
            + _BRAND_INTRO + "\n\n"
            "{name}님 채널 꾸준히 보고 있는데, 실제로 써본 후 추천하시는 톤이 저희 제품과 잘 맞을 것 같아 연락드려요.{personal_hook}\n\n"
            "최근에 새로 출시한 '캡슐 표백제'를 소개드리고 싶어요.\n"
            "▶ 쿠팡 상품 페이지: " + _CAPSULE_URL + "\n\n"
            "세탁조에 캡슐 하나 넣으면 표백과 세정이 동시에 되는 제품이에요. "
            "산소계 성분이라 색상 옷에도 써도 되고, 비포/애프터 차이가 뚜렷해서 살림 콘텐츠로 풀어내기 좋아요.\n\n"
            + _OFFER_BLOCK + "\n\n"
            + _CTA_BLOCK
        ),
    },
    "B": {
        "subject": "{name}님, 아기 옷 세탁 주제로 신제품 제안드려요",
        "body": (
            "{name}님 안녕하세요, 비코어랩 마케팅팀이에요.\n\n"
            + _BRAND_INTRO + "\n\n"
            "{name}님 채널 꾸준히 보고 있는데, 육아하는 집 관점에서 제품을 꼼꼼히 고르시는 스타일이 저희 브랜드 철학과 잘 맞아서 연락드려요.{personal_hook}\n\n"
            "최근에 새로 출시한 '캡슐 표백제'를 소개드리고 싶어요.\n"
            "▶ 쿠팡 상품 페이지: " + _CAPSULE_URL + "\n\n"
            "세탁조에 캡슐 하나 넣으면 표백과 세정이 동시에 되는 제품이에요. "
            "산소계 표백 성분이라 아기 옷에도 안심하고 쓰실 수 있고, 침구류 얼룩이나 이염 잡는 데 효과가 확실해요.\n\n"
            + _OFFER_BLOCK + "\n\n"
            + _CTA_BLOCK
        ),
    },
    "C": {
        "subject": "{name}님, 새로 출시한 제품 하나 보내드리고 싶어요",
        "body": (
            "{name}님 안녕하세요, 비코어랩 마케팅팀이에요.\n\n"
            + _BRAND_INTRO + "\n\n"
            "{name}님이 직접 써보고 솔직하게 리뷰하시는 스타일이 저희 제품과 잘 맞을 것 같아 연락드려요.{personal_hook}\n\n"
            "최근에 새로 출시한 '캡슐 표백제'를 소개드리고 싶어요.\n"
            "▶ 쿠팡 상품 페이지: " + _CAPSULE_URL + "\n\n"
            "세탁조에 캡슐 하나 넣으면 표백과 세정이 동시에 되는 제품이에요. "
            "산소계 성분이라 색상 옷에도 안전하게 쓸 수 있고, 아직 유튜브에 리뷰 영상이 많지 않아서 선점 효과도 기대할 만해요.\n\n"
            + _OFFER_BLOCK + "\n\n"
            + _CTA_BLOCK
        ),
    },
}


def _pick_template_type(category: str) -> str:
    """카테고리 키워드로 템플릿 타입 결정."""
    cat_lower = category.lower() if category else ""
    if any(kw in cat_lower for kw in ["살림", "생활", "빨래", "청소"]):
        return "A"
    if any(kw in cat_lower for kw in ["육아", "아기", "반려"]):
        return "B"
    return "C"


# ── 서브커맨드: crawl ────────────────────────────────────────────

def cmd_crawl():
    """YouTube 크롤 + Haiku 스크리닝 + 구글 시트 추가."""
    print(f"{'='*60}")
    print(f"[CRAWL] 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"키워드 {len(KEYWORDS)}개: {KEYWORDS}")
    print(f"{'='*60}")

    # 1) 기존 시트의 channel_id 로드 (중복 방지)
    try:
        existing_ids = sheet_get_existing_channel_ids()
        print(f"[DEDUP] 시트에 기존 채널 {len(existing_ids)}개")
    except Exception as e:
        print(f"[WARN] 시트 읽기 실패, 중복 체크 스킵: {e}")
        existing_ids = set()

    # 2) 키워드별 크롤
    all_raw_channels = {}  # channel_id -> partial data
    for kw in KEYWORDS:
        print(f"\n[SEARCH] '{kw}' 검색 중...")
        try:
            hits = search_coupang_partners_channels(kw)
            for h in hits:
                cid = h.get("channel_id")
                if cid and cid not in existing_ids:
                    all_raw_channels.setdefault(cid, h)
            print(f"  -> {len(hits)}개 채널 발견, 신규 누적 {len(all_raw_channels)}개")
        except Exception as e:
            print(f"  [ERROR] 검색 실패: {e}")

    if not all_raw_channels:
        print("\n[DONE] 새로운 후보 없음")
        return

    # 3) 각 채널 상세 수집 + 스크리닝
    qualified = []
    for i, (cid, raw) in enumerate(all_raw_channels.items(), 1):
        print(f"\n[ENRICH] ({i}/{len(all_raw_channels)}) {cid}")
        try:
            enriched = enrich_full(cid)
        except Exception as e:
            print(f"  [ERROR] 상세 조회 실패: {e}")
            continue

        # 필터: 구독자 범위 + 최근 활동 + 이메일 있음
        if not enriched.get("is_in_tier"):
            print(f"  [SKIP] 구독자 범위 밖 ({enriched.get('subscriber_count', 0):,})")
            continue
        if not enriched.get("is_fresh"):
            print(f"  [SKIP] 최근 업로드 없음")
            continue
        if not enriched.get("contact_email"):
            print(f"  [SKIP] 이메일 없음")
            continue

        # Haiku 스크리닝
        print(f"  [SCREEN] {enriched.get('title', '')} ({enriched.get('subscriber_count', 0):,}명)")
        try:
            screen_result = screen_channel(enriched)
            enriched["screen"] = screen_result
            print(f"  -> score={screen_result.get('match_score')}, verdict={screen_result.get('verdict')}")
        except Exception as e:
            print(f"  [WARN] 스크리닝 실패: {e}")
            enriched["screen"] = {
                "match_score": 5,
                "matched_products": [],
                "rationale": f"스크리닝 오류: {e}",
                "verdict": "maybe",
            }

        qualified.append(enriched)

    # 4) 시트에 추가
    if qualified:
        try:
            sheet_append_candidates(qualified)
            print(f"\n[SHEET] {len(qualified)}개 후보 시트에 추가 완료")
        except Exception as e:
            print(f"\n[ERROR] 시트 추가 실패: {e}")
            # 로컬 백업
            backup_path = os.path.join(_DIR, "crawl_backup.json")
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(qualified, f, ensure_ascii=False, indent=2, default=str)
            print(f"  로컬 백업: {backup_path}")

    # 요약
    print(f"\n{'='*60}")
    print(f"[CRAWL 완료]")
    print(f"  검색 키워드: {len(KEYWORDS)}개")
    print(f"  발견 채널: {len(all_raw_channels)}개 (중복 제외)")
    print(f"  적격 후보: {len(qualified)}개 (시트 추가됨)")
    print(f"{'='*60}")


# ── 서브커맨드: send ─────────────────────────────────────────────

def cmd_send():
    """승인된 유튜버에게 메일 발송."""
    print(f"{'='*60}")
    print(f"[SEND] 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"일일 발송 한도: {DAILY_SEND_LIMIT}통")
    print(f"{'='*60}")

    try:
        unsent = sheet_get_approved_unsent()
    except Exception as e:
        print(f"[ERROR] 시트 조회 실패: {e}")
        return

    if not unsent:
        print("[DONE] 발송 대기 중인 승인 건 없음")
        return

    print(f"[QUEUE] 발송 대기: {len(unsent)}명")

    sent_count = 0
    errors = []

    for c in unsent:
        if sent_count >= DAILY_SEND_LIMIT:
            print(f"\n[LIMIT] 일일 한도 {DAILY_SEND_LIMIT}통 도달, 나머지는 내일 발송")
            break

        name = c["name"]
        email = c["email"]
        if not email:
            print(f"  [SKIP] {name} — 이메일 없음")
            continue

        ttype = _pick_template_type(c.get("category", ""))
        tpl = TEMPLATES[ttype]
        subject = f"{PARTNERS_SUBJECT_PREFIX} {tpl['subject'].format(name=name)}"
        hook = c.get("personal_hook", "") or ""
        hook_with_space = " " + hook if hook else ""
        body = tpl["body"].format(name=name, personal_hook=hook_with_space)

        print(f"\n[MAIL] {name} ({email}) — Type {ttype}")
        try:
            result = send_mail(to=email, subject=subject, body_ko=body)
            msg_id = result.get("message_id", "")
            sent_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

            # 시트 업데이트
            sheet_update_sent(c["row_number"], msg_id, sent_date)
            sent_count += 1
            print(f"  -> 성공! Message-ID: {msg_id[:50]}...")

            # 레이트리밋 방지
            time.sleep(3)
        except Exception as e:
            print(f"  -> 실패: {e}")
            errors.append({"name": name, "email": email, "error": str(e)})

    # 요약
    print(f"\n{'='*60}")
    print(f"[SEND 완료]")
    print(f"  발송 성공: {sent_count}통")
    print(f"  발송 실패: {len(errors)}건")
    if errors:
        for err in errors:
            print(f"    - {err['name']} ({err['email']}): {err['error']}")
    remaining = len(unsent) - sent_count - len(errors)
    if remaining > 0:
        print(f"  남은 대기: {remaining}명 (내일 발송)")
    print(f"{'='*60}")


# ── 서브커맨드: check ────────────────────────────────────────────

def cmd_check():
    """이메일 답장 확인 + 자동 분류 + 자동 답장."""
    print(f"{'='*60}")
    print(f"[CHECK] 답장 확인 + 자동 답장 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    try:
        stats = process_replies()
        if stats["total"] == 0 and stats["skipped"] == 0:
            print("[DONE] 새 회신 없음")
    except Exception as e:
        print(f"[ERROR] 답장 처리 실패: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"[CHECK 완료]")
    print(f"{'='*60}")


# ── 서브커맨드: status ───────────────────────────────────────────

def cmd_status():
    """파이프라인 현황 요약."""
    print(f"{'='*60}")
    print(f"[STATUS] 쿠팡 파트너스 유튜버 컨택 파이프라인")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    try:
        counts = sheet_get_status_counts()
    except Exception as e:
        print(f"[ERROR] 시트 조회 실패: {e}")
        return

    status_counts = counts.get("status", {})
    approval_counts = counts.get("approval", {})
    total = sum(status_counts.values())

    print(f"\n총 후보: {total}명")
    print(f"\n[상태별]")
    status_order = ["screened", "approved", "contacted", "replied",
                    "sample_sent", "uploaded", "ghosted", "rejected", "blacklisted"]
    status_labels = {
        "screened": "1차 스크리닝 완료",
        "approved": "승인 (발송 대기)",
        "contacted": "메일 발송 완료",
        "replied": "답장 수신",
        "sample_sent": "샘플 발송",
        "uploaded": "영상 업로드",
        "ghosted": "잠수",
        "rejected": "거절",
        "blacklisted": "블랙리스트",
    }
    for s in status_order:
        cnt = status_counts.get(s, 0)
        if cnt > 0:
            label = status_labels.get(s, s)
            print(f"  {label}: {cnt}명")
    # 기타 상태
    for s, cnt in status_counts.items():
        if s not in status_order and cnt > 0:
            print(f"  {s}: {cnt}명")

    print(f"\n[승인 현황]")
    for k, v in sorted(approval_counts.items()):
        print(f"  {k}: {v}명")

    print(f"\n{'='*60}")


# ── 서브커맨드: notify ───────────────────────────────────────────

DOORI_BOT_TOKEN = "8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"
DOORI_CHAT_ID = "8708718261"


def cmd_notify():
    """승인 대기 후보가 있으면 두리를 통해 텔레그램 알림."""
    ws = _get_candidate_sheet()
    all_rows = ws.get_all_values()

    pending = []
    for row in all_rows[1:]:
        if len(row) < 10 or not row[0]:
            continue
        status = (row[8] if len(row) > 8 else "").strip()
        approval = (row[9] if len(row) > 9 else "").strip()
        if status == "screened" and not approval:
            name = row[0]
            subs = row[2] if len(row) > 2 else ""
            pending.append(f"  • {name} ({subs}명)")

    if not pending:
        print("[NOTIFY] 승인 대기 후보 없음 — 알림 스킵")
        return

    text = (
        f"🐰 대표님~ 두리예요!\n\n"
        f"유튜브 파트너스 승인 대기 후보 {len(pending)}명이 있어요:\n\n"
        + "\n".join(pending[:10])
        + (f"\n  ...외 {len(pending)-10}명" if len(pending) > 10 else "")
        + "\n\n시트에서 J열에 '승인' 입력해주시면 자동 발송돼요 💕"
    )

    resp = requests.post(
        f"https://api.telegram.org/bot{DOORI_BOT_TOKEN}/sendMessage",
        json={"chat_id": DOORI_CHAT_ID, "text": text},
        timeout=10,
    )
    if resp.ok:
        print(f"[NOTIFY] 텔레그램 알림 발송 완료 ({len(pending)}명)")
    else:
        print(f"[NOTIFY] 텔레그램 발송 실패: {resp.status_code} {resp.text[:200]}")


# ── argparse ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="쿠팡 파트너스 유튜버 컨택 파이프라인",
    )
    sub = parser.add_subparsers(dest="command", help="실행할 커맨드")
    sub.required = True

    sub.add_parser("crawl", help="YouTube 크롤 + Gemini 스크리닝 + 구글 시트 추가")
    sub.add_parser("send", help="승인된 유튜버에게 메일 발송")
    sub.add_parser("check", help="이메일 답장 확인")
    sub.add_parser("status", help="파이프라인 현황 요약")
    sub.add_parser("notify", help="승인 대기 후보 텔레그램 알림")

    args = parser.parse_args()

    commands = {
        "crawl": cmd_crawl,
        "send": cmd_send,
        "check": cmd_check,
        "status": cmd_status,
        "notify": cmd_notify,
    }

    try:
        commands[args.command]()
    except KeyboardInterrupt:
        print("\n[중단됨]")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL] 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
