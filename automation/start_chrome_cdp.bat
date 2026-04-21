@echo off
REM Chrome CDP 모드 실행 (소싱앱 크롤링용 — 헬프스토어 확장 포함)
set HELPSTORE_DIR=C:\Users\User\ChromeCDP\Default\Extensions\nfbjgieajobfohijlkaaplipbiofblef
for /d %%v in ("%HELPSTORE_DIR%\*") do set HELPSTORE_VER=%%v
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="C:\Users\User\ChromeCDP" --load-extension="%HELPSTORE_VER%" --no-first-run
