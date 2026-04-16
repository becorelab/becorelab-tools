@echo off
chcp 65001 >nul
echo [BECORELAB] Starting Mio Chrome (CDP mode on port 9222)...
echo.

REM Kill only existing CDP listener on port 9222 (regular Chrome untouched)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":9222" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Launch Chrome with separate profile (no conflict with main Chrome)
set "MIO_PROFILE=%LOCALAPPDATA%\Google\Chrome\User Data - Mio"
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%MIO_PROFILE%" --no-first-run --no-default-browser-check

echo [BECORELAB] Chrome launched on port 9222.
echo [BECORELAB] Please log in to alibaba.com in this new Chrome window.
echo [BECORELAB] Your regular Chrome is untouched.
echo.
pause
