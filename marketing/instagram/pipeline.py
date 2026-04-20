"""인스타그램 공동구매 파이프라인 — 중앙 오케스트레이터.

Windows Task Scheduler에서 서브커맨드별 호출:
  python pipeline.py crawl   — 해시태그 크롤 + Haiku 스크리닝 + 구글 시트 추가
  python pipeline.py send    — 승인된 계정에 DM 발송 (session.json 필요)
  python pipeline.py check   — DM 답장 상태 확인 (수동 안내)
  python pipeline.py status  — 파이프라인 현황 요약
"""
import sys
import os
import asyncio
import random
import time
from datetime import datetime, timezone

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(os.path.join(_DIR, "..", "..", "sourcing", "analyzer", ".env"))

from config import (
    KEY_PATH, SHEET_ID, CANDIDATE_SHEET_NAME,
    MIN_FOLLOWERS, MAX_FOLLOWERS, DAILY_SEND_LIMIT,
)
from ig_screener import screen_account
from instagram_bot import (
    AccountDiscovery, DMSender, generate_dm,
    get_db, get_setting, init_db, SESSION_PATH, TARGET_HASHTAGS,
)

import gspread
from google.oauth2.service_account import Credentials

# ── 구글 시트 ────────────────────────────────────────────────────

_gc = None

def _sheets_client():
    global _gc
    if _gc is None:
        creds = Credentials.from_service_account_file(KEY_PATH, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
        ])
        _gc = gspread.authorize(creds)
    return _gc


def _get_sheet():
    gc = _sheets_client()
    sh = gc.open_by_key(SHEET_ID)
    try:
        return sh.worksheet(CANDIDATE_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=CANDIDATE_SHEET_NAME, rows=1000, cols=12)
        headers = [
            "username", "프로필URL", "팔로워", "발견해시태그",
            "좋아요율", "댓글율", "선정이유", "추천제품",
            "상태", "승인", "메모", "발견일",
        ]
        ws.update(values=[headers], range_name="A1:L1")
        return ws


def sheet_get_existing_usernames() -> set:
    ws = _get_sheet()
    col = ws.col_values(1)  # A열 = username
    return set(col[1:])


def sheet_append_accounts(accounts: list[dict]):
    if not accounts:
        return
    ws = _get_sheet()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    rows = []
    for a in accounts:
        screen = a.get("screen", {})
        rows.append([
            a["username"],                                           # A username
            f"https://www.instagram.com/{a['username']}/",          # B 프로필URL
            a.get("followers", 0),                                   # C 팔로워
            a.get("discovered_hashtag", ""),                         # D 발견해시태그
            f"{a.get('like_rate', 0):.2%}",                         # E 좋아요율
            f"{a.get('comment_rate', 0):.2%}",                      # F 댓글율
            screen.get("rationale", ""),                             # G 선정이유
            ", ".join(screen.get("matched_products", [])),           # H 추천제품
            "screened",                                              # I 상태
            "",                                                      # J 승인 — 대표님 수동 입력
            "",                                                      # K 메모
            now_str,                                                 # L 발견일
        ])
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"[SHEET] {len(rows)}개 추가 완료")


def sheet_get_approved_unsent() -> list[dict]:
    """승인됐지만 미발송인 행 반환.
    컬럼: A(0)=username B(1)=URL C(2)=팔로워 D(3)=해시태그
          E(4)=좋아요율 F(5)=댓글율 G(6)=선정이유 H(7)=추천제품
          I(8)=상태 J(9)=승인 K(10)=메모 L(11)=발견일"""
    ws = _get_sheet()
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return []
    results = []
    for i, row in enumerate(all_rows[1:], start=2):
        if len(row) < 9 or not row[0]:
            continue
        approval = (row[9] if len(row) > 9 else "").strip()
        status = (row[8] if len(row) > 8 else "").strip()
        if approval in ("승인", "approved") and status not in ("contacted", "replied"):
            results.append({
                "row_number": i,
                "username": row[0],
                "followers": row[2],
            })
    return results


def sheet_update_sent(row_number: int, sent_date: str):
    ws = _get_sheet()
    ws.update(values=[["contacted"]], range_name=f"I{row_number}")
    ws.update(values=[[f"DM발송 {sent_date}"]], range_name=f"K{row_number}")


def sheet_update_replied(row_number: int):
    ws = _get_sheet()
    ws.update(values=[["replied"]], range_name=f"I{row_number}")


def sheet_get_status_counts() -> dict:
    ws = _get_sheet()
    all_rows = ws.get_all_values()
    counts = {}
    for row in all_rows[1:]:
        if len(row) < 9 or not row[0]:
            continue
        s = (row[8] if len(row) > 8 else "") or "screened"
        counts[s] = counts.get(s, 0) + 1
    return counts


# ── 서브커맨드: crawl ────────────────────────────────────────────

def cmd_crawl():
    print(f"{'='*60}")
    print(f"[CRAWL] 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    ig_user = get_setting("ig_username")
    ig_pass = get_setting("ig_password")
    if not ig_user or not ig_pass:
        print("[ERROR] 인스타 계정 미설정 — 대시보드 설정에서 계정 입력 필요")
        return

    discovery = AccountDiscovery()
    if not discovery.login(ig_user, ig_pass):
        print("[ERROR] instagrapi 로그인 실패")
        return

    try:
        existing = sheet_get_existing_usernames()
    except Exception as e:
        print(f"[ERROR] 시트 조회 실패: {e}")
        return

    hashtag = random.choice(TARGET_HASHTAGS)
    print(f"[HASHTAG] #{hashtag} 탐색 중...")
    raw_results = discovery.discover_hashtag(hashtag, amount=30)

    new_accounts = [
        {**r, "discovered_hashtag": hashtag}
        for r in raw_results
        if r["genuine"] and r["username"] not in existing
        and MIN_FOLLOWERS <= r["followers"] <= MAX_FOLLOWERS
    ]
    print(f"[CRAWL] 신규 적합 계정: {len(new_accounts)}개")

    if not new_accounts:
        print("[DONE] 신규 계정 없음")
        return

    print(f"[SCREEN] Haiku 스크리닝 시작 ({len(new_accounts)}개)...")
    screened = []
    for acc in new_accounts:
        try:
            result = screen_account(acc)
            acc["screen"] = result
            verdict = result.get("verdict", "maybe")
            score = result.get("match_score", 0)
            print(f"  @{acc['username']} — score:{score} verdict:{verdict}")
            if verdict in ("approved", "maybe"):
                screened.append(acc)
        except Exception as e:
            print(f"  [SKIP] @{acc['username']} 스크리닝 오류: {e}")
        time.sleep(0.5)

    print(f"[SCREEN] 통과: {len(screened)}개 (approved+maybe)")
    sheet_append_accounts(screened)
    print(f"[DONE] 크롤 완료 — 시트에서 승인 처리 후 send 실행")


# ── 서브커맨드: send ─────────────────────────────────────────────

async def _send_dms():
    print(f"{'='*60}")
    print(f"[SEND] 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"일일 발송 한도: {DAILY_SEND_LIMIT}통")
    print(f"{'='*60}")

    if not os.path.exists(SESSION_PATH):
        print("[ERROR] session.json 없음")
        print("  → 사무실 PC에서 python login_manual.py 실행 후 로그인 필요")
        return

    try:
        unsent = sheet_get_approved_unsent()
    except Exception as e:
        print(f"[ERROR] 시트 조회 실패: {e}")
        return

    if not unsent:
        print("[DONE] 발송 대기 중인 승인 건 없음")
        return

    print(f"[QUEUE] 발송 대기: {len(unsent)}명")

    sender = DMSender()
    await sender.start()

    try:
        if not await sender.is_logged_in():
            print("[ERROR] Playwright 세션 만료 — login_manual.py로 재로그인 필요")
            return

        sent_count = 0
        for c in unsent:
            if sent_count >= DAILY_SEND_LIMIT:
                print(f"\n[LIMIT] 일일 한도 {DAILY_SEND_LIMIT}통 도달")
                break

            username = c["username"]
            wait = random.randint(60, 180)
            print(f"\n[WAIT] {wait}초 대기 후 @{username} 발송...")
            await asyncio.sleep(wait)

            message = generate_dm(username)
            print(f"[DM] @{username} — {message[:40]}...")

            success = await sender.send_dm(username, message)
            if success:
                sent_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet_update_sent(c["row_number"], sent_date)
                sent_count += 1
                print(f"  ✅ 발송 완료 ({sent_count}/{DAILY_SEND_LIMIT})")
            else:
                print(f"  ❌ 발송 실패")

    finally:
        await sender.stop()

    print(f"\n{'='*60}")
    print(f"[SEND 완료] 발송 성공: {sent_count}통")
    print(f"{'='*60}")


def cmd_send():
    asyncio.run(_send_dms())


# ── 서브커맨드: check ────────────────────────────────────────────

def cmd_check():
    print(f"{'='*60}")
    print(f"[CHECK] DM 답장 확인 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print()
    print("인스타그램 DM은 공식 API로 자동 확인이 불가합니다.")
    print()
    print("수동 확인 방법:")
    print("  1. 인스타그램 앱 → DM 수신함 확인")
    print("  2. 답장 받은 계정 → 구글 시트 I열을 'replied'로 변경")
    print()

    try:
        counts = sheet_get_status_counts()
        contacted = counts.get("contacted", 0)
        replied = counts.get("replied", 0)
        if contacted > 0:
            reply_rate = replied / contacted * 100
            print(f"  발송 완료: {contacted}명 | 답장: {replied}명 | 답장률: {reply_rate:.1f}%")
    except Exception as e:
        print(f"[ERROR] 시트 조회 실패: {e}")


# ── 서브커맨드: status ───────────────────────────────────────────

STATUS_LABELS = {
    "screened": "스크리닝 완료 (승인 대기)",
    "contacted": "DM 발송 완료",
    "replied": "답장 수신",
}


def cmd_status():
    print(f"{'='*60}")
    print(f"[STATUS] 파이프라인 현황 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    try:
        counts = sheet_get_status_counts()
        total = sum(counts.values())
        print(f"\n총 {total}명 관리 중\n")
        for status, label in STATUS_LABELS.items():
            cnt = counts.get(status, 0)
            print(f"  {label}: {cnt}명")
        others = {k: v for k, v in counts.items() if k not in STATUS_LABELS}
        for k, v in others.items():
            print(f"  {k}: {v}명")
    except Exception as e:
        print(f"[ERROR] 시트 조회 실패: {e}")


# ── 진입점 ───────────────────────────────────────────────────────

COMMANDS = {
    "crawl": cmd_crawl,
    "send": cmd_send,
    "check": cmd_check,
    "status": cmd_status,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("사용법: python pipeline.py [crawl|send|check|status]")
        sys.exit(1)
    init_db()
    COMMANDS[sys.argv[1]]()
