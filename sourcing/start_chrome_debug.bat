@echo off
echo [BECORELAB] Chrome 디버그 모드로 시작합니다...
echo [BECORELAB] 기존 Chrome을 모두 닫고 디버그 모드로 재시작합니다.
echo.
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 >nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data"
echo [BECORELAB] Chrome이 포트 9222에서 디버그 모드로 실행됩니다.
echo [BECORELAB] 헬프스토어 확장 프로그램 + 쿠팡윙 로그인 확인 후 스캔해주세요.
pause
