@echo off
REM 두리 Claude Code 세션 런처
chcp 65001 >nul
cd /d "%~dp0"
set "TELEGRAM_BOT_TOKEN=8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"
set "TELEGRAM_STATE_DIR=C:\Users\info\.claude\channels\telegram-doori"
set "TELEGRAM_ACCESS_MODE=static"
echo [DOORI] Starting Claude Code with Doori bot...
echo.
"C:\Users\info\AppData\Roaming\npm\claude.cmd" --channels "plugin:telegram@claude-plugins-official" --dangerously-skip-permissions --model sonnet
