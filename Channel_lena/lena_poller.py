"""
레나 알리바바 인박스 폴러
- 5분 주기로 알리바바 인박스 raw text 가져옴
- 이전 상태와 비교해서 새 메시지 신호 감지
- 새 메시지면 레나 봇으로 대표님께 텔레그램 알림
- 비정형 상황 감지는 레나 채널 세션이 받아서 판단함 (poller는 알림만)
"""

import sys
import os
import json
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

LENA_DIR = Path(r"C:\Users\info\ClaudeAITeam\Channel_lena")
STATE_FILE = LENA_DIR / "poller_state.json"
LOG_FILE = LENA_DIR / "poller.log"

LENA_BOT_TOKEN = "8663458998:AAEEnXYWJhq98o2PfoBuqVxbe7JOUvJZYxc"
BOSS_CHAT_ID = "8708718261"

MIO_DIR = r"C:\Users\info\ClaudeAITeam\sourcing\mio"
sys.path.insert(0, MIO_DIR)
sys.path.insert(0, r"C:\Users\info\ClaudeAITeam\sourcing")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{LENA_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": BOSS_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return bool(result.get("ok"))
    except Exception as e:
        log(f"텔레그램 전송 실패: {e}")
        return False


def cdp_health_check() -> bool:
    """Chrome CDP가 살아있는지 확인"""
    try:
        with urllib.request.urlopen("http://localhost:9222/json/version", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_hash": "", "last_check": "", "last_excerpt": "", "alert_count_today": 0, "alert_date": ""}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    log("=== 레나 폴러 시작 ===")

    if not cdp_health_check():
        msg = "⚠️ Chrome CDP(포트 9222)가 응답하지 않아요. 알리바바 폴링 불가."
        log(msg)
        send_telegram(f"[레나 폴러] {msg}")
        return 1

    try:
        from tools import alibaba_check_inbox
    except Exception as e:
        log(f"tools import 실패: {e}")
        send_telegram(f"[레나 폴러] tools 모듈 import 실패: {e}")
        return 2

    log("알리바바 인박스 체크 중...")
    result = alibaba_check_inbox()

    if not result.get("success"):
        err = result.get("error", "unknown")
        log(f"인박스 체크 실패: {err}")
        send_telegram(f"[레나 폴러] 인박스 체크 실패: {err}")
        return 3

    raw_text = result.get("raw_text", "")
    text_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    state = load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("alert_date") != today:
        state["alert_count_today"] = 0
        state["alert_date"] = today

    state["last_check"] = datetime.now().isoformat()

    if text_hash != state.get("last_hash"):
        log(f"새 메시지 감지! hash {state.get('last_hash', '')[:8]} → {text_hash[:8]}")
        state["last_hash"] = text_hash
        state["last_excerpt"] = raw_text[:300]
        state["alert_count_today"] = state.get("alert_count_today", 0) + 1

        excerpt = raw_text[:500].replace("<", "&lt;").replace(">", "&gt;")
        msg = (
            f"📬 <b>[레나] 알리바바 새 메시지 감지</b>\n"
            f"시각: {datetime.now().strftime('%H:%M')}\n"
            f"오늘 알림 #{state['alert_count_today']}\n\n"
            f"<i>인박스 미리보기 (앞 500자):</i>\n"
            f"<pre>{excerpt}</pre>\n\n"
            f"확인하시려면 레나 터미널에서 <code>인박스 확인</code>이라고 말씀해주세요."
        )
        send_telegram(msg)
    else:
        log("변동 없음")

    save_state(state)
    log("=== 레나 폴러 종료 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
