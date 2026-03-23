@echo off
REM 서비스 헬스체크 — 죽었으면 자동 재시작

REM 물류 서버 (8082)
netstat -ano | findstr ":8082.*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] 물류 서버 재시작 >> C:\Users\info\ClaudeAITeam\logistics\data\healthcheck.log
    cd /d C:\Users\info\ClaudeAITeam
    start /b "" C:\Users\info\AppData\Local\Python\pythoncore-3.14-64\python.exe logistics\logistics_app.py
)

REM 허브 서버 (8000)
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] 허브 서버 재시작 >> C:\Users\info\ClaudeAITeam\logistics\data\healthcheck.log
    start /b "" C:\Users\info\AppData\Local\Python\pythoncore-3.14-64\python.exe -m http.server 8000 --directory C:\Users\info\ClaudeAITeam\hub
)

REM OpenClaw 게이트웨이 (18789)
netstat -ano | findstr ":18789.*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] OpenClaw 게이트웨이 재시작 >> C:\Users\info\ClaudeAITeam\logistics\data\healthcheck.log
    start /b "" C:\Users\info\AppData\Roaming\npm\openclaw.cmd gateway
    REM 게이트웨이 시작 후 브라우저도 시작
    timeout /t 15 /nobreak >nul
    start /b "" C:\Users\info\AppData\Roaming\npm\openclaw.cmd browser start
)

REM 두리 텔레그램 채널 (Claude Code) — lock 파일로 실행 여부 확인
set DOORI_LOCK=C:\Users\info\ClaudeAITeam\Channel_doori\.doori.lock
set DOORI_ALIVE=0
if exist "%DOORI_LOCK%" (
    set /p DOORI_PID=<"%DOORI_LOCK%"
    powershell -NoProfile -Command "if (Get-Process -Id %DOORI_PID% -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
    if not errorlevel 1 set DOORI_ALIVE=1
)
if "%DOORI_ALIVE%"=="0" (
    echo [%date% %time%] 두리 채널 재시작 >> C:\Users\info\ClaudeAITeam\logistics\data\healthcheck.log
    start "두리 채널 (자동재시작)" /min cmd /c C:\Users\info\ClaudeAITeam\start-doori-channel.bat
)
