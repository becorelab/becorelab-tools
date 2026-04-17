"""
레나 알리바바 인박스 폴러
- 5분 주기로 알리바바 인박스 raw text 가져옴
- 이전 상태와 비교해서 새 메시지 신호 감지
- 새 메시지면 레나 봇으로 대표님께 텔레그램 알림
- 비정형 상황 감지는 레나 채널 세션이 받아서 판단함 (poller는 알림만)
"""

import sys
import os
import re
import json
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

LENA_DIR = Path(r"C:\Users\info\ClaudeAITeam\Channel_lena")
STATE_FILE = LENA_DIR / "poller_state.json"
LOG_FILE = LENA_DIR / "poller.log"

LENA_BOT_TOKEN = "8663458998:AAEEnXYWJhq98o2PfoBuqVxbe7JOUvJZYxc"
BOSS_CHAT_ID = "8708718261"

QUIET_START_HOUR = 22
QUIET_END_HOUR = 7
HASH_RING_SIZE = 5
COOLDOWN_MINUTES = 10
EXCERPT_COMPARE_LEN = 200

NOISE_UI_LABELS = {
    "검색", "받은 편지함", "모두", "읽지 않음",
    "프로젝트", "모든 프로젝트 보기",
    "네트워크 연결이 끊어졌습니다",
    "답장", "삭제", "번역", "읽음", "안 읽음",
}

TIME_PATTERNS = [
    re.compile(r"^\d{1,2}:\d{2}$"),
    re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$"),
    re.compile(r"^\d+\s*분\s*전$"),
    re.compile(r"^\d+\s*시간\s*전$"),
    re.compile(r"^\d+\s*일\s*전$"),
    re.compile(r"^방금\s*전$"),
    re.compile(r"^어제$"),
    re.compile(r"^오늘$"),
]

DIGIT_ONLY = re.compile(r"^\d+$")


def extract_signal_text(raw: str) -> str:
    """raw_text에서 노이즈(애니메이션 숫자/시간/UI 라벨) 제거하고 의미 있는 라인만 반환."""
    result = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s in NOISE_UI_LABELS:
            continue
        if DIGIT_ONLY.match(s):
            continue
        if any(pat.match(s) for pat in TIME_PATTERNS):
            continue
        result.append(s)
    return "\n".join(result)

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
    return {
        "last_hash": "",
        "last_check": "",
        "last_excerpt": "",
        "alert_count_today": 0,
        "alert_date": "",
        "recent_hashes": [],
        "last_alert_at": "",
        "last_alert_excerpt_head": "",
        "quiet_suppressed_count": 0,
        "quiet_suppressed_first_at": "",
    }


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def is_quiet_hours(now: datetime) -> bool:
    h = now.hour
    if QUIET_START_HOUR <= QUIET_END_HOUR:
        return QUIET_START_HOUR <= h < QUIET_END_HOUR
    return h >= QUIET_START_HOUR or h < QUIET_END_HOUR


def within_cooldown(state: dict, now: datetime, excerpt_head: str) -> bool:
    last = state.get("last_alert_at", "")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return False
    if now - last_dt > timedelta(minutes=COOLDOWN_MINUTES):
        return False
    return state.get("last_alert_excerpt_head", "") == excerpt_head


def main():
    log("=== 레나 폴러 시작 ===")

    now = datetime.now()
    if is_quiet_hours(now):
        log(f"야간 시간대({QUIET_START_HOUR}~{QUIET_END_HOUR}시) — 폴링 스킵")
        log("=== 레나 폴러 종료 ===")
        return 0

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
    signal_text = extract_signal_text(raw_text)
    text_hash = hashlib.sha256(signal_text.encode("utf-8")).hexdigest()
    excerpt_head = signal_text[:EXCERPT_COMPARE_LEN]

    state = load_state()
    state.setdefault("recent_hashes", [])
    state.setdefault("last_alert_at", "")
    state.setdefault("last_alert_excerpt_head", "")
    state.setdefault("quiet_suppressed_count", 0)
    state.setdefault("quiet_suppressed_first_at", "")

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    if state.get("alert_date") != today:
        state["alert_count_today"] = 0
        state["alert_date"] = today

    state["last_check"] = now.isoformat()
    recent_hashes = state.get("recent_hashes", [])
    quiet = is_quiet_hours(now)

    hash_changed = text_hash != state.get("last_hash")
    hash_in_ring = text_hash in recent_hashes

    should_alert = False
    skip_reason = None

    if not hash_changed:
        skip_reason = "변동 없음"
    elif hash_in_ring:
        skip_reason = f"해시 토글 감지 (최근 링에 이미 있음: {text_hash[:8]})"
    elif within_cooldown(state, now, excerpt_head):
        skip_reason = f"쿨다운 중 (최근 {COOLDOWN_MINUTES}분 내 동일 excerpt)"
    elif quiet:
        state["quiet_suppressed_count"] = state.get("quiet_suppressed_count", 0) + 1
        if not state.get("quiet_suppressed_first_at"):
            state["quiet_suppressed_first_at"] = now.isoformat()
        skip_reason = f"야간 알림 억제 (누적 {state['quiet_suppressed_count']}건)"
    else:
        should_alert = True

    if hash_changed:
        state["last_hash"] = text_hash
        state["last_excerpt"] = raw_text[:300]
        recent_hashes = ([text_hash] + [h for h in recent_hashes if h != text_hash])[:HASH_RING_SIZE]
        state["recent_hashes"] = recent_hashes

    if should_alert:
        state["alert_count_today"] = state.get("alert_count_today", 0) + 1

        quiet_suppressed = state.get("quiet_suppressed_count", 0)
        quiet_header = ""
        if quiet_suppressed > 0:
            since = state.get("quiet_suppressed_first_at", "")
            quiet_header = f"🌙 <i>야간 동안 {quiet_suppressed}건 누적 (since {since[11:16] if since else '?'}) — 지금 최신만 요약</i>\n\n"
            state["quiet_suppressed_count"] = 0
            state["quiet_suppressed_first_at"] = ""

        log(f"알림 발송: hash {text_hash[:8]} (#{state['alert_count_today']})")

        excerpt_show = raw_text[:500].replace("<", "&lt;").replace(">", "&gt;")
        msg = (
            f"📬 <b>[레나] 알리바바 새 메시지 감지</b>\n"
            f"시각: {now.strftime('%H:%M')}\n"
            f"오늘 알림 #{state['alert_count_today']}\n\n"
            f"{quiet_header}"
            f"<i>인박스 미리보기 (앞 500자):</i>\n"
            f"<pre>{excerpt_show}</pre>\n\n"
            f"확인하시려면 레나 터미널에서 <code>인박스 확인</code>이라고 말씀해주세요."
        )
        if send_telegram(msg):
            state["last_alert_at"] = now.isoformat()
            state["last_alert_excerpt_head"] = excerpt_head
    else:
        log(skip_reason)

    save_state(state)
    log("=== 레나 폴러 종료 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
