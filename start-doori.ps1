# 두리(클로드 채널) 시작 스크립트 — 중복/고아 프로세스 방지
# 핵심: PID 파일 + taskkill /T (자식 프로세스 트리까지 종료)

$PIDFile = "C:\Users\info\ClaudeAITeam\Channel_doori\doori.pid"
$DooriWorkDir = "C:\Users\info\ClaudeAITeam\Channel_doori"

Write-Host "=== 두리 시작 준비 ===" -ForegroundColor Cyan
chcp 65001 > $null

# 1. 기존 두리 프로세스 트리 종료 (PID 파일 기반)
#    taskkill /T = 자식 프로세스까지 함께 종료 (cmd → node → bun 체인)
if (Test-Path $PIDFile) {
    $oldPid = (Get-Content $PIDFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($oldPid -match '^\d+$') {
        $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "기존 두리 트리 종료: PID $oldPid (+ 자식 node/bun)" -ForegroundColor Yellow
            & taskkill.exe /F /T /PID $oldPid 2>&1 | Out-Null
            Start-Sleep -Seconds 2
        } else {
            Write-Host "PID 파일의 프로세스 이미 종료됨" -ForegroundColor Gray
        }
    }
}

# 2. 고아 텔레그램 bun 정리 (부모 프로세스 없는 bun)
#    claude node를 죽여도 bun이 살아남는 현상 방지
$orphanBuns = Get-WmiObject Win32_Process -Filter "Name='bun.exe'" | Where-Object {
    $_.CommandLine -match 'telegram.*start' -and
    -not (Get-Process -Id $_.ParentProcessId -ErrorAction SilentlyContinue)
}

foreach ($b in $orphanBuns) {
    Write-Host "고아 bun 정리: PID $($b.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $b.ProcessId -Force -ErrorAction SilentlyContinue
}

# 3. 텔레그램 409 체크
Write-Host "텔레그램 409 체크..." -ForegroundColor Yellow
$token = "8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"
try {
    $result = Invoke-RestMethod "https://api.telegram.org/bot$token/getUpdates?limit=1&timeout=2" -TimeoutSec 5
    if ($result.ok) {
        Write-Host "텔레그램 정상! 두리 시작합니다..." -ForegroundColor Green
    }
} catch {
    Write-Host "텔레그램 체크 실패, 그래도 시작합니다..." -ForegroundColor Yellow
}

# 4. 두리 시작 (run_doori.bat을 통해 cmd 셸에서)
#    cmd.exe PID 를 저장 → 다음 재시작 때 taskkill /T 로 트리 전체 종료 가능
Write-Host "두리 세션 시작 중..." -ForegroundColor Cyan
$proc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "$DooriWorkDir\run_doori.bat" `
    -WorkingDirectory $DooriWorkDir `
    -WindowStyle Minimized `
    -PassThru

# 5. PID 파일에 cmd.exe PID 저장 (launcher PID)
if ($proc -and $proc.Id) {
    $proc.Id | Out-File $PIDFile -Encoding ascii
    Write-Host "두리 시작 완료: launcher PID $($proc.Id)" -ForegroundColor Green
    Write-Host "   PID 파일: $PIDFile" -ForegroundColor Gray
} else {
    Write-Host "두리 시작 실패 — Start-Process가 PID를 반환하지 않음" -ForegroundColor Red
}
