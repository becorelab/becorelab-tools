@echo off
:: 마켓 파인더 Windows 작업 스케줄러 등록 (관리자 권한으로 실행)
echo 마켓 파인더 자동 시작 등록 중...

schtasks /create /tn "비코어랩 마켓파인더" ^
  /tr "C:\Users\pnp28\claude\sourcing\start_market_finder.bat" ^
  /sc ONLOGON ^
  /ru "%USERNAME%" ^
  /rl LIMITED ^
  /f

if %ERRORLEVEL% == 0 (
    echo.
    echo [성공] 부팅 후 자동 시작 등록 완료!
    echo 앱 주소: http://localhost:8090
) else (
    echo.
    echo [실패] 관리자 권한으로 다시 실행해주세요.
    echo 이 파일을 우클릭 - "관리자 권한으로 실행" 선택
)
pause
