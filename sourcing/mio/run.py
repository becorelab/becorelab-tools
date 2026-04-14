"""
미오 세션 실행기
알리바바 소싱 요청을 미오에게 전달하고 결과를 스트리밍으로 받습니다.

사용법:
    python run.py '배수구 트랩 소싱해줘'
    python run.py '스테인리스 식기 건조대, MOQ 200개 이하, FOB $3 이하'
    python run.py   ← 대화식 입력
"""
import os
import sys
import anthropic
from dotenv import load_dotenv

_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_dir, '..', 'analyzer', '.env'))
load_dotenv(os.path.join(_dir, 'mio.env'))

from tools import dispatch_tool   # noqa: E402 — 경로 설정 후 임포트


def run_mio(task: str) -> None:
    agent_id = os.environ.get("MIO_AGENT_ID")
    env_id   = os.environ.get("MIO_ENVIRONMENT_ID")

    if not agent_id or not env_id:
        print("❌ mio.env 없음. setup.py를 먼저 실행하세요.")
        sys.exit(1)

    client = anthropic.Anthropic()

    print(f"\n{'─' * 54}")
    print(f"🤖 미오 소싱 시작")
    print(f"   요청: {task[:60]}")
    print(f"{'─' * 54}\n")

    # ── 세션 생성 ────────────────────────────────────────────
    session = client.beta.sessions.create(
        agent=agent_id,          # 최신 버전 사용 (문자열 단축형)
        environment_id=env_id,
        title=task[:60],
    )
    print(f"세션 ID: {session.id}\n")

    first_turn = True

    # ── 메인 이벤트 루프 ─────────────────────────────────────
    # 패턴: 스트림 열기 → (첫 턴) 메시지 전송 → 이벤트 처리
    #       → 커스텀 툴 호출 시: 스트림 닫기 → 툴 실행 → 결과 전송 → 재연결
    while True:
        with client.beta.sessions.events.stream(session_id=session.id) as stream:

            # 첫 번째 턴: 스트림 먼저 열고 메시지 전송 (stream-first)
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

                if etype == "agent.thinking":
                    # 미오의 사고 과정 표시
                    thinking_text = getattr(event, 'thinking', '') or getattr(event, 'content', '')
                    if thinking_text:
                        print(f"\n💭 [미오 생각 중...]\n{thinking_text}\n{'─'*40}", flush=True)

                elif etype == "agent.message":
                    for block in event.content:
                        if block.type == "text":
                            print(block.text, end="", flush=True)

                elif etype == "agent.custom_tool_use":
                    # 미오가 Playwright 툴 호출 → 세션은 idle로 전환 대기
                    tool_calls.append(event)

                elif etype == "session.status_idle":
                    # tool_calls 있으면 requires_action, 없으면 완료
                    break

                elif etype == "session.status_terminated":
                    print("\n\n세션 종료.")
                    return

                elif etype == "session.error":
                    print(f"\n\n❌ 세션 오류: {event}")
                    return

                # session.status_running / span.* / agent.thinking 등은 무시

        # ── 툴 호출 없음 → 작업 완료 ─────────────────────────
        if not tool_calls:
            print(f"\n\n{'─' * 54}")
            print("✅ 미오 작업 완료!")
            print(f"{'─' * 54}")
            return

        # ── 툴 실행 → 결과 전송 ──────────────────────────────
        results = []
        for call in tool_calls:
            # call.input: SDK 반환 타입 → dict 변환
            tool_input = call.input if isinstance(call.input, dict) else dict(call.input)
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
        # 다음 while 이터레이션에서 새 스트림 오픈 → 에이전트 응답 수신


def main():
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = input("소싱 요청을 입력하세요: ").strip()
        if not task:
            print("소싱 요청을 입력해주세요.")
            sys.exit(1)

    run_mio(task)


if __name__ == "__main__":
    main()
