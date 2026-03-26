#!/usr/bin/env python3
"""
두리 아침 보고 - Windows 작업 스케줄러용
Claude Code 세션과 무관하게 매일 05:30 실행
"""

import urllib.request
import urllib.parse
import json
import sys
import traceback

TELEGRAM_BOT_TOKEN = "8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"
CHAT_ID = "8708718261"
LOGISTICS_BASE = "http://localhost:8082"


def fetch_text(url, timeout=30):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return raw.decode("utf-8")
            except Exception:
                return raw.decode("cp949", errors="replace")
    except Exception as e:
        return f"[오류] {e}"


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": ""
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main():
    # 매출 보고
    sales = fetch_text(f"{LOGISTICS_BASE}/api/daily-report?format=text")
    # 재고 보고
    inventory = fetch_text(f"{LOGISTICS_BASE}/api/inventory-report?format=text")

    msg = "대표님~! 두리예요 💕 아침 보고 드릴게요!\n\n"
    msg += "📊 매출 현황\n"
    msg += sales.strip() + "\n\n"
    msg += "📦 재고 현황\n"
    msg += inventory.strip()

    # 너무 길면 자르기 (Telegram 4096자 제한)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n...(생략)"

    result = send_telegram(msg)
    if result.get("ok"):
        sys.stdout.buffer.write("OK: morning report sent\n".encode())
    else:
        sys.stdout.buffer.write(f"FAIL: {result}\n".encode())
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # 에러도 텔레그램으로 알림
        err = traceback.format_exc()
        try:
            send_telegram(f"두리 아침 보고 오류 발생 😢\n\n{err[:500]}")
        except Exception:
            pass
        sys.exit(1)
