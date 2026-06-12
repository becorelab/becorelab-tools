"""통합 장애 알림 — 모든 크론/파이프라인 공용 모듈.
문제 발생 시 두리 텔레그램으로 등급별 알림 전송. ("조용히 실패" 근절)

사용:
    import sys; sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
    from alert import alert
    alert("그로스 크론", "세션 만료 — gross_relogin.sh로 재로그인 필요", "critical")

level: "critical"(🔴 매출/수집 멈춤) | "warn"(🟡 곧 만료/주의) | "info"(ℹ️)
토큰은 automation/.env(gitignore됨)에서 로드 — 코드에 평문 토큰 없음.
"""
import os
from datetime import datetime

import requests

_ENV = "/Users/macmini_ky/ClaudeAITeam/automation/.env"


def _load_env():
    if os.path.exists(_ENV):
        for line in open(_ENV, encoding="utf-8"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()
_TOKEN = os.environ.get("DOORI_BOT_TOKEN", "")
_CHAT = os.environ.get("DOORI_CHAT_ID", "")
_EMOJI = {"critical": "🔴", "warn": "🟡", "info": "ℹ️"}
_HEADER = {
    "critical": "대표님~ 봐주셔야 할 게 있어요 🥺",
    "warn": "대표님~ 미리 살짝 알려드려요! 🟡",
    "info": "대표님~ 하치예요 😊",
}


def alert(source: str, message: str, level: str = "critical") -> bool:
    """장애 알림을 두리 텔레그램으로 전송.

    source : 출처 (예: '그로스 크론', '로켓', '인스타 공구')
    message: 내용 + 가능하면 조치 방법까지
    level  : 'critical' / 'warn' / 'info'

    알림 전송 실패가 본 작업을 막지 않도록 예외를 던지지 않음(항상 bool 반환)."""
    emoji = _EMOJI.get(level, "🔴")
    ts = datetime.now().strftime("%m/%d %H:%M")
    head = _HEADER.get(level, "대표님~ 하치예요 😊")
    text = (
        f"{emoji} <b>{head}</b>\n\n"
        f"💬 {message}\n\n"
        f"<i>📍 {source} · {ts} · 하치가 챙기고 있어요 💕</i>"
    )
    if not _TOKEN or not _CHAT:
        print(f"[ALERT-미설정] {source}: {message}")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{_TOKEN}/sendMessage",
            json={"chat_id": _CHAT, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if not r.ok:
            print(f"[ALERT-실패] HTTP {r.status_code}: {r.text[:120]}")
        return r.ok
    except Exception as e:
        print(f"[ALERT-예외] {e}")
        return False


if __name__ == "__main__":
    ok = alert(
        "알림 테스트",
        "통합 장애 알림 시스템 가동 확인 ✅\n이제 크론이 터지면 여기로 바로 알려드려요!",
        "info",
    )
    print("전송:", "성공" if ok else "실패")
