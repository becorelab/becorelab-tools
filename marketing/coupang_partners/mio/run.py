"""미오 파트너스 세션 실행기.
사용:
  python run.py '채널 UCxxxx 아웃리치 초안 써줘'
  python run.py   ← 대화식 입력
"""
import os
import sys
import anthropic
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_dir, "..", "..", "..", "sourcing", "analyzer", ".env"))
load_dotenv(os.path.join(_dir, "mio.env"))

from tools import dispatch_tool  # noqa: E402


def run_mio(task: str) -> None:
    agent_id = os.environ.get("MIO_PARTNERS_AGENT_ID")
    env_id = os.environ.get("MIO_PARTNERS_ENVIRONMENT_ID")
    if not agent_id or not env_id:
        print("mio.env 없음. setup.py를 먼저 실행하세요.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic()

    print(f"\n{'─' * 54}")
    print(f"미오 파트너스 세션 시작")
    print(f"  요청: {task[:60]}")
    print(f"{'─' * 54}\n")

    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=env_id,
        title=task[:60],
    )
    print(f"세션 ID: {session.id}\n")

    first_turn = True
    while True:
        with client.beta.sessions.events.stream(session_id=session.id) as stream:
            if first_turn:
                client.beta.sessions.events.send(
                    session_id=session.id,
                    events=[{
                        "type": "user.message",
                        "content": [{"type": "text", "text": task}],
                    }],
                )
                first_turn = False

            tool_calls = []
            for event in stream:
                etype = event.type
                if etype == "agent.message":
                    for block in event.content:
                        if block.type == "text":
                            print(block.text, end="", flush=True)
                elif etype == "agent.custom_tool_use":
                    tool_calls.append(event)
                elif etype == "session.status_idle":
                    break
                elif etype == "session.status_terminated":
                    print("\n\n세션 종료.")
                    return
                elif etype == "session.error":
                    print(f"\n\n세션 오류: {event}", file=sys.stderr)
                    return

        if not tool_calls:
            print(f"\n\n{'─' * 54}")
            print("미오 작업 완료")
            print(f"{'─' * 54}")
            return

        results = []
        for call in tool_calls:
            tool_input = call.input if isinstance(call.input, dict) else dict(call.input)
            print(f"\n[툴 호출] {call.name}({list(tool_input.keys())})")
            result_json = dispatch_tool(call.name, tool_input)
            results.append({
                "type": "user.custom_tool_result",
                "custom_tool_use_id": call.id,
                "content": [{"type": "text", "text": result_json}],
            })

        client.beta.sessions.events.send(
            session_id=session.id,
            events=results,
        )


def main():
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = input("요청을 입력하세요: ").strip()
        if not task:
            sys.exit(1)
    run_mio(task)


if __name__ == "__main__":
    main()
