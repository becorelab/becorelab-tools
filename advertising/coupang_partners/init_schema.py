"""Firestore 3개 컬렉션 핸드셰이크 테스트.
실행:  python init_schema.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from firestore_client import (
    init_firestore, upsert_candidate, get_candidate, update_candidate_status,
    append_thread_message, get_thread,
    add_to_ghost_queue, list_ghost_queue, resolve_ghost,
    db,
)
from config import (
    COLL_CANDIDATES, COLL_THREADS, COLL_GHOST_QUEUE,
    STATUS_DISCOVERED, STATUS_APPROVED,
)

TEST_CH = "_schema_test_channel"


def main():
    init_firestore()

    print("\n1️⃣  candidates upsert/update/get")
    upsert_candidate(TEST_CH, {
        "channel_name": "Schema Test",
        "subscribers": 50000,
        "email": "test@example.com",
        "niche": "test",
        "fit_score": 0,
        "matched_products": [],
    })
    got = get_candidate(TEST_CH)
    assert got and got["status"] == STATUS_DISCOVERED, f"candidate 생성 실패: {got}"
    update_candidate_status(TEST_CH, STATUS_APPROVED, {"note": "schema test"})
    got = get_candidate(TEST_CH)
    assert got["status"] == STATUS_APPROVED and len(got["events"]) == 1
    print(f"   ✅ {COLL_CANDIDATES}")

    print("\n2️⃣  threads append/get")
    append_thread_message(TEST_CH, {
        "direction": "outbound",
        "from": "marketing@becorelab.kr",
        "to": "test@example.com",
        "subject": "schema test",
        "body": "hi",
    })
    t = get_thread(TEST_CH)
    assert t and len(t["messages"]) == 1
    print(f"   ✅ {COLL_THREADS}")

    print("\n3️⃣  ghost_queue add/list/resolve")
    add_to_ghost_queue(TEST_CH, "no_reply_7d")
    pending = list_ghost_queue(resolved=False)
    assert any(g["channel_id"] == TEST_CH for g in pending)
    resolve_ghost(TEST_CH, "close")
    print(f"   ✅ {COLL_GHOST_QUEUE}")

    print("\n4️⃣  테스트 데이터 정리")
    db().collection(COLL_CANDIDATES).document(TEST_CH).delete()
    db().collection(COLL_THREADS).document(TEST_CH).delete()
    db().collection(COLL_GHOST_QUEUE).document(TEST_CH).delete()
    print("   ✅ cleanup 완료")

    print("\n🎉 Firestore 스키마 핸드셰이크 성공")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 실패: {e}", file=sys.stderr)
        sys.exit(1)
