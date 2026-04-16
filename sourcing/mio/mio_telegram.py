"""
미오 텔레그램 알림 모듈
대표님께 메시지 보내고, 대표님 답장 받기 (long polling)
"""
import os
import httpx
from pathlib import Path

TOKEN_FILE = Path(os.path.expanduser("~")) / ".claude" / "mio_telegram_token.txt"
OWNER_CHAT_ID = 8708718261  # 대표님 chat_id

_token_cache = None


def _get_token():
    global _token_cache
    if _token_cache:
        return _token_cache
    if not TOKEN_FILE.exists():
        raise RuntimeError(f"텔레그램 토큰 파일 없음: {TOKEN_FILE}")
    _token_cache = TOKEN_FILE.read_text(encoding="utf-8").strip()
    return _token_cache


def send_message(text: str, chat_id: int = OWNER_CHAT_ID, parse_mode: str = None) -> dict:
    """대표님 (또는 지정 chat_id) 에게 텔레그램 메시지 발송"""
    token = _get_token()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        resp = httpx.post(url, json=payload, timeout=10)
        data = resp.json()
        return {"success": data.get("ok", False), "response": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_love(text: str, chat_id: int = OWNER_CHAT_ID) -> dict:
    """대표님께 애정 가득한 일반 메시지 (에스컬레이션 아닌 일반 소통용)"""
    return send_message(text, chat_id)


def get_updates(offset: int = None, timeout: int = 2) -> list:
    """대표님 답장 가져오기 (long polling)"""
    token = _get_token()
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    try:
        resp = httpx.get(url, params=params, timeout=timeout + 5)
        data = resp.json()
        return data.get("result", []) if data.get("ok") else []
    except Exception:
        return []


def wait_for_reply(timeout_seconds: int = 300) -> dict | None:
    """
    대표님 답장 대기 (최대 timeout_seconds 초)
    반환: {"text": "...", "message_id": ..., "timestamp": ...} 또는 None
    """
    import time
    start = time.time()
    last_update_id = None

    # 현재 시점 이후의 메시지만 받기 위해 한 번 읽어서 offset 설정
    initial = get_updates(timeout=1)
    if initial:
        last_update_id = initial[-1]["update_id"]

    while time.time() - start < timeout_seconds:
        updates = get_updates(offset=(last_update_id + 1) if last_update_id else None, timeout=2)
        for update in updates:
            last_update_id = update["update_id"]
            msg = update.get("message", {})
            if msg.get("chat", {}).get("id") == OWNER_CHAT_ID and msg.get("text"):
                return {
                    "text": msg["text"],
                    "message_id": msg["message_id"],
                    "timestamp": msg.get("date"),
                }
        time.sleep(1)
    return None
