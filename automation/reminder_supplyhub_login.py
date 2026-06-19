#!/usr/bin/env python3
"""퇴근 전(18:30) 서플라이허브 로그인 리마인더 → 대표님 텔레그램 발송.
세션 idle 만료 실험용: 퇴근 때 로그인하면 다음날 아침 크론까지 세션이 더 오래 가는지 검증.
의존성 0 (표준 urllib만) — 어떤 python3에서도 동작."""
import json
import os
import urllib.request
from pathlib import Path

HERMES_ENV = Path(os.path.expanduser("~")) / ".hermes" / ".env"
OWNER_CHAT_ID = 8708718261  # 대표님 (루나 봇 TELEGRAM_ALLOWED_USERS 와 동일)


def _get_token():
    for line in HERMES_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("TELEGRAM_BOT_TOKEN 없음")

MSG = (
    "🐣 대표님~ 퇴근 시간이에요! 마무리 전에 한 가지만요 💕\n\n"
    "🔐 서플라이허브 로그인 한 번 해주세요!\n"
    "(다음날 아침 로켓 크론이 세션 끊김 없이 자동으로 돌게 — idle 만료 실험 중)\n\n"
    "터미널에 붙여넣기:\n"
    "python3 ~/ClaudeAITeam/automation/supplyhub_relogin.py\n\n"
    "크롬 뜨면 becorelab 로그인만 하시면 끝! 오늘도 고생 많으셨어요 🥰"
)


def main():
    token = _get_token()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": OWNER_CHAT_ID, "text": MSG}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        print("발송 결과:", resp.status, resp.read().decode("utf-8")[:200])


if __name__ == "__main__":
    main()
