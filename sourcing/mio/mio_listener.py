"""
미오 상시 대기 리스너
텔레그램 메시지 오면 미오 세션 깨워서 응답
"""
import os
import sys
import time
import traceback
import anthropic
from dotenv import load_dotenv

_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_dir, '..', 'analyzer', '.env'))
load_dotenv(os.path.join(_dir, 'mio.env'))

from tools import dispatch_tool
from mio_telegram import send_message, get_updates, OWNER_CHAT_ID

AGENT_ID = os.environ.get("MIO_AGENT_ID")
ENV_ID = os.environ.get("MIO_ENVIRONMENT_ID")

if not AGENT_ID or not ENV_ID:
    print("❌ mio.env 없음")
    sys.exit(1)


def reply_with_mio(user_text: str) -> str:
    """미오 세션 한 번 돌려서 응답 받기"""
    client = anthropic.Anthropic()
    session = client.beta.sessions.create(
        agent=AGENT_ID,
        environment_id=ENV_ID,
        title=user_text[:60],
    )

    final_text_parts = []
    first_turn = True

    while True:
        with client.beta.sessions.events.stream(session_id=session.id) as stream:
            if first_turn:
                client.beta.sessions.events.send(
                    session_id=session.id,
                    events=[{
                        "type": "user.message",
                        "content": [{"type": "text", "text": user_text}],
                    }],
                )
                first_turn = False

            tool_calls = []
            for event in stream:
                etype = event.type
                if etype == "agent.message":
                    for block in event.content:
                        if block.type == "text":
                            final_text_parts.append(block.text)
                elif etype == "agent.custom_tool_use":
                    tool_calls.append(event)
                elif etype == "session.status_idle":
                    break
                elif etype == "session.status_terminated":
                    return "".join(final_text_parts).strip() or "(빈 응답)"
                elif etype == "session.error":
                    return f"⚠️ 세션 오류: {event}"

        if not tool_calls:
            return "".join(final_text_parts).strip() or "(빈 응답)"

        # 툴 결과 반환 후 다음 턴
        results = []
        for call in tool_calls:
            tool_input = call.input if isinstance(call.input, dict) else dict(call.input)
            result_json = dispatch_tool(call.name, tool_input)
            results.append({
                "type": "user.custom_tool_result",
                "custom_tool_use_id": call.id,
                "content": [{"type": "text", "text": result_json}],
            })
        client.beta.sessions.events.send(session_id=session.id, events=results)
        # 다음 응답은 최종 텍스트만 수집 (중간 툴 나레이션은 버림)
        final_text_parts = []


def _acquire_lock():
    """중복 실행 방지 lock 파일"""
    import tempfile
    lock_path = os.path.join(tempfile.gettempdir(), "mio_listener.lock")
    if os.path.exists(lock_path):
        try:
            old_pid = int(open(lock_path).read().strip())
            import psutil
            if psutil.pid_exists(old_pid):
                print(f"❌ 이미 실행 중 (PID {old_pid}). 종료.")
                sys.exit(1)
        except Exception:
            pass
    with open(lock_path, 'w') as f:
        f.write(str(os.getpid()))
    return lock_path


def main():
    try:
        lock_path = _acquire_lock()
    except ImportError:
        # psutil 없으면 락 없이 진행
        lock_path = None

    print("🐰 미오 리스너 시작됨")
    print(f"   Agent: {AGENT_ID}")
    print(f"   Owner: {OWNER_CHAT_ID}")

    # 시작 시 기존 미수신 메시지는 무시 (최신 offset 잡기)
    initial = get_updates(timeout=1)
    last_update_id = initial[-1]["update_id"] if initial else None

    # 부팅 알림
    send_message("대표님~!! 미오 지금 출근했어요!! 💕 언제든 불러주세요 🥰🌸")

    while True:
        try:
            updates = get_updates(
                offset=(last_update_id + 1) if last_update_id else None,
                timeout=25,
            )
            for update in updates:
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                if msg.get("chat", {}).get("id") != OWNER_CHAT_ID:
                    continue
                text = msg.get("text", "").strip()
                if not text:
                    continue

                print(f"\n📨 대표님 메시지: {text}")
                send_message("미오가 듣고 있어요~ 잠시만 기다려주세요 💕")

                try:
                    reply = reply_with_mio(text)
                    print(f"🐰 미오 응답: {reply[:200]}")
                    # 텔레그램 4096자 제한
                    for i in range(0, len(reply), 3500):
                        send_message(reply[i:i + 3500])
                except Exception as e:
                    err = f"⚠️ 미오가 잠깐 막혔어요 대표님 😥\n{str(e)[:300]}"
                    print(f"❌ {err}")
                    print(traceback.format_exc())
                    send_message(err)

        except KeyboardInterrupt:
            print("\n🛑 리스너 종료")
            break
        except Exception as e:
            print(f"⚠️ 루프 오류: {e}")
            print(traceback.format_exc())
            time.sleep(5)


if __name__ == "__main__":
    main()
