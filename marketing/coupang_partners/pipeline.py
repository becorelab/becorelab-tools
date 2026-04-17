"""쿠팡 파트너스 유튜버 컨택 파이프라인 — 중앙 오케스트레이터.

Windows Task Scheduler에서 서브커맨드별 호출:
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

KEY_PATH = r"C:\Users\info\claudeaiteam\sourcing\analyzer\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
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
    col_values = ws.col_values(1)  # A열 = channel_id
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
        rows.append([
            c.get("channel_id", ""),
            c.get("title", ""),
            c.get("subscriber_count", 0),
            ", ".join(screen.get("matched_products", [])) or c.get("category", ""),
            c.get("contact_email", ""),
            channel_url,
            screen.get("rationale", ""),
            ", ".join(screen.get("matched_products", [])),
            screen.get("match_score", 0),
            "",  # 승인 — 대표님이 수동 입력
            "screened",
            "",  # 발송일
            "",  # message_id
            "",  # 비고
            now_str,
        ])
    ws.append_rows(rows, value_input_option="USER_ENTERED")


def sheet_get_approved_unsent() -> list[dict]:
    """승인(J열=idx9)됐지만 아직 미발송(L열=idx11 != contacted)인 행 반환.
    시트 칼럼: A=번호 B=채널명 C=구독자 D=카테고리 E=추천제품 F=선정이유
               G=채널URL H=이메일 I=쿠팡파트너스 J=승인 K=메모 L=상태 M=발송일 N=Message-ID"""
    ws = _get_candidate_sheet()
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return []
    results = []
    for i, row in enumerate(all_rows[1:], start=2):
        if len(row) < 10 or not row[1]:
            continue
        approval = (row[9] if len(row) > 9 else "").strip()
        status = (row[11] if len(row) > 11 else "").strip()
        if approval in ("승인", "approved") and status not in ("contacted", "replied", "sample_sent", "uploaded"):
            results.append({
                "row_number": i,
                "channel_id": row[0] if row[0] else "",
                "name": row[1],
                "subscriber_count": row[2],
                "category": row[3],
                "email": row[7],
                "channel_url": row[6],
            })
    return results


def sheet_update_sent(row_number: int, message_id: str, sent_date: str):
    """발송 완료 후 시트 업데이트: L열=상태, M열=발송일, N열=Message-ID."""
    ws = _get_candidate_sheet()
    ws.update(values=[["contacted"]], range_name=f"L{row_number}")
    ws.update(values=[[sent_date]], range_name=f"M{row_number}")
    ws.update(values=[[message_id]], range_name=f"N{row_number}")


def sheet_update_replied(row_number: int):
    """답장 수신 시 상태 업데이트 (L열)."""
    ws = _get_candidate_sheet()
    ws.update(values=[["replied"]], range_name=f"L{row_number}")


def sheet_get_status_counts() -> dict:
    """상태별 카운트."""
    ws = _get_candidate_sheet()
    all_rows = ws.get_all_values()
    counts = {}
    for row in all_rows[1:]:
        if len(row) < 12 or not row[1]:
            continue
        status = (row[11] or "screened").strip()
        counts[status] = counts.get(status, 0) + 1
    # 승인 컬럼도 집계
    approval_counts = {}
    for row in all_rows[1:]:
        if len(row) < 10 or not row[0]:
            continue
        approval = (row[9] or "미검토").strip()
        approval_counts[approval] = approval_counts.get(approval, 0) + 1
    return {"status": counts, "approval": approval_counts}


# ── 크롤 키워드 ──────────────────────────────────────────────────
KEYWORDS = [
    "쿠팡 추천템 살림",
    "쿠팡 파트너스 생활용품",
    "쿠팡 살림템 리뷰",
    "육아템 추천 쿠팡",
    "청소 꿀템 추천",
]


# ── 메일 템플릿 ──────────────────────────────────────────────────
TEMPLATES = {
    "A": {
        "subject": "{name}님, 구독자분들이 댓글로 물어볼 제품이에요",
        "body": """{name}님 안녕하세요!
쿠팡 건조기 시트 리뷰 7,000개, 패밀리케어 브랜드 iLBiA(일비아)입니다.

{name}님 채널 영상 잘 봤어요.
댓글에 세탁 꿀팁 물어보시는 분들이 많으시던데,
저희가 이번에 새로 출시한 '캡슐 표백제'가
딱 그 주제로 영상 하나 나올 수 있는 제품이에요.

세탁조에 캡슐 하나 넣기만 하면 끝이라 사용법도 간단하고,
산소계 표백 성분이라 색상 옷도 안전해요.
비포/애프터가 확실해서 시청자 반응 좋을 것 같아요.

이 외에도 건조기 시트, 식기세척기 세제, 얼룩 제거제 등
iLBiA 제품 풀세트(5~7만원 상당)를 보내드릴게요.

한번 써보시겠어요?
제품 제공 또는 원고료 등 조건은 편하게 맞춰드릴게요.

비코어랩 마케팅팀""",
    },
    "B": {
        "subject": "{name}님 안녕하세요, 영상 소재 하나 제안드려도 될까요?",
        "body": """{name}님 안녕하세요!
쿠팡 건조기 시트 리뷰 7,000개, 패밀리케어 브랜드 iLBiA입니다.

{name}님 영상 보면서 "이 분한테 저희 신제품 보내드리면
진짜 리얼한 후기가 나오겠다" 싶었어요.

아이 있는 집은 세탁이 전쟁이잖아요.
이번에 새로 나온 '캡슐 표백제'가 세탁조에 하나 넣기만 하면 되는 거라
아기 옷 얼룩, 침구류 세탁에 딱이에요.
산소계 성분이라 아기 옷에도 안심이고, 비포/애프터 찍으시면 조회수 터질 소재예요.

캡슐 표백제 외에도 건조기 시트, 얼룩 제거제 등
iLBiA 제품 풀세트(5~7만원 상당)를 보내드릴게요.

마음에 안 드시면 영상 안 만드셔도 되고요.
제품 제공 또는 원고료 등 조건은 편하게 맞춰드릴게요.

비코어랩 마케팅팀""",
    },
    "C": {
        "subject": "{name}님, 신제품 캡슐 표백제 첫 리뷰어 되실래요?",
        "body": """{name}님 안녕하세요!
쿠팡 건조기 시트 리뷰 7,000개, 패밀리케어 브랜드 iLBiA입니다.

{name}님이 추천하시는 것들 보면 진짜 써보고 고르신 게 느껴져서
저희 신제품 첫 리뷰를 {name}님한테 맡기고 싶었어요.

이번에 새로 출시한 '캡슐 표백제'인데,
세탁조에 캡슐 하나 넣으면 표백 + 세정이 한번에 되는 제품이에요.
산소계 성분이라 색상 옷도 OK, 아직 리뷰 영상이 거의 없어서 선점 효과도 있을 거예요.

캡슐 표백제 외에도 건조기 시트, 식기세척기 세제, 얼룩 제거제 등
iLBiA 제품 풀세트(5~7만원 상당)를 함께 보내드릴게요.

제품 제공 또는 원고료 등 조건은 따로 상의해요.

비코어랩 마케팅팀""",
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
        body = tpl["body"].format(name=name)

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


# ── argparse ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="쿠팡 파트너스 유튜버 컨택 파이프라인",
    )
    sub = parser.add_subparsers(dest="command", help="실행할 커맨드")
    sub.required = True

    sub.add_parser("crawl", help="YouTube 크롤 + Haiku 스크리닝 + 구글 시트 추가")
    sub.add_parser("send", help="승인된 유튜버에게 메일 발송")
    sub.add_parser("check", help="이메일 답장 확인")
    sub.add_parser("status", help="파이프라인 현황 요약")

    args = parser.parse_args()

    commands = {
        "crawl": cmd_crawl,
        "send": cmd_send,
        "check": cmd_check,
        "status": cmd_status,
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
