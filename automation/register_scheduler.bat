@echo off
REM 비코어랩 새벽 자동화 - Windows 작업 스케줄러 등록
REM 매일 03:50에 실행

schtasks /create /tn "BecorelabMorningCollect" ^
    /tr "\"C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe\" \"C:\Users\User\ClaudeAITeam\automation\morning_collect.py\"" ^
    /sc DAILY /st 03:50 ^
    /ru "%USERNAME%" ^
    /f

echo.
echo 등록 완료: 매일 03:50 실행
echo 확인: schtasks /query /tn "BecorelabMorningCollect"
pause
