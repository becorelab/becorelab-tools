"""미오 파트너스 에이전트 새 버전 배포.

setup.py의 SYSTEM_PROMPT / TOOLS를 수정한 뒤 이 스크립트를 실행하면
기존 agent_id에 새 버전이 추가된다. mio.env의 VERSION만 갱신.
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

from setup import SYSTEM_PROMPT, TOOLS  # noqa: E402


def _write_env(agent_id: str, version, env_id: str):
    path = os.path.join(_dir, "mio.env")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"MIO_PARTNERS_AGENT_ID={agent_id}\n")
        f.write(f"MIO_PARTNERS_AGENT_VERSION={version}\n")
        f.write(f"MIO_PARTNERS_ENVIRONMENT_ID={env_id}\n")


def main():
    agent_id = os.environ.get("MIO_PARTNERS_AGENT_ID")
    env_id = os.environ.get("MIO_PARTNERS_ENVIRONMENT_ID")
    if not agent_id or not env_id:
        print("mio.env 없음. setup.py를 먼저 실행하세요.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic()

    # 현재 버전 조회
    current = client.beta.agents.retrieve(agent_id=agent_id)
    current_version = getattr(current, "version", None)
    print(f"기존 agent {agent_id} (현재 v{current_version}) 업데이트 중...\n")

    agent = client.beta.agents.update(
        agent_id=agent_id,
        version=current_version,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
    )

    new_version = getattr(agent, "version", None)
    print(f"신규 버전: v{new_version}\n")

    _write_env(agent_id, new_version, env_id)
    print("mio.env 갱신 완료.")


if __name__ == "__main__":
    main()
