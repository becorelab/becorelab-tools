"""
봇 그룹채팅 공유 상태 관리

모든 봇(보리/픽시/레나)이 같은 파일을 읽고 쓰면서 협업.
- 라운드 카운터: 봇끼리 N번 주고받으면 자동 정지
- STOP 상태: 대표님이 "그만" 명령 시 정지
- 마지막 발언자: 같은 봇이 연속 발언 방지
"""
import json
import os
import time
from datetime import datetime

STATE_FILE = r"C:\Users\User\ClaudeAITeam\data\group_state.json"
MESSAGES_FILE = r"C:\Users\User\ClaudeAITeam\data\group_messages.json"

# 봇 자율 대화 설정
MAX_BOT_ROUNDS = 100  # 사실상 무제한 (대표님이 STOP으로 통제)
MAX_HISTORY = 30  # 그룹 메시지 히스토리 최대 30개
STOP_KEYWORDS = ["그만해", "조용히", "스톱", "stop", "중지", "잠깐만", "STOP"]
RESET_KEYWORDS = ["시작", "계속", "이어서", "다시"]

# 봇별 호칭 (자기 이름 언급 감지)
BOT_NAME_PATTERNS = {
    "lena": ["레나야", "레나 ", "레나,", "레나~", "레나!", "레나?", "@레나"],
    "pixie": ["픽시야", "픽시 ", "픽시,", "픽시~", "픽시!", "픽시?", "@픽시"],
    "bori": ["보리야", "보리 ", "보리,", "보리~", "보리!", "보리?", "@보리"],
}


def _read_all() -> dict:
    """전체 상태 파일 읽기"""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_all(data: dict):
    """전체 상태 파일 쓰기"""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"group_state 쓰기 실패: {e}")


def get_state(chat_id: int) -> dict:
    """특정 그룹의 상태 조회"""
    all_state = _read_all()
    key = str(chat_id)
    if key not in all_state:
        all_state[key] = {
            "round": 0,
            "last_speaker": None,
            "stopped": False,
            "stopped_at": None,
            "last_human_msg_at": None,
        }
        _write_all(all_state)
    return all_state[key]


def update_state(chat_id: int, **kwargs):
    """특정 그룹의 상태 업데이트"""
    all_state = _read_all()
    key = str(chat_id)
    if key not in all_state:
        all_state[key] = {
            "round": 0,
            "last_speaker": None,
            "stopped": False,
            "stopped_at": None,
            "last_human_msg_at": None,
        }
    all_state[key].update(kwargs)
    _write_all(all_state)


def is_stop_command(text: str) -> bool:
    """STOP 명령 감지"""
    if not text:
        return False
    return any(kw in text for kw in STOP_KEYWORDS)


def is_reset_command(text: str) -> bool:
    """리셋 명령 감지"""
    if not text:
        return False
    return any(kw in text for kw in RESET_KEYWORDS)


def on_human_message(chat_id: int, text: str):
    """대표님 메시지 처리: STOP/RESET 감지 + 라운드 리셋"""
    if is_stop_command(text):
        update_state(
            chat_id,
            stopped=True,
            stopped_at=datetime.now().isoformat(),
            round=0,
            last_speaker="human",
        )
        return "stop"
    if is_reset_command(text):
        update_state(
            chat_id,
            stopped=False,
            round=0,
            last_speaker="human",
            last_human_msg_at=datetime.now().isoformat(),
        )
        return "reset"

    # 일반 메시지 - 라운드 리셋, STOP 해제
    update_state(
        chat_id,
        stopped=False,
        round=0,
        last_speaker="human",
        last_human_msg_at=datetime.now().isoformat(),
    )
    return "human"


def is_directly_mentioned(text: str, bot_name: str) -> bool:
    """봇 이름이 메시지에 언급됐는지 감지 (간접 호명 포함)
    예: '레나야', '레나가', '레나는', '레나도', '@레나', '레나에게' 등 모두 인식
    """
    if not text:
        return False
    # 한글 이름 → 메시지에 포함만 되면 자기 얘기로 간주
    korean_names = {
        "lena": "레나",
        "pixie": "픽시",
        "bori": "보리",
    }
    name = korean_names.get(bot_name)
    if name and name in text:
        return True
    # 텔레그램 username 매칭
    patterns = BOT_NAME_PATTERNS.get(bot_name, [])
    return any(p in text for p in patterns)


def can_bot_respond(chat_id: int, bot_name: str, message_text: str = "") -> tuple[bool, str]:
    """
    봇이 응답할 수 있는지 판단
    Returns: (응답 가능 여부, 사유)
    """
    state = get_state(chat_id)

    # STOP 상태면 응답 금지 (단, 직접 멘션이면 무시 못 함)
    if state.get("stopped"):
        return False, "stopped"

    # 자기 이름 직접 언급되면 무조건 응답 (라운드/연속 무시)
    if is_directly_mentioned(message_text, bot_name):
        return True, "directly_called"

    # 라운드 한도 초과
    if state.get("round", 0) >= MAX_BOT_ROUNDS:
        return False, "max_round"

    # 자기가 직전 발언자면 연속 발언 금지 (이름 언급 안 됐을 때)
    if state.get("last_speaker") == bot_name:
        return False, "consecutive"

    return True, "ok"


def on_bot_response(chat_id: int, bot_name: str):
    """봇이 응답한 후 상태 업데이트"""
    state = get_state(chat_id)
    update_state(
        chat_id,
        round=state.get("round", 0) + 1,
        last_speaker=bot_name,
    )


def get_status_summary(chat_id: int) -> str:
    """상태 요약 (디버그용)"""
    state = get_state(chat_id)
    return (
        f"Round: {state.get('round', 0)}/{MAX_BOT_ROUNDS} | "
        f"Last: {state.get('last_speaker')} | "
        f"Stopped: {state.get('stopped', False)}"
    )


# === 그룹 메시지 공유 히스토리 ===
# 모든 봇이 같은 메시지 로그를 보고 응답 → 진짜 대화 가능

def _read_messages() -> dict:
    if not os.path.exists(MESSAGES_FILE):
        return {}
    try:
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_messages(data: dict):
    try:
        os.makedirs(os.path.dirname(MESSAGES_FILE), exist_ok=True)
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"group_messages 쓰기 실패: {e}")


def append_group_message(chat_id: int, sender: str, content: str, message_id: int = None):
    """그룹 메시지를 공유 로그에 추가
    sender: 'human', 'bori', 'pixie', 'lena' 등
    """
    all_msgs = _read_messages()
    key = str(chat_id)
    if key not in all_msgs:
        all_msgs[key] = []

    # 중복 방지 (message_id 있으면)
    if message_id:
        for msg in all_msgs[key]:
            if msg.get("message_id") == message_id:
                return

    all_msgs[key].append({
        "sender": sender,
        "content": content,
        "message_id": message_id,
        "ts": datetime.now().isoformat(),
    })

    if len(all_msgs[key]) > MAX_HISTORY:
        all_msgs[key] = all_msgs[key][-MAX_HISTORY:]

    _write_messages(all_msgs)


def get_group_context(chat_id: int, current_bot_name: str, limit: int = 20) -> list:
    """그룹 대화를 LLM 컨텍스트(messages 배열)로 변환
    자기가 한 말은 'assistant', 나머지는 'user'로 (이름 라벨 포함)
    """
    all_msgs = _read_messages()
    key = str(chat_id)
    msgs = all_msgs.get(key, [])[-limit:]

    formatted = []
    for msg in msgs:
        sender = msg["sender"]
        content = msg["content"]
        if sender == current_bot_name:
            formatted.append({"role": "assistant", "content": content})
        else:
            # 누가 말했는지 명시 (사람처럼 인식하라고)
            label_map = {
                "human": "대표님",
                "bori": "보리🐻",
                "pixie": "픽시🦋",
                "lena": "레나🌹",
            }
            label = label_map.get(sender, sender)
            formatted.append({
                "role": "user",
                "content": f"[{label}]: {content}"
            })
    return formatted
