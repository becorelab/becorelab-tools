"""유튜버 회신 감지 + 텔레그램 알림.

크론(또는 스케줄러)에서 run()을 호출하면:
  1. 네이버웍스 '유튜브 협찬 메일' 폴더의 미열람 메일 조회
  2. send_results.json의 발송 기록과 매칭 (In-Reply-To 헤더 또는 발신자 이메일)
  3. 매칭된 회신마다 텔레그램 알림 발송
  4. 처리한 메일 ID는 로컬 상태 파일에 저장하여 중복 알림 방지
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from naverworks_mail import fetch_unseen
from config import PARTNERS_INBOX_MAILBOX, BASE_DIR

# ── 경로 ──────────────────────────────────────────────────────────
SEND_RESULTS_PATH = str(BASE_DIR / "send_results.json")
REPLY_SEEN_PATH = str(BASE_DIR / "credentials" / "reply_seen.json")
LENA_ENV_PATH = "/Users/macmini_ky/ClaudeAITeam/Channel_lena/.env"


# ── 텔레그램 자격증명 ────────────────────────────────────────────
def _load_telegram_config() -> dict:
    """Channel_lena .env에서 TELEGRAM_BOT_TOKEN, CHAT_ID 로드."""
    config = {}
    with open(LENA_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    token = config.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = config.get("CHAT_ID", "")
    if not token or not chat_id:
        raise ValueError(f"TELEGRAM_BOT_TOKEN 또는 CHAT_ID가 {LENA_ENV_PATH}에 없음")
    return {"token": token, "chat_id": chat_id}


# ── 발송 기록 로드 ───────────────────────────────────────────────
def _load_send_results() -> list[dict]:
    if not os.path.exists(SEND_RESULTS_PATH):
        return []
    with open(SEND_RESULTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 중복 방지 상태 ───────────────────────────────────────────────
def _load_reply_seen() -> set:
    if not os.path.exists(REPLY_SEEN_PATH):
        return set()
    try:
        with open(REPLY_SEEN_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f).get("message_ids", []))
    except Exception:
        return set()


def _save_reply_seen(seen: set):
    os.makedirs(os.path.dirname(REPLY_SEEN_PATH), exist_ok=True)
    with open(REPLY_SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "message_ids": sorted(seen),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, f, ensure_ascii=False, indent=2)


# ── 핵심 함수 ────────────────────────────────────────────────────
def check_replies() -> list[dict]:
    """미열람 메일을 조회하고, 발송 기록과 매칭된 회신 목록 반환.

    매칭 기준:
      1순위: In-Reply-To 헤더가 send_results의 message_id와 일치
      2순위: 발신자 이메일이 send_results의 to와 일치
    """
    send_results = _load_send_results()
    if not send_results:
        return []

    # 인덱스 구축
    by_msg_id = {}   # message_id -> send record
    by_email = {}    # to(email) -> send record
    for rec in send_results:
        mid = (rec.get("message_id") or "").strip()
        if mid:
            by_msg_id[mid] = rec
        addr = (rec.get("to") or "").strip().lower()
        if addr:
            by_email[addr] = rec

    seen = _load_reply_seen()
    msgs = fetch_unseen(mailbox=PARTNERS_INBOX_MAILBOX)
    matched = []

    for m in msgs:
        mail_id = (m.get("message_id") or "").strip()
        if not mail_id or mail_id in seen:
            continue

        # 매칭 시도
        irt = (m.get("in_reply_to") or "").strip()
        rec = by_msg_id.get(irt) if irt else None

        if rec is None:
            sender = (m.get("from") or "").strip().lower()
            rec = by_email.get(sender)

        if rec is not None:
            matched.append({
                "message_id": mail_id,
                "youtuber_name": rec.get("name", "알 수 없음"),
                "youtuber_email": rec.get("to", ""),
                "subject": m.get("subject", ""),
                "body": m.get("body", ""),
                "received_at": m.get("received_at", ""),
                "matched_by": "in_reply_to" if irt and irt in by_msg_id else "sender_email",
            })
            seen.add(mail_id)

    _save_reply_seen(seen)
    return matched


def notify_telegram(youtuber_name: str, reply_preview: str) -> bool:
    """텔레그램으로 유튜버 회신 알림 발송. 성공 시 True."""
    try:
        tg = _load_telegram_config()
    except Exception as e:
        print(f"[reply_checker] 텔레그램 설정 로드 실패: {e}", file=sys.stderr)
        return False

    preview = reply_preview[:200].strip()
    if len(reply_preview) > 200:
        preview += "..."

    text = (
        f"\U0001f4ec 유튜버 회신 도착!\n"
        f"\n"
        f"채널: {youtuber_name}\n"
        f"내용: {preview}\n"
        f"\n"
        f"네이버웍스 메일함에서 확인해주세요!"
    )

    url = f"https://api.telegram.org/bot{tg['token']}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": tg["chat_id"],
            "text": text,
        }, timeout=15)
        if resp.status_code == 200 and resp.json().get("ok"):
            return True
        print(f"[reply_checker] 텔레그램 API 응답 이상: {resp.status_code} {resp.text}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[reply_checker] 텔레그램 발송 실패: {e}", file=sys.stderr)
        return False


def run() -> int:
    """메인 루틴: 회신 확인 → 텔레그램 알림 → 신규 회신 수 반환."""
    replies = check_replies()
    count = 0
    for r in replies:
        ok = notify_telegram(r["youtuber_name"], r["body"])
        if ok:
            count += 1
            print(f"[reply_checker] 알림 완료: {r['youtuber_name']} ({r['matched_by']})")
        else:
            print(f"[reply_checker] 알림 실패: {r['youtuber_name']}", file=sys.stderr)
    if not replies:
        print("[reply_checker] 신규 회신 없음")
    return count


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    n = run()
    print(f"\n총 {n}건 알림 발송 완료")
