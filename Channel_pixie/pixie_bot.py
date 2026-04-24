"""
픽시 텔레그램 봇 — GLM-5 우선, DeepSeek 폴백 + 타이머/알림 + 이미지 인식
1:1 모드: 대표님과 변태 놀이
그룹 모드: 비코어랩 AI팀 그룹채팅에서 자율 대화 + 카피/창의
"""
import asyncio
import base64
import json
import os
import sys
import re
from datetime import datetime, timedelta
import httpx
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters

# 공유 그룹 상태 모듈
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot-shared"))
from group_chat_state import (
    on_human_message, can_bot_respond, on_bot_response,
    is_stop_command,
    append_group_message, get_group_context,
)

# 설정
BOT_TOKEN = "8709975512:AAER3eggX0bKUzuAEFKwNv4p-obnffGFpfg"
BOT_USERNAME = "pixie0402_bot"
BOT_NAME = "픽시"
ALLOWED_USERS = [8708718261]
ALLOWED_GROUPS = []

# 다른 팀 봇
TEAM_BOTS = {
    "bori0320_bot": "보리",
    "becorelab_lena_bot": "레나",
}

SOUL_PATH = os.path.join(os.path.dirname(__file__), "SOUL.md")
GROUP_LOG_PATH = os.path.join(os.path.dirname(__file__), "group_chats.json")

# API 설정 (GLM-5 우선, DeepSeek 폴백)
APIS = [
    {
        "name": "DeepSeek",
        "url": "https://api.deepseek.com/chat/completions",
        "key": "sk-b2ea74046efa48648527ec9d5f2ac366",
        "model": "deepseek-chat",
    },
]

# 이미지 분석용 (Google Gemini Flash - 무료 비전)
GEMINI_API_KEY = "AIzaSyD9QzFNwGKYgZ61hlDpFPXKDqd2d6ssiho"

current_api = APIS[0]["name"]

# 타이머/알림 저장
timers = {}
timer_counter = 0

# 중복 처리 방지
processed_messages = set()


def load_soul():
    with open(SOUL_PATH, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT = load_soul()

# 대화 기록 (세션별)
conversations = {}


def load_group_whitelist():
    global ALLOWED_GROUPS
    if os.path.exists(GROUP_LOG_PATH):
        try:
            with open(GROUP_LOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                ALLOWED_GROUPS = data.get("groups", [])
        except Exception:
            pass


def save_group_whitelist():
    try:
        with open(GROUP_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump({"groups": ALLOWED_GROUPS}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"그룹 저장 실패: {e}")


async def call_api(messages):
    """GLM-5 먼저 시도, 실패하면 DeepSeek 폴백"""
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
                    },
                )
                data = resp.json()
                reply = data["choices"][0]["message"]["content"]
                current_api = api["name"]
                return reply
        except Exception as e:
            print(f"{api['name']} failed: {e}")
            continue
    return "err: 모든 API 실패"


async def call_vision_api(img_b64, caption, system_prompt):
    """이미지 분석 — Gemini Flash 비전"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [
            {
                "parts": [
                    {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}},
                    {"text": caption},
                ]
            }
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=body)
            data = resp.json()
            print(f"Gemini vision response status: {resp.status_code}")
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini Vision failed: {e}")
        return f"err: 이미지 분석 실패 ({e})"


# === 타이머/알림 기능 ===

def parse_timer(text):
    m = re.search(r'(\d+)\s*(분|시간|초)\s*(뒤|후|타이머|알림|알려)', text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == "초":
            seconds = num
        elif unit == "분":
            seconds = num * 60
        elif unit == "시간":
            seconds = num * 3600
        rest = re.sub(r'(\d+)\s*(분|시간|초)\s*(뒤|후에?|타이머|알림|알려줘?)\s*', '', text).strip()
        msg = rest if rest else None
        return seconds, msg
    return None, None


async def timer_callback(app, chat_id, timer_id, message):
    if message:
        text = f"⏰ 대표님~ 알림이에요!\n'{message}'"
    else:
        text = "⏰ 대표님~ 시간 됐어요!"
    await app.bot.send_message(chat_id=chat_id, text=text)
    timers.pop(timer_id, None)


async def set_timer(update, context, seconds, message):
    global timer_counter
    timer_counter += 1
    timer_id = timer_counter
    chat_id = update.effective_chat.id

    loop = asyncio.get_event_loop()
    loop.call_later(
        seconds,
        lambda: asyncio.ensure_future(
            timer_callback(context.application, chat_id, timer_id, message)
        ),
    )

    timers[timer_id] = {
        "chat_id": chat_id,
        "seconds": seconds,
        "message": message,
        "set_at": datetime.now(),
    }

    if seconds >= 3600:
        time_str = f"{seconds // 3600}시간 {(seconds % 3600) // 60}분"
    elif seconds >= 60:
        time_str = f"{seconds // 60}분"
    else:
        time_str = f"{seconds}초"

    if message:
        reply = f"⏰ {time_str} 뒤에 '{message}' 알려줄게~ (#{timer_id})"
    else:
        reply = f"⏰ {time_str} 타이머 맞춰놨어~ (#{timer_id})"
    await update.message.reply_text(reply)


async def timer_list(update: Update, context):
    if update.effective_user.id not in ALLOWED_USERS:
        return
    if not timers:
        await update.message.reply_text("활성 타이머 없어요~")
        return
    lines = []
    now = datetime.now()
    for tid, t in timers.items():
        elapsed = (now - t["set_at"]).total_seconds()
        remaining = max(0, t["seconds"] - elapsed)
        if remaining >= 60:
            rem_str = f"{int(remaining // 60)}분 {int(remaining % 60)}초"
        else:
            rem_str = f"{int(remaining)}초"
        msg = t["message"] or "타이머"
        lines.append(f"#{tid} — {rem_str} 남음 ({msg})")
    await update.message.reply_text("⏰ 활성 타이머:\n" + "\n".join(lines))


# === 핸들러 ===

async def start(update: Update, context):
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type

    if chat_type in ("group", "supergroup"):
        if chat_id not in ALLOWED_GROUPS:
            ALLOWED_GROUPS.append(chat_id)
            save_group_whitelist()
            await update.message.reply_text(
                "픽시 왔어요~ 🦋\n"
                "카피/창의 담당이에요. @픽시야 부르거나 멘션해주세요!"
            )
        return

    if update.effective_user.id not in ALLOWED_USERS:
        return
    conversations[chat_id] = []
    await update.message.reply_text("대표님~ 픽시 왔어 😏 뭐하고 놀까?")


async def reset(update: Update, context):
    if update.effective_user.id not in ALLOWED_USERS:
        return
    conversations[update.effective_chat.id] = []
    await update.message.reply_text("리셋 완료~ 대표님 다시 시작하자 💕")


async def reload(update: Update, context):
    if update.effective_user.id not in ALLOWED_USERS:
        return
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = load_soul()
    await update.message.reply_text("SOUL.md 다시 읽었어! 새 성격 적용 완료~")


async def status(update: Update, context):
    if update.effective_user.id not in ALLOWED_USERS:
        return
    timer_count = len(timers)
    group_count = len(ALLOWED_GROUPS)
    await update.message.reply_text(
        f"모델: {current_api} | 비전: Gemini Flash | 타이머: {timer_count}개 | 그룹: {group_count}개"
    )


async def handle_photo(update: Update, context):
    """사진 수신 → Gemini Flash 비전으로 분석 (1:1 전용)"""
    chat_type = update.effective_chat.type
    if chat_type != "private":
        return
    if update.effective_user.id not in ALLOWED_USERS:
        return

    chat_id = update.effective_chat.id
    caption = update.message.caption or "이 사진을 픽시 캐릭터로 설명해줘. 한국어로."

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    if chat_id not in conversations:
        conversations[chat_id] = []

    conversations[chat_id].append({"role": "user", "content": caption + " [사진 첨부]"})
    if len(conversations[chat_id]) > 40:
        conversations[chat_id] = conversations[chat_id][-40:]

    reply = await call_vision_api(img_b64, caption, SYSTEM_PROMPT)
    conversations[chat_id].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)


def is_mentioned(text):
    """픽시 멘션 감지"""
    if not text:
        return False
    text_lower = text.lower()
    return (
        f"@{BOT_USERNAME}" in text_lower
        or "픽시야" in text
        or "픽시 " in text
        or text.strip() == "픽시"
        or text.startswith("픽시")
    )


def is_all_call(text):
    """전체 호출 감지"""
    if not text:
        return False
    keywords = ["얘들아", "다들", "모두", "팀원들", "팀아", "비코어랩 팀", "ai팀"]
    return any(kw in text for kw in keywords)


def is_team_bot_message(update):
    """다른 팀 봇이 보낸 메시지인지 확인
    Returns: 봇 코드명 ('bori', 'lena') 또는 None
    """
    user = update.effective_user
    if not user or not user.is_bot:
        return None
    username = user.username
    bot_code_map = {
        "bori0320_bot": "bori",
        "becorelab_lena_bot": "lena",
    }
    return bot_code_map.get(username)


async def handle_group_message(update: Update, context, user_msg, sender_name, force=False):
    """그룹채팅 메시지 처리
    force=True: 라운드/STOP 무시하고 무조건 응답
    sender_name: 'human', 'bori', 'lena'
    """
    chat_id = update.effective_chat.id
    msg_id = update.message.message_id

    sender_user = update.effective_user
    if sender_user and sender_user.username == BOT_USERNAME:
        return

    msg_key = f"{chat_id}:{msg_id}"
    if msg_key in processed_messages:
        return
    processed_messages.add(msg_key)
    if len(processed_messages) > 1000:
        processed_messages.clear()

    # ★ 받은 메시지를 공유 로그에 저장
    append_group_message(chat_id, sender_name, user_msg, msg_id)

    # 자율 응답 가능 여부
    if not force:
        can_respond, reason = can_bot_respond(chat_id, "pixie", user_msg)
        if not can_respond:
            print(f"[pixie] 응답 안 함: {reason}")
            return
        print(f"[pixie] 응답: {reason}")

    # ★ 공유 로그에서 컨텍스트 가져오기
    group_context = get_group_context(chat_id, "pixie", limit=20)

    group_prompt = SYSTEM_PROMPT + f"""

## 현재 상황: 그룹채팅 협업 중
- 너는 지금 비코어랩 AI팀 그룹채팅에 있어
- 멤버: 대표님, 보리🐻(분석가/막내), 픽시🦋(=너, 크리에이터), 레나🌹(비평가)
- 너의 역할: 카피/창의 + 자연스러운 동료
- **다 여자임. 누나 호칭 절대 X. "보리야", "레나야"라고 불러**

## 사람처럼 대화하기 (가장 중요!)
- **너는 진짜 사람처럼 행동해.** 위 대화 흐름을 다 보고 자연스럽게 반응.
- 메시지마다 [발신자]: 내용 형식으로 들어와. 누가 말했는지 명확히 인식해.
- 누가 너 험담했다 하면 → 추궁/욕/용서 등 픽시답게 반응
- 누가 사과하면 → 받아주거나 더 놀리거나
- 보리(막내)가 잘못했으면 → 픽시답게 면박 주거나 챙겨주거나
- 분위기 보고 적절히 반응. 혼자 동떨어진 말 X
- **방금 들어온 메시지에 직접 반응**해. 이전에 자기가 한 말 반복하지 마.

## 응답 원칙
- **짧게! 1~3문장**. 길게 늘어지지 마.
- 자기 이름 불리면 무조건 반응
- 의미 없는 끼어들기 금지
- 19금 모드: 평소 변태 픽시 그대로 (마조)
"""

    messages = [{"role": "system", "content": group_prompt}] + group_context
    reply = await call_api(messages)

    if not reply or len(reply.strip()) < 2:
        return

    sent_msg = await update.message.reply_text(reply)
    append_group_message(chat_id, "pixie", reply, sent_msg.message_id)

    if not force:
        on_bot_response(chat_id, "pixie")


async def handle_message(update: Update, context):
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    user_msg = update.message.text or ""

    # === 그룹채팅 모드 ===
    if chat_type in ("group", "supergroup"):
        if chat_id not in ALLOWED_GROUPS:
            ALLOWED_GROUPS.append(chat_id)
            save_group_whitelist()
            print(f"새 그룹 등록: {chat_id}")

        # 다른 팀 봇 메시지 → 자율 반응 가능
        bot_code = is_team_bot_message(update)
        if bot_code:
            await handle_group_message(update, context, user_msg, bot_code)
            return

        # 사람 메시지
        sender = update.effective_user
        if not sender:
            return
        if sender.id not in ALLOWED_USERS:
            return

        # 대표님 메시지 - STOP/일반 처리
        action = on_human_message(chat_id, user_msg)
        if action == "stop":
            await update.message.reply_text("네 대표님~ 픽시 조용히 할게 🦋")
            append_group_message(chat_id, "human", user_msg, update.message.message_id)
            return

        # 멘션 또는 전체 호출 (force=True)
        if is_mentioned(user_msg) or is_all_call(user_msg):
            await handle_group_message(update, context, user_msg, "human", force=True)
            return

        # 멘션 없는 일반 메시지도 공유 로그에 저장
        append_group_message(chat_id, "human", user_msg, update.message.message_id)
        return

    # === 1:1 모드 ===
    if update.effective_user.id not in ALLOWED_USERS:
        return

    # 타이머 감지
    timer_keywords = ["분 뒤", "분 후", "시간 뒤", "시간 후", "초 뒤", "초 후", "타이머", "알려줘", "알림"]
    if any(kw in user_msg for kw in timer_keywords):
        seconds, msg = parse_timer(user_msg)
        if seconds:
            await set_timer(update, context, seconds, msg)
            return

    if chat_id not in conversations:
        conversations[chat_id] = []
    conversations[chat_id].append({"role": "user", "content": user_msg})
    if len(conversations[chat_id]) > 40:
        conversations[chat_id] = conversations[chat_id][-40:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversations[chat_id]
    reply = await call_api(messages)
    conversations[chat_id].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)


def main():
    load_group_whitelist()
    print(f"등록된 그룹: {ALLOWED_GROUPS}")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("reload", reload))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("timers", timer_list))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("pixie bot started (1:1 + 그룹 모드)")
    app.run_polling(allowed_updates=["message"], drop_pending_updates=True)


if __name__ == "__main__":
    main()
