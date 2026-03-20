@echo off
REM 서비스 헬스체크 — 죽었으면 자동 재시작

REM 물류 서버 (8082)
netstat -ano | findstr ":8082.*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] 물류 서버 재시작 >> C:\Users\info\ClaudeAITeam\logistics\data\healthcheck.log
    cd /d C:\Users\info\ClaudeAITeam
    start /b "" C:\Users\info\AppData\Local\Python\pythoncore-3.14-64\python.exe logistics\logistics_app.py
)

REM OpenClaw 게이트웨이 (18789)
netstat -ano | findstr ":18789.*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] OpenClaw 게이트웨이 재시작 >> C:\Users\info\ClaudeAITeam\logistics\data\healthcheck.log
    start /b "" C:\Users\info\AppData\Roaming\npm\openclaw.cmd gateway
)
