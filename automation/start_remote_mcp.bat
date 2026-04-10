@echo off
REM 비코어랩 Remote MCP 서버 시작 스크립트
REM PC 부팅 시 자동 실행 (Windows 작업 스케줄러)

cd /d C:\Users\info\ClaudeAITeam\mcp-server

REM 기존 프로세스 정리
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8500" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a 2>nul
)

REM 가상환경 Python으로 SSE 서버 실행
start "becorelab_remote_mcp" /B ".venv\Scripts\python.exe" server_remote.py > C:\Users\info\ClaudeAITeam\data\remote_mcp.log 2>&1

REM Tailscale Funnel 활성화 (이미 켜져있으면 무시됨)
timeout /t 3 /nobreak >nul
tailscale funnel --bg --set-path / http://localhost:8500 >nul 2>&1

echo Remote MCP server started on port 8500
echo Funnel: https://ky.taile569b3.ts.net/sse
