"""쿠팡 파트너스 답장 수신 폴러.

주기: 10분 (스케줄러는 별도 — Task Scheduler 또는 cron에서 호출)
동작:
  1. 네이버웍스 '유튜브 협찬 메일' 폴더의 미열람 메일 조회
  2. In-Reply-To 헤더로 Firestore thread 매칭
  3. 매칭된 스레드에 inbound 메시지 append
  4. 매칭 실패 시 orphan_inbox 스레드에 저장 (수동 확인)

본 스크립트는 메일 "읽음" 표시를 하지 않는다 (웹메일에서 대표님이 확인 가능).
대신 로컬 상태 파일에 처리한 Message-ID 를 누적하여 중복 append 방지.
"""
import os
import sys
import json
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from naverworks_mail import fetch_unseen
from firestore_client import (
    get_thread, append_thread_message, db, init_firestore,
)
from config import (
    PARTNERS_INBOX_MAILBOX, BASE_DIR, COLL_THREADS,
)

SEEN_STATE_PATH = str(BASE_DIR / "credentials" / "inbox_seen.json")


def _load_seen() -> set:
    if not os.path.exists(SEEN_STATE_PATH):
        return set()
    try:
        with open(SEEN_STATE_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f).get("message_ids", []))
    except Exception:
        return set()


def _save_seen(seen: set):
    os.makedirs(os.path.dirname(SEEN_STATE_PATH), exist_ok=True)
    with open(SEEN_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "message_ids": sorted(seen),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, f, ensure_ascii=False, indent=2)


def _find_thread_by_message_id(original_msg_id: str) -> str:
    """outbound messages.message_id 기준으로 스레드 찾기."""
    if not original_msg_id:
        return ""
    # Firestore는 array 내부 필드 검색에 collection group query 필요.
    # MVP: 모든 threads 순회 (초기엔 스레드 수 적어서 OK).
    for snap in db().collection(COLL_THREADS).stream():
        data = snap.to_dict() or {}
        for m in data.get("messages") or []:
            if m.get("message_id") == original_msg_id:
                return data.get("thread_id") or snap.id
    return ""


def poll_once() -> dict:
    init_firestore()
    seen = _load_seen()
    matched = 0
    orphan = 0
    skipped = 0

    msgs = fetch_unseen(mailbox=PARTNERS_INBOX_MAILBOX)
    for m in msgs:
        mid = (m.get("message_id") or "").strip()
        if not mid or mid in seen:
            skipped += 1
            continue

        irt = (m.get("in_reply_to") or "").strip()
        thread_id = _find_thread_by_message_id(irt)

        payload = {
            "direction": "inbound",
            "message_id": mid,
            "in_reply_to": irt,
            "references": m.get("references") or "",
            "from": m.get("from") or "",
            "from_name": m.get("from_name") or "",
            "subject": m.get("subject") or "",
            "body": m.get("body") or "",
            "received_at": m.get("received_at") or "",
        }

        if thread_id:
            append_thread_message(thread_id, payload)
            matched += 1
        else:
            # orphan: In-Reply-To가 없거나 매칭 실패
            append_thread_message("orphan_inbox", {
                **payload,
                "reason": "no in_reply_to match",
            })
            orphan += 1

        seen.add(mid)

    _save_seen(seen)
    return {
        "fetched": len(msgs),
        "matched": matched,
        "orphan": orphan,
        "skipped_already_seen": skipped,
        "mailbox": PARTNERS_INBOX_MAILBOX,
        "at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    result = poll_once()
    print(json.dumps(result, ensure_ascii=False, indent=2))
