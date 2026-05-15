"""인스타 공동구매 파이프라인 — 중앙 오케스트레이터.

Windows Task Scheduler에서 서브커맨드별 호출:
  python pipeline.py crawl    — 인스타 해시태그 크롤 + Haiku 스크리닝 + 구글 시트 추가
  python pipeline.py send     — 승인된 후보에게 DM 발송 (Playwright)
  python pipeline.py status   — 파이프라인 현황 요약
"""
import sys
import os
import argparse
import asyncio
import json
import random
import time
from datetime import datetime, timezone

# ── 경로 설정 ────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(os.path.join(_DIR, ".env"))
load_dotenv(os.path.join(_DIR, "..", "..", "sourcing", "analyzer", ".env"))

# ── 내부 모듈 ────────────────────────────────────────────────
from config import (
    KEY_PATH, SHEET_ID, SHEET_NAME,
    DAILY_SEND_MIN, DAILY_SEND_MAX,
    SEND_START_HOUR, SEND_END_HOUR,
    STATUS_SCREENED, STATUS_APPROVED, STATUS_CONTACTED,
)
from crawler import InstaCrawler
from screener import screen_account
from templates import generate_dm
from dm_sender import DMSender, get_dm_count_today

# ── 구글 시트 설정 ───────────────────────────────────────────
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

COL = {
    "username": 0,       # A
    "프로필URL": 1,       # B
    "팔로워": 2,          # C
    "참여율": 3,          # D
    "카테고리": 4,        # E
    "공구경험": 5,        # F
    "이메일": 6,          # G
    "적합도": 7,          # H
    "상태": 8,            # I
    "승인": 9,            # J
    "개인화훅": 10,       # K
    "비고": 11,           # L
    "발견일": 12,         # M
}

HEADER_LABELS = list(COL.keys())

_gc = None


def _sheets_client():
    global _gc
    if _gc is None:
        creds = Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
        _gc = gspread.authorize(creds)
    return _gc


def _get_sheet():
    gc = _sheets_client()
    sh = gc.open_by_key(SHEET_ID)
    try:
        return sh.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=500, cols=len(HEADER_LABELS))
        ws.update(values=[HEADER_LABELS], range_name=f"A1:{chr(65 + len(HEADER_LABELS) - 1)}1")
        return ws


# ── 시트 유틸 ────────────────────────────────────────────────

def sheet_get_existing_usernames() -> set:
    ws = _get_sheet()
    col_values = ws.col_values(COL["username"] + 1)
    return set(col_values[1:])


def _build_memo(account: dict, screen: dict) -> str:
    """비고란 텍스트 조합: 선정이유 + fake_flags + 외국인 비율."""
    parts = []
    rationale = screen.get("rationale", "")
    if rationale:
        parts.append(rationale)
    flags = account.get("fake_flags", [])
    if flags:
        parts.append(f"⚠ {', '.join(flags)}")
    fc = account.get("foreign_check", {})
    if fc.get("checked") and fc.get("foreign_ratio") is not None:
        parts.append(f"외국인 {fc['foreign_ratio']:.0%}")
    return " | ".join(parts)


def sheet_append_candidates(candidates: list[dict]):
    if not candidates:
        return
    ws = _get_sheet()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    rows = []
    for c in candidates:
        screen = c.get("screen", {})
        rows.append([
            c.get("username", ""),                                    # A username
            c.get("profile_url", ""),                                 # B 프로필URL
            c.get("followers", 0),                                    # C 팔로워
            f"{c.get('engagement_rate', 0):.1%}",                     # D 참여율
            screen.get("category", ""),                               # E 카테고리
            "O" if c.get("has_gonggu_experience") else "",            # F 공구경험
            c.get("email", ""),                                       # G 이메일
            screen.get("match_score", 0),                             # H 적합도
            STATUS_SCREENED,                                          # I 상태
            "",                                                       # J 승인
            screen.get("personal_hook", ""),                          # K 개인화훅
            _build_memo(c, screen),                                    # L 비고
            now_str,                                                  # M 발견일
        ])
    ws.append_rows(rows, value_input_option="USER_ENTERED")


def sheet_get_approved_unsent() -> list[dict]:
    ws = _get_sheet()
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return []
    results = []
    for i, row in enumerate(all_rows[1:], start=2):
        if len(row) < 10 or not row[0]:
            continue
        padded = row + [""] * (len(HEADER_LABELS) - len(row))
        approval = padded[COL["승인"]].strip()
        status = padded[COL["상태"]].strip()
        if approval in ("승인", "approved") and status not in (
            STATUS_CONTACTED, "replied", "negotiating", "gonggu_confirmed", "declined"
        ):
            results.append({
                "row_number": i,
                "username": padded[COL["username"]],
                "email": padded[COL["이메일"]],
                "personal_hook": padded[COL["개인화훅"]],
                "category": padded[COL["카테고리"]],
            })
    return results


def sheet_update_sent(row_number: int):
    ws = _get_sheet()
    col_status = COL["상태"] + 1
    ws.update_cell(row_number, col_status, STATUS_CONTACTED)
    col_memo = COL["비고"] + 1
    sent_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    ws.update_cell(row_number, col_memo, f"DM발송 {sent_date}")


def sheet_get_status_counts() -> dict:
    ws = _get_sheet()
    all_rows = ws.get_all_values()
    status_counts = {}
    approval_counts = {}
    for row in all_rows[1:]:
        if not row or not row[0]:
            continue
        padded = row + [""] * (len(HEADER_LABELS) - len(row))
        status = (padded[COL["상태"]] or STATUS_SCREENED).strip()
        status_counts[status] = status_counts.get(status, 0) + 1
        approval = (padded[COL["승인"]] or "미검토").strip()
        approval_counts[approval] = approval_counts.get(approval, 0) + 1
    return {"status": status_counts, "approval": approval_counts}


# ── 서브커맨드: crawl ────────────────────────────────────────

def cmd_crawl():
    """인스타 해시태그 크롤 + Haiku 스크리닝 + 구글 시트 추가."""
    print(f"{'='*60}")
    print(f"[CRAWL] 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    # 1) 기존 시트의 username 로드 (중복 방지)
    try:
        existing = sheet_get_existing_usernames()
        print(f"[DEDUP] 시트에 기존 계정 {len(existing)}개")
    except Exception as e:
        print(f"[WARN] 시트 읽기 실패, 중복 체크 스킵: {e}")
        existing = set()

    # 2) 크롤링
    crawler = InstaCrawler()
    if not crawler.login():
        print("[ERROR] instagrapi 로그인 실패")
        return

    raw_accounts = crawler.crawl_hashtags()

    # 중복 제거
    new_accounts = [a for a in raw_accounts if a["username"] not in existing]
    print(f"[FILTER] 신규 {len(new_accounts)}명 (기존 제외)")

    if not new_accounts:
        print("[DONE] 새로운 후보 없음")
        return

    # 3) Haiku 스크리닝
    qualified = []
    for i, account in enumerate(new_accounts, 1):
        print(f"\n[SCREEN] ({i}/{len(new_accounts)}) @{account['username']}")
        try:
            screen_result = screen_account(account)
            account["screen"] = screen_result
            verdict = screen_result.get("verdict", "maybe")
            score = screen_result.get("match_score", 0)
            print(f"  -> score={score}, verdict={verdict}")

            if verdict != "rejected":
                qualified.append(account)
        except Exception as e:
            print(f"  [WARN] 스크리닝 실패: {e}")
            account["screen"] = {
                "match_score": 50,
                "category": "기타",
                "rationale": f"스크리닝 오류: {e}",
                "verdict": "maybe",
            }
            qualified.append(account)

    # 4) 외국인 팔로워 체크 (Haiku 통과 후보만 — API 부하 절감)
    if qualified:
        print(f"\n[FOREIGN] 외국인 팔로워 체크 ({len(qualified)}명 대상)")
        final = []
        for account in qualified:
            user_id = account.get("user_id", "")
            username = account["username"]
            result = crawler.check_foreign_followers(user_id)

            if result["checked"] and result["is_suspicious"]:
                ratio = result["foreign_ratio"]
                account.setdefault("fake_flags", []).append(
                    f"외국인팔로워 {ratio:.0%}"
                )
                # 기존 fake_flags와 합쳐서 2개 이상이면 컷
                if len(account.get("fake_flags", [])) >= 2:
                    print(f"  ✗ @{username} 가짜 의심 SKIP: {', '.join(account['fake_flags'])}")
                    continue
                else:
                    print(f"  ⚠ @{username} 외국인 {ratio:.0%} (플래그 1개, 통과)")

            account["foreign_check"] = result
            final.append(account)

        qualified = final
        print(f"[FOREIGN] 최종 {len(qualified)}명 통과")

    # 5) 시트에 추가
    if qualified:
        try:
            sheet_append_candidates(qualified)
            print(f"\n[SHEET] {len(qualified)}개 후보 시트에 추가 완료")
        except Exception as e:
            print(f"\n[ERROR] 시트 추가 실패: {e}")
            backup_path = os.path.join(_DIR, "crawl_backup.json")
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(qualified, f, ensure_ascii=False, indent=2, default=str)
            print(f"  로컬 백업: {backup_path}")

    print(f"\n{'='*60}")
    print(f"[CRAWL 완료] 발견: {len(raw_accounts)} | 신규: {len(new_accounts)} | 적격: {len(qualified)}")
    print(f"{'='*60}")


# ── 서브커맨드: send ─────────────────────────────────────────

def cmd_send():
    """승인된 후보에게 DM 발송."""
    now = datetime.now()
    hour = now.hour

    if not (SEND_START_HOUR <= hour < SEND_END_HOUR):
        print(f"[SKIP] 운영 시간 외 (현재 {hour}시, 운영: {SEND_START_HOUR}~{SEND_END_HOUR}시)")
        return

    daily_limit = random.randint(DAILY_SEND_MIN, DAILY_SEND_MAX)

    print(f"{'='*60}")
    print(f"[SEND] 시작 — {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"오늘 한도: {daily_limit}통 | 이미 발송: {get_dm_count_today()}통")
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

    # DM 메시지 생성
    targets = []
    for c in unsent:
        msg = generate_dm(c["username"], c.get("personal_hook", ""))
        targets.append({
            "username": c["username"],
            "message": msg,
            "row_number": c["row_number"],
        })

    # Playwright 발송
    async def _run():
        sender = DMSender()
        await sender.start()
        try:
            if not await sender.is_logged_in():
                print("[ERROR] Playwright 세션 만료 — login_manual.py로 다시 로그인해주세요")
                return

            sent_count = 0
            failed_count = 0
            consecutive_failures = 0

            for target in targets:
                if sent_count + get_dm_count_today() >= daily_limit:
                    print(f"\n[LIMIT] 오늘 한도 {daily_limit}통 도달")
                    break

                if consecutive_failures >= 3:
                    print(f"\n[WARN] 연속 실패 {consecutive_failures}회 — 차단 의심, 중단")
                    break

                # 자연 행동 삽입 (30% 확률)
                if random.random() < 0.3 and sent_count > 0:
                    from dm_sender import _natural_behavior
                    print("  [행동] 자연 행동 삽입...")
                    await _natural_behavior(sender.page)

                # 가우시안 대기
                from dm_sender import next_interval
                wait = next_interval()
                print(f"\n⏳ {wait:.0f}초 대기 후 @{target['username']}에게 발송...")
                await asyncio.sleep(wait)

                success = await sender.send_dm(target["username"], target["message"])

                if success:
                    sent_count += 1
                    consecutive_failures = 0
                    try:
                        sheet_update_sent(target["row_number"])
                    except Exception as e:
                        print(f"  [WARN] 시트 업데이트 실패: {e}")
                else:
                    failed_count += 1
                    consecutive_failures += 1

            print(f"\n{'='*60}")
            print(f"[SEND 완료] 발송: {sent_count} | 실패: {failed_count}")
            print(f"오늘 총 발송: {get_dm_count_today()}통")
            print(f"{'='*60}")

        finally:
            await sender.stop()

    asyncio.run(_run())


# ── 서브커맨드: status ───────────────────────────────────────

def cmd_status():
    """파이프라인 현황 요약."""
    print(f"{'='*60}")
    print(f"[STATUS] 인스타 공동구매 파이프라인")
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
    status_order = [
        "screened", "contacted", "replied",
        "negotiating", "gonggu_confirmed", "declined",
    ]
    status_labels = {
        "screened": "스크리닝 완료",
        "contacted": "DM 발송 완료",
        "replied": "답장 수신",
        "negotiating": "협상 중",
        "gonggu_confirmed": "공구 확정",
        "declined": "거절",
    }
    for s in status_order:
        cnt = status_counts.get(s, 0)
        if cnt > 0:
            print(f"  {status_labels.get(s, s)}: {cnt}명")
    for s, cnt in status_counts.items():
        if s not in status_order and cnt > 0:
            print(f"  {s}: {cnt}명")

    print(f"\n[승인 현황]")
    for k, v in sorted(approval_counts.items()):
        print(f"  {k}: {v}명")

    # DM 로그
    dm_today = get_dm_count_today()
    print(f"\n[오늘 DM] {dm_today}통 발송")

    print(f"\n{'='*60}")


# ── argparse ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="인스타 공동구매 파이프라인",
    )
    sub = parser.add_subparsers(dest="command", help="실행할 커맨드")
    sub.required = True

    sub.add_parser("crawl", help="인스타 해시태그 크롤 + Haiku 스크리닝 + 시트 추가")
    sub.add_parser("send", help="승인된 후보에게 DM 발송")
    sub.add_parser("status", help="파이프라인 현황 요약")

    args = parser.parse_args()

    commands = {
        "crawl": cmd_crawl,
        "send": cmd_send,
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
