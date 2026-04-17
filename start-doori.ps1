# 두리(클로드 채널) 시작 스크립트 — 중복 방지
Write-Host "=== 두리 시작 준비 ===" -ForegroundColor Cyan

# 1. 기존 두리 관련 프로세스 정리 (하치 제외)
chcp 65001 > $null
$mainClaude = Get-Process claude -ErrorAction SilentlyContinue | Sort-Object WorkingSet64 -Descending | Select-Object -First 1
Get-Process claude -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $mainClaude.Id } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process bun -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "기존 프로세스 정리 완료" -ForegroundColor Green

# 2. 3초 대기 (텔레그램 polling 해제)
Start-Sleep -Seconds 3

# 3. 409 체크
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

# 4. 두리 시작
Set-Location "C:\Users\info\claudeaiteam"
& "C:\Users\info\AppData\Roaming\npm\claude.cmd" --channels "plugin:telegram@claude-plugins-official" --dangerously-skip-permissions --model opus
