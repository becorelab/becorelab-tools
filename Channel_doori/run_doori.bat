@echo off
REM 두리 Claude Code 세션 런처
REM 두리 봇 토큰 환경변수 주입 + plugin:telegram 채널 수신 활성화
chcp 65001 >nul
cd /d "%~dp0"
set "TELEGRAM_BOT_TOKEN=8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"
echo [DOORI] Starting Claude Code with Doori bot...
echo.
claude --channels "plugin:telegram@claude-plugins-official" --dangerously-skip-permissions --model opus
