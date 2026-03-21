@echo off
chcp 65001 >nul
:: 비코어랩 소싱콕 — 집 PC 시작 스크립트

:: 1. 기존 서버 종료
echo [소싱콕] 기존 서버 정리 중...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 >nul

:: 2. Chrome CDP 모드 시작
echo [소싱콕] Chrome CDP 모드 시작 중...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 >nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir=C:\Temp\ChromeDebug
timeout /t 3 >nul

:: 3. 소싱콕 서버 시작
echo [소싱콕] 서버 시작 중...
cd /d C:\Users\pnp28\claude\sourcing
start /min python analyzer\app.py

timeout /t 4 >nul
echo.
echo [소싱콕] 시작 완료!
echo [소싱콕] http://localhost:8090
echo.
echo ※ Chrome에서 coupang.com 로그인 후 상세 분석 사용 가능
pause
