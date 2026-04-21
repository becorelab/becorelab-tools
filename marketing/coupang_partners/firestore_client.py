"""쿠팡 파트너스 파이프라인 — Firestore 접근 레이어

컬렉션 (PRD §7):
  coupang_partners_candidates    — 유튜버 후보 (channel_id = doc id)
  coupang_partners_threads       — 이메일 스레드 (thread_id = doc id, events 배열)
  coupang_partners_ghost_queue   — 잠수 대기함 (channel_id = doc id)

Firebase 서비스 계정 키는 sourcing/analyzer/ 에 있는 becorelab-tools 키 재사용.
"""
import os
from datetime import datetime, timezone
from typing import Optional
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import firebase_admin
from firebase_admin import credentials

from config import (
    COLL_CANDIDATES, COLL_THREADS, COLL_GHOST_QUEUE,
    STATUS_DISCOVERED,
)

_db: Optional[firestore.Client] = None

_KEY_SEARCH_DIRS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials"),
    r"C:\Users\User\ClaudeAITeam\sourcing\analyzer",
]


def _find_key_path() -> str:
    for d in _KEY_SEARCH_DIRS:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".json") and "firebase-adminsdk" in f:
                return os.path.join(d, f)
    raise FileNotFoundError(
        "Firebase 서비스 계정 키 없음. coupang_partners/credentials/ 또는 "
        "sourcing/analyzer/ 에 *firebase-adminsdk*.json 배치 필요."
    )


def init_firestore() -> firestore.Client:
    global _db
    if _db is not None:
        return _db
    key_path = _find_key_path()
    cred = credentials.Certificate(key_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    _db = firestore.Client.from_service_account_json(key_path)
    print(f"[FIRESTORE] 연결: {_db.project}")
    return _db


def db() -> firestore.Client:
    return _db or init_firestore()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── coupang_partners_candidates ──────────────────────────────
def upsert_candidate(channel_id: str, data: dict) -> dict:
    """후보 생성/업데이트. channel_id가 primary key."""
    ref = db().collection(COLL_CANDIDATES).document(channel_id)
    snap = ref.get()
    now = _now_iso()
    if snap.exists:
        payload = {**data, "last_event_at": now}
        ref.update(payload)
    else:
        payload = {
            "channel_id": channel_id,
            "status": STATUS_DISCOVERED,
            "events": [],
            "revenue_tracked": 0,
            "created_at": now,
            "last_event_at": now,
            **data,
        }
        ref.set(payload)
    return ref.get().to_dict()


def get_candidate(channel_id: str) -> Optional[dict]:
    snap = db().collection(COLL_CANDIDATES).document(channel_id).get()
    return snap.to_dict() if snap.exists else None


def update_candidate_status(channel_id: str, status: str, detail: Optional[dict] = None):
    """상태 변경 + events 배열에 로그 append."""
    ref = db().collection(COLL_CANDIDATES).document(channel_id)
    now = _now_iso()
    event = {"type": status, "at": now, "detail": detail or {}}
    ref.update({
        "status": status,
        "last_event_at": now,
        "events": firestore.ArrayUnion([event]),
    })


def list_candidates_by_status(status: str, limit: int = 500) -> list[dict]:
    q = (db().collection(COLL_CANDIDATES)
         .where(filter=FieldFilter("status", "==", status))
         .limit(limit))
    return [doc.to_dict() for doc in q.stream()]


# ── coupang_partners_threads ─────────────────────────────────
def append_thread_message(thread_id: str, message: dict):
    """이메일 스레드에 메시지 append. message = {direction, from, to, subject, body, at}"""
    ref = db().collection(COLL_THREADS).document(thread_id)
    snap = ref.get()
    now = _now_iso()
    msg = {**message, "at": message.get("at") or now}
    if snap.exists:
        ref.update({
            "messages": firestore.ArrayUnion([msg]),
            "last_message_at": now,
        })
    else:
        ref.set({
            "thread_id": thread_id,
            "messages": [msg],
            "created_at": now,
            "last_message_at": now,
        })


def get_thread(thread_id: str) -> Optional[dict]:
    snap = db().collection(COLL_THREADS).document(thread_id).get()
    return snap.to_dict() if snap.exists else None


# ── coupang_partners_ghost_queue ─────────────────────────────
def add_to_ghost_queue(channel_id: str, reason: str, detail: Optional[dict] = None):
    ref = db().collection(COLL_GHOST_QUEUE).document(channel_id)
    ref.set({
        "channel_id": channel_id,
        "reason": reason,
        "detail": detail or {},
        "added_at": _now_iso(),
        "resolved": False,
    }, merge=True)


def list_ghost_queue(resolved: bool = False) -> list[dict]:
    q = (db().collection(COLL_GHOST_QUEUE)
         .where(filter=FieldFilter("resolved", "==", resolved)))
    return [doc.to_dict() for doc in q.stream()]


def resolve_ghost(channel_id: str, action: str):
    """action: 'continue' | 'close' | 'blacklist'"""
    ref = db().collection(COLL_GHOST_QUEUE).document(channel_id)
    ref.update({
        "resolved": True,
        "resolution": action,
        "resolved_at": _now_iso(),
    })
