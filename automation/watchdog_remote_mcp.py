"""Remote MCP 서버 watchdog
5분마다 헬스체크 → 죽었으면 자동 재시작
Windows 작업 스케줄러로 5분마다 실행
"""
import os
import sys
import subprocess
import socket
from datetime import datetime

PROJECT_ROOT = r"C:\Users\User\ClaudeAITeam"
START_BAT = os.path.join(PROJECT_ROOT, "automation", "start_remote_mcp.bat")
LOG_FILE = os.path.join(PROJECT_ROOT, "data", "remote_mcp_watchdog.log")
PORT = 8500


def is_alive(port: int, timeout: float = 2.0) -> bool:
    """포트가 LISTENING 상태인지 확인"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def restart():
    """start_remote_mcp.bat 실행"""
    try:
        subprocess.Popen(
            ["cmd", "/c", START_BAT],
            cwd=PROJECT_ROOT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        log(f"재시작 명령 실행: {START_BAT}")
        return True
    except Exception as e:
        log(f"재시작 실패: {e}")
        return False


def main():
    if is_alive(PORT):
        log(f"OK - Remote MCP 서버 정상 (port {PORT})")
        return 0
    else:
        log(f"FAIL - Remote MCP 서버 다운 → 재시작 시도")
        restart()
        return 1


if __name__ == "__main__":
    sys.exit(main())
