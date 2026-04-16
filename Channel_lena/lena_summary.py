"""
레나 정기 보고 — 하루 2회 (11시, 17시)
- 폴러 로그 + conversations/ 디렉토리 + poller_state.json 종합
- 처리 대화 요약, 진행중 건, 에스컬레이션 현황을 텔레그램으로 전송
"""

import sys
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

LENA_DIR = Path(r"C:\Users\info\ClaudeAITeam\Channel_lena")
STATE_FILE = LENA_DIR / "poller_state.json"
LOG_FILE = LENA_DIR / "poller.log"
CONV_DIR = Path(r"C:\Users\info\ClaudeAITeam\sourcing\mio\conversations")

LENA_BOT_TOKEN = "8663458998:AAEEnXYWJhq98o2PfoBuqVxbe7JOUvJZYxc"
BOSS_CHAT_ID = "8708718261"


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
            return json.loads(resp.read().decode()).get("ok", False)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")
        return False


def collect_conversations() -> dict:
    """mio/conversations/{category}/{supplier}.json 전체 스캔"""
    summary = {"by_stage": {}, "recently_active": []}
    if not CONV_DIR.exists():
        return summary

    cutoff = datetime.now() - timedelta(hours=12)
    for path in CONV_DIR.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        stage = data.get("stage", "unknown")
        summary["by_stage"][stage] = summary["by_stage"].get(stage, 0) + 1

        last_msg = data.get("messages", [{}])[-1] if data.get("messages") else {}
        ts_str = last_msg.get("ts") or data.get("updated_at")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts > cutoff:
                    summary["recently_active"].append({
                        "supplier": data.get("supplier") or path.stem,
                        "stage": stage,
                        "last_ts": ts_str,
                    })
            except Exception:
                pass

    return summary


def main():
    now = datetime.now()
    title_hour = now.strftime("%H:%M")

    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    last_check = state.get("last_check", "(없음)")
    alerts_today = state.get("alert_count_today", 0)

    convs = collect_conversations()
    stage_lines = "\n".join(
        f"  • {stage}: {count}건" for stage, count in sorted(convs["by_stage"].items())
    ) or "  • (대화 데이터 없음)"

    recent_lines = "\n".join(
        f"  • {r['supplier']} ({r['stage']})" for r in convs["recently_active"][:10]
    ) or "  • 최근 12시간 내 활동 없음"

    msg = (
        f"📊 <b>[레나] {title_hour} 정기 보고</b>\n"
        f"보고 시각: {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"오늘 폴러 알림: {alerts_today}건\n"
        f"마지막 인박스 체크: {last_check[:19].replace('T', ' ')}\n\n"
        f"<b>대화 단계별</b>\n{stage_lines}\n\n"
        f"<b>최근 12시간 활동</b>\n{recent_lines}"
    )
    ok = send_telegram(msg)
    print(f"보고 전송: {'성공' if ok else '실패'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
