"""채널톡 전체 상담 히스토리 다운로드"""
import requests
import json
import time
import datetime
import os

API_BASE = "https://api.channel.io/open/v5"
HEADERS = {
    "x-access-key": "6a0554c104ba3b33e314",
    "x-access-secret": "2e28464ac91692df0fcb9dc269d56b2b",
    "Content-Type": "application/json",
}
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

def fetch_chats(state, limit=50):
    """상담 목록을 페이지네이션으로 전부 가져오기"""
    all_chats = []
    url = f"{API_BASE}/user-chats?state={state}&limit={limit}"
    page = 0
    while url:
        page += 1
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print(f"  [오류] 상담 목록 조회 실패: {resp.status_code}")
            break
        data = resp.json()
        chats = data.get("userChats", [])
        all_chats.extend(chats)
        next_cursor = data.get("next")
        if next_cursor and chats:
            url = f"{API_BASE}/user-chats?state={state}&limit={limit}&since={next_cursor}"
        else:
            url = None
        print(f"  페이지 {page}: {len(chats)}건 (누적 {len(all_chats)}건)")
        time.sleep(0.15)
    return all_chats


def fetch_messages(chat_id):
    """특정 상담의 메시지 전체 가져오기"""
    all_msgs = []
    url = f"{API_BASE}/user-chats/{chat_id}/messages?limit=50"
    while url:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            break
        data = resp.json()
        msgs = data.get("messages", [])
        all_msgs.extend(msgs)
        next_cursor = data.get("next")
        if next_cursor and msgs:
            url = f"{API_BASE}/user-chats/{chat_id}/messages?limit=50&since={next_cursor}"
        else:
            url = None
        time.sleep(0.1)
    return all_msgs


def ts_to_str(ts):
    if not ts:
        return "?"
    return datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")


def main():
    all_conversations = []

    for state in ["closed", "opened", "snoozed"]:
        print(f"\n[{state}] 상담 목록 가져오는 중...")
        chats = fetch_chats(state)
        print(f"  → {state} 상담 총 {len(chats)}건")

        for i, chat in enumerate(chats):
            chat_id = chat["id"]
            created = ts_to_str(chat.get("createdAt"))
            msgs = fetch_messages(chat_id)

            conversation = {
                "chat_id": chat_id,
                "state": state,
                "created_at": created,
                "closed_at": ts_to_str(chat.get("closedAt")),
                "messages": [],
            }

            for m in sorted(msgs, key=lambda x: x.get("createdAt", 0)):
                conversation["messages"].append({
                    "timestamp": ts_to_str(m.get("createdAt")),
                    "person_type": m.get("personType", "?"),
                    "text": m.get("plainText") or m.get("message") or "",
                    "has_file": bool(m.get("files")),
                })

            all_conversations.append(conversation)

            if (i + 1) % 20 == 0:
                print(f"  진행: {i+1}/{len(chats)} ({state})")

    out_path = os.path.join(OUTPUT_DIR, "all_chats.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_conversations, f, ensure_ascii=False, indent=2)

    total_msgs = sum(len(c["messages"]) for c in all_conversations)
    print(f"\n===== 완료 =====")
    print(f"총 상담: {len(all_conversations)}건")
    print(f"총 메시지: {total_msgs}건")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
