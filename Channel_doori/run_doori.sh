#!/bin/bash
# 두리 Claude Code 세션 런처 (macOS)
cd "$(dirname "$0")"

export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
export TELEGRAM_BOT_TOKEN="8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"
export TELEGRAM_STATE_DIR="$HOME/.claude/channels/telegram-doori"

echo "[DOORI] Starting Claude Code with Doori bot..."
echo ""

claude --channels "plugin:telegram@claude-plugins-official" \
  --dangerously-skip-permissions \
  --model sonnet
