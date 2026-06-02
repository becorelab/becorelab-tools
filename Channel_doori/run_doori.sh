#!/bin/bash
# 두리 Claude Code 세션 런처 (macOS)
# launchd 헤드리스 환경에서 pseudo-TTY를 통해 claude --channels를 실행
cd "$(dirname "$0")"

export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export TELEGRAM_STATE_DIR="$HOME/.claude/channels/telegram-doori"

# TELEGRAM_BOT_TOKEN은 ~/.claude/channels/telegram-doori/.env 에서 로드됨
# (pty_launcher.py 및 server.ts 공통)

# 이전 세션 좀비 프로세스 제거 (CPU 100% 폭주 방지)
pkill -f "bun.*server.ts" 2>/dev/null && echo "[DOORI] 이전 좀비 프로세스 제거 완료" && sleep 2
pkill -f "pty_launcher.py" 2>/dev/null

echo "[DOORI] Starting Claude Code with Doori bot (PTY mode)..."

# launchd는 TTY 없이 실행되므로 claude가 --print 모드로 빠지는 것을 방지하기 위해
# Python PTY 래퍼를 사용해 pseudo-TTY를 할당한 뒤 claude를 실행
exec /usr/bin/python3 "$(dirname "$0")/pty_launcher.py"
