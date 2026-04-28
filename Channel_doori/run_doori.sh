#!/bin/bash
# 두리 Claude Code 세션 런처 (macOS)
cd "$(dirname "$0")"

export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
export TELEGRAM_BOT_TOKEN="8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"
export TELEGRAM_STATE_DIR="$HOME/.claude/channels/telegram-doori"

# 이전 세션 좀비 프로세스 제거 (CPU 100% 폭주 방지)
pkill -f "bun.*server.ts" 2>/dev/null && echo "[DOORI] 이전 좀비 프로세스 제거 완료" && sleep 2

echo "[DOORI] Starting Claude Code with Doori bot..."
echo ""

claude --channels "plugin:telegram@claude-plugins-official" \
  --dangerously-skip-permissions \
  --model sonnet
