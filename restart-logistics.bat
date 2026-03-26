@echo off
title 물류 서버 재시작
echo 물류 서버(8082) 재시작 중...

:: 8082 포트 프로세스 종료
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8082 "') do (
    echo PID %%a 종료 중...
    taskkill /F /PID %%a 2>nul
)

timeout /t 2 /nobreak

:: 물류 서버 재시작
cd /d C:\Users\info\ClaudeAITeam
start "물류서버(8082)" C:\Users\info\AppData\Local\Python\pythoncore-3.14-64\python.exe logistics\logistics_app.py

echo 재시작 완료! 5초 후 창 닫힘
timeout /t 5 /nobreak
