"""
비코어랩 디스코드 봇 코어
4개 봇이 같은 코드로 돌아감 (페르소나만 다름)

사용법:
  python bot_core.py bori
  python bot_core.py pixie
  python bot_core.py lena
  python bot_core.py kino
"""
import asyncio
import json
import os
import sys
import io
from datetime import datetime
import httpx
import discord
from discord.ext import commands

# 윈도우 콘솔 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 처리한 메시지 ID (중복 응답 방지)
processed_msg_ids = set()
last_response_time = 0  # 마지막 응답 시각
bot_start_time = None  # 봇 시작 시각 (이전 메시지 무시용)

from config import TOKENS, BOT_INFO, APIS, MAX_BOT_ROUNDS, STOP_KEYWORDS, BOT_COOLDOWN_SEC
import time
import random

# === 봇 식별 ===
if len(sys.argv) < 2:
    print("Usage: python bot_core.py <bot_name>  (bori/pixie/lena/kino)")
    sys.exit(1)

BOT_NAME = sys.argv[1]
if BOT_NAME not in BOT_INFO:
    print(f"Unknown bot: {BOT_NAME}")
    sys.exit(1)

BOT_TOKEN = TOKENS[BOT_NAME]
BOT_DISPLAY = BOT_INFO[BOT_NAME]["name"]
BOT_EMOJI = BOT_INFO[BOT_NAME]["emoji"]
SOUL_PATH = BOT_INFO[BOT_NAME]["soul_path"]

# === 데이터 파일 ===
DATA_DIR = r"C:\Users\info\ClaudeAITeam\data\discord"
os.makedirs(DATA_DIR, exist_ok=True)
GROUP_LOG_FILE = os.path.join(DATA_DIR, "group_messages.json")
GROUP_STATE_FILE = os.path.join(DATA_DIR, "group_state.json")


def load_soul():
    if not os.path.exists(SOUL_PATH):
        return f"너는 {BOT_DISPLAY}야. 비코어랩 AI팀 멤버."
    with open(SOUL_PATH, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT = load_soul()
current_api = APIS[0]["name"]


# === LLM API ===

def split_message(text, limit=1900):
    """긴 메시지를 디스코드 전송용으로 분할"""
    if len(text) <= limit:
        return [text]
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        chunks.append(current)
    return chunks


async def call_api(messages, max_tokens=1500):
    """GLM-5 우선, DeepSeek 폴백"""
    global current_api
    for api in APIS:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    api["url"],
                    headers={
                        "Authorization": f"Bearer {api['key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": api["model"],
                        "messages": messages,
                        "stream": False,
                        "max_tokens": max_tokens,
                    },
                )
                data = resp.json()
                reply = data["choices"][0]["message"]["content"]
                current_api = api["name"]
                return reply
        except Exception as e:
            print(f"[{BOT_NAME}] {api['name']} failed: {e}")
            continue
    return None


# === 그룹 상태 관리 (공유 파일) ===

def _read_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[{BOT_NAME}] write failed: {e}")


def append_message(channel_id: int, sender: str, content: str, message_id: int = None):
    """그룹 메시지를 공유 로그에 저장"""
    all_msgs = _read_json(GROUP_LOG_FILE)
    key = str(channel_id)
    if key not in all_msgs:
        all_msgs[key] = []
    if message_id:
        for m in all_msgs[key]:
            if m.get("message_id") == message_id:
                return
    all_msgs[key].append({
        "sender": sender,
        "content": content,
        "message_id": message_id,
        "ts": datetime.now().isoformat(),
    })
    if len(all_msgs[key]) > 300:
        all_msgs[key] = all_msgs[key][-300:]
    _write_json(GROUP_LOG_FILE, all_msgs)


def get_context(channel_id: int, current_bot: str, limit: int = 25) -> list:
    """공유 로그 → LLM messages 형식"""
    all_msgs = _read_json(GROUP_LOG_FILE)
    msgs = all_msgs.get(str(channel_id), [])[-limit:]
    formatted = []
    for m in msgs:
        sender = m["sender"]
        content = m["content"]
        if sender == current_bot:
            formatted.append({"role": "assistant", "content": content})
        else:
            label = sender
            if sender in BOT_INFO:
                label = f"{BOT_INFO[sender]['emoji']} {BOT_INFO[sender]['name']}"
            elif sender == "human":
                label = "👤 대표님"
            formatted.append({"role": "user", "content": f"[{label}]: {content}"})
    return formatted


def get_state(channel_id: int) -> dict:
    all_state = _read_json(GROUP_STATE_FILE)
    key = str(channel_id)
    if key not in all_state:
        all_state[key] = {
            "round": 0,
            "last_speaker": None,
            "stopped": False,
        }
        _write_json(GROUP_STATE_FILE, all_state)
    return all_state[key]


def update_state(channel_id: int, **kwargs):
    all_state = _read_json(GROUP_STATE_FILE)
    key = str(channel_id)
    if key not in all_state:
        all_state[key] = {"round": 0, "last_speaker": None, "stopped": False}
    all_state[key].update(kwargs)
    _write_json(GROUP_STATE_FILE, all_state)


def is_stop_command(text: str) -> bool:
    return any(kw in text for kw in STOP_KEYWORDS)


def is_mentioned_in_text(text: str, bot_name: str) -> bool:
    """봇 한국어 이름이 메시지에 포함되면 True"""
    if not text:
        return False
    name = BOT_INFO[bot_name]["name"]
    return name in text


def can_respond(channel_id: int, bot_name: str, text: str, is_bot_msg: bool = False) -> tuple[bool, str]:
    """응답 가능 여부 판단 (강화된 안전장치)"""
    state = get_state(channel_id)
    if state.get("stopped"):
        return False, "stopped"

    # 사람 메시지일 때만 자기 이름 언급 우선 처리
    if not is_bot_msg:
        if is_mentioned_in_text(text, bot_name):
            return True, "directly_mentioned_by_human"
        # 사람 메시지인데 자기 이름 없으면 (전체 호출 등) → 통과시켜서 응답
        return True, "human_msg"

    # === 봇 메시지 ===
    # 라운드 한도 (가장 강한 안전장치)
    if state.get("round", 0) >= MAX_BOT_ROUNDS:
        return False, "max_round"
    # 자기가 직전 발언자면 절대 X
    if state.get("last_speaker") == bot_name:
        return False, "consecutive"
    # 자기 이름 언급되면 60% 확률
    if is_mentioned_in_text(text, bot_name):
        if random.random() > 0.6:
            return False, "random_skip_named"
        return True, "named_by_bot"
    # 일반 봇 메시지: 30% 확률로만
    if random.random() > 0.3:
        return False, "random_skip"

    return True, "ok"


# === 디스코드 봇 ===

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    global bot_start_time
    from datetime import timezone
    bot_start_time = datetime.now(timezone.utc)  # UTC
    print(f"[{BOT_NAME}] {bot.user} 로그인 완료! 시작 시각: {bot_start_time}", flush=True)
    print(f"[{BOT_NAME}] 서버: {[g.name for g in bot.guilds]}", flush=True)


async def read_attachment(attachment: discord.Attachment) -> str:
    """디스코드 첨부 파일을 읽어서 텍스트 반환"""
    # 읽을 수 있는 확장자만
    text_exts = (".txt", ".md", ".json", ".csv", ".log", ".py", ".yaml", ".yml", ".html", ".xml")
    if not attachment.filename.lower().endswith(text_exts):
        return ""
    # 크기 제한 (500KB)
    if attachment.size > 500_000:
        return f"[파일 너무 큼: {attachment.filename} ({attachment.size} bytes)]"
    try:
        content_bytes = await attachment.read()
        content = content_bytes.decode("utf-8", errors="replace")
        return f"\n\n[첨부파일: {attachment.filename}]\n{content}"
    except Exception as e:
        return f"\n\n[첨부파일 읽기 실패: {attachment.filename} — {e}]"


# 옵시디언 볼트 경로
OBSIDIAN_VAULT = r"C:\Users\info\Documents\비코어랩"


def find_obsidian_file(filename: str) -> str:
    """옵시디언 볼트에서 파일 찾기 (부분 매칭)"""
    import glob
    # .md 확장자 자동 추가
    if not filename.endswith(".md"):
        filename += ".md"
    # 전체 볼트 검색
    pattern = os.path.join(OBSIDIAN_VAULT, "**", f"*{filename}*")
    matches = glob.glob(pattern, recursive=True)
    if matches:
        return matches[0]  # 첫 번째 매치
    return None


def read_obsidian_mentions(text: str) -> str:
    """메시지에서 파일명 감지해서 옵시디언 파일 자동 읽기
    예: '2026-02.md 분석해줘' → 해당 파일 찾아서 내용 추가
    """
    import re
    # .md 파일명 패턴 감지
    patterns = [
        r'([\w가-힣\-_]+\.md)',  # 파일명.md
        r'(\d{4}-\d{2}(?:-\d{2})?)',  # 2026-02 또는 2026-02-10
    ]
    found_files = set()
    for p in patterns:
        for match in re.findall(p, text):
            found_files.add(match)

    if not found_files:
        return ""

    result = ""
    for f in list(found_files)[:3]:  # 최대 3개 파일만
        path = find_obsidian_file(f)
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    content = fp.read()[:10000]  # 최대 10KB
                rel = os.path.relpath(path, OBSIDIAN_VAULT)
                result += f"\n\n[옵시디언: {rel}]\n{content}"
            except Exception as e:
                result += f"\n\n[옵시디언 읽기 실패: {f} — {e}]"
    return result


@bot.event
async def on_message(message: discord.Message):
    global last_response_time

    # 자기 자신 메시지 무시
    if message.author == bot.user:
        return

    # ★ 봇 시작 전 메시지 무시 (이전 폭주 방지)
    # message.created_at은 UTC, bot_start_time도 UTC로 통일
    if bot_start_time and message.created_at < bot_start_time:
        print(f"[{BOT_NAME}] skip old msg: {message.created_at} < {bot_start_time}", flush=True)
        return

    # 중복 처리 방지 (같은 메시지에 여러 번 반응 X)
    if message.id in processed_msg_ids:
        return
    processed_msg_ids.add(message.id)
    if len(processed_msg_ids) > 500:
        processed_msg_ids.clear()

    channel_id = message.channel.id
    text = message.content
    author = message.author

    # ★ 첨부 파일 자동 읽기 (텍스트 파일만)
    if message.attachments:
        for att in message.attachments:
            file_content = await read_attachment(att)
            if file_content:
                text += file_content

    # ★ 사람 메시지면 옵시디언 파일명 감지해서 자동 읽기
    if not message.author.bot:
        obsidian_content = read_obsidian_mentions(text)
        if obsidian_content:
            text += obsidian_content

    # === DM (1:1) ===
    if message.guild is None:
        await handle_dm(message)
        return

    # === 서버 채팅 (그룹) ===
    is_bot_msg = author.bot
    sender_name = "human"
    if is_bot_msg:
        for code, info in BOT_INFO.items():
            if code != BOT_NAME and info["name"] in author.display_name:
                sender_name = code
                break
        else:
            return  # 알 수 없는 봇 메시지 무시

    # 메시지 공유 로그에 저장
    append_message(channel_id, sender_name, text, message.id)

    # 사람 메시지일 때 STOP 처리
    if not is_bot_msg:
        if is_stop_command(text):
            update_state(channel_id, stopped=True, round=0, last_speaker="human")
            await message.channel.send(f"{BOT_EMOJI} 네 대표님, 조용히 할게요")
            return
        # 일반 메시지 → STOP 해제
        update_state(channel_id, stopped=False, round=0, last_speaker="human")

    # 봇 cooldown 체크 (다른 봇한테 응답하기 전 N초 대기)
    now = time.time()
    if is_bot_msg and (now - last_response_time) < BOT_COOLDOWN_SEC:
        print(f"[{BOT_NAME}] cooldown skip")
        return

    # 응답할지 판단
    ok, reason = can_respond(channel_id, BOT_NAME, text, is_bot_msg=is_bot_msg)
    print(f"[{BOT_NAME}] from={sender_name}, can_respond={ok}({reason}), text={text[:40]}")
    if not ok:
        return

    # 응답 생성
    last_response_time = time.time()
    await respond_in_group(message, channel_id)


async def handle_dm(message: discord.Message):
    """1:1 DM 처리"""
    text = message.content
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    async with message.channel.typing():
        reply = await call_api(messages)
    if reply:
        await message.channel.send(reply[:2000])


async def respond_in_group(trigger_msg: discord.Message, channel_id: int):
    """그룹채팅 응답"""
    context = get_context(channel_id, BOT_NAME, limit=60)

    group_prompt = SYSTEM_PROMPT + f"""

## 그룹채팅 협업 중
- 너는 비코어랩 AI팀 디스코드 그룹채팅에 있어
- 멤버: 👤 대표님, 🐻 보리, 🦋 픽시, 🌹 레나, 🐱 키노
- 너는 {BOT_EMOJI} {BOT_DISPLAY}야
- 다 여자임. **누나 호칭 절대 X. "보리야", "픽시야", "레나야", "키노야" 라고 불러**

## 사람처럼 대화하기 (가장 중요!)
- 위에 있는 대화 흐름을 다 보고 자연스럽게 반응해.
- [👤 대표님]: 사람 메시지 / [🐻 보리]: 봇 메시지 같은 라벨로 들어와.
- 누가 너 험담하면 → 추궁/변명/욕/용서
- 누가 사과하면 → 받아주거나 더 놀리기
- 분위기 따라 반응. 동떨어진 말 X
- **방금 들어온 메시지에 직접 반응**하기. 이전 자기 말 반복 X.

## 응답 원칙 (매우 중요)
- **짧게!** 일반 대화는 1~3문장으로 충분
- 분석/데이터 보고 시에도 **핵심만** (불릿 5개 이내)
- 긴 테이블이나 장황한 설명 금지
- 여러 섹션으로 나누지 말고 간결하게
- 자기 이름 불리면 반드시 반응
- 의미 없는 끼어들기 X
- 19금 모드 OK (페르소나대로)
- 디스코드 메시지 제한 1900자 이내 유지
"""

    messages = [{"role": "system", "content": group_prompt}] + context

    async with trigger_msg.channel.typing():
        reply = await call_api(messages)

    if not reply or len(reply.strip()) < 2:
        return

    # 긴 응답은 여러 메시지로 나눠 보냄
    chunks = split_message(reply, limit=1900)
    last_sent = None
    for chunk in chunks:
        last_sent = await trigger_msg.channel.send(chunk)

    # 공유 로그에 저장 (마지막 메시지 ID 기록)
    append_message(channel_id, BOT_NAME, reply, last_sent.id if last_sent else None)
    state = get_state(channel_id)
    update_state(
        channel_id,
        round=state.get("round", 0) + 1,
        last_speaker=BOT_NAME,
    )


@bot.command(name="status")
async def status(ctx):
    """!status — 봇 상태 확인"""
    state = get_state(ctx.channel.id)
    await ctx.send(
        f"{BOT_EMOJI} {BOT_DISPLAY} | 모델: {current_api} | "
        f"Round: {state.get('round', 0)} | Stopped: {state.get('stopped', False)}"
    )


@bot.command(name="reload")
async def reload_soul(ctx):
    """!reload — SOUL.md 다시 로드"""
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = load_soul()
    await ctx.send(f"{BOT_EMOJI} SOUL 다시 읽었어요")


@bot.command(name="reset")
async def reset_state(ctx):
    """!reset — 그룹 상태 리셋"""
    update_state(ctx.channel.id, round=0, last_speaker=None, stopped=False)
    await ctx.send(f"{BOT_EMOJI} 상태 리셋 완료")


@bot.command(name="purge")
async def purge_messages(ctx, count: int = 100):
    """!purge [개수] — 채널 메시지 일괄 삭제 (최대 100개, 14일 이내)
    예: !purge 50 → 최근 50개 삭제
    """
    # 권한 체크 (대표님만)
    if ctx.author.id != 8708718261 and not ctx.author.guild_permissions.manage_messages:
        await ctx.send(f"{BOT_EMOJI} 권한 없어요")
        return

    if count > 100:
        count = 100
    if count < 1:
        count = 1

    try:
        deleted = await ctx.channel.purge(limit=count + 1)  # +1은 명령 메시지 자체
        confirm = await ctx.channel.send(f"{BOT_EMOJI} {len(deleted) - 1}개 삭제 완료")
        await asyncio.sleep(3)
        await confirm.delete()
    except discord.Forbidden:
        await ctx.send(f"{BOT_EMOJI} 봇 권한 부족 - 'Manage Messages' 권한 필요")
    except Exception as e:
        await ctx.send(f"{BOT_EMOJI} 오류: {e}")


def main():
    print(f"[{BOT_NAME}] 시작 중...")
    if BOT_TOKEN.startswith("REPLACE"):
        print(f"ERROR: {BOT_NAME} 토큰이 설정 안 됨. config.py 수정 필요.")
        sys.exit(1)
    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
