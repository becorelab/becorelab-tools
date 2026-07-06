#!/usr/bin/env python3
"""텔레그램 알림 (레나 봇 재사용 — Channel_lena/.env)"""
import os
import urllib.request
import urllib.parse
from pathlib import Path

ENV_PATH = Path.home() / "ClaudeAITeam" / "Channel_lena" / ".env"
BOSS_CHAT_ID = "8708718261"


def _token():
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def tg_send(text):
    token = _token()
    if not token:
        print("(텔레그램 토큰 없음 — 알림 스킵)", text[:80])
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": BOSS_CHAT_ID, "text": text[:3900]}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        print("텔레그램 발송 실패:", e)
        return False


if __name__ == "__main__":
    import sys
    tg_send(sys.argv[1] if len(sys.argv) > 1 else "[알리바바봇] 테스트 알림이에요!")
