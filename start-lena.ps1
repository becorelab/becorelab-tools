# 레나(클로드 채널) 시작 스크립트 — 알리바바 소싱 협상 담당
# 봇: @becorelab_lena_bot (8663458998)
Write-Host "=== 레나 시작 준비 ===" -ForegroundColor Cyan

# 1. 레나 봇만 사용하는 텔레그램 인스턴스 정리 (메인 하치 세션 건드리지 않음)
#    하치 세션은 두리 토큰(8621050278)을 .env에서 읽기 때문에
#    레나는 환경변수로 다른 토큰을 주입하면 같은 PC에서도 충돌 없음
Get-Process bun -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*Channel_lena*"
} | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "기존 레나 bun 프로세스 정리 완료" -ForegroundColor Green

Start-Sleep -Seconds 2

# 2. 레나 봇 토큰 정상 동작 체크
$lenaToken = "8663458998:AAEEnXYWJhq98o2PfoBuqVxbe7JOUvJZYxc"
Write-Host "레나 봇 텔레그램 체크..." -ForegroundColor Yellow
try {
    $result = Invoke-RestMethod "https://api.telegram.org/bot$lenaToken/getMe" -TimeoutSec 5
    if ($result.ok) {
        Write-Host "레나 봇 정상: @$($result.result.username)" -ForegroundColor Green
    }
} catch {
    Write-Host "레나 봇 체크 실패, 그래도 시작합니다..." -ForegroundColor Yellow
}

# 3. 환경변수 주입 — 레나 전용 토큰 + 별도 state 디렉토리
$env:TELEGRAM_BOT_TOKEN = $lenaToken
$env:TELEGRAM_STATE_DIR = "C:\Users\info\.claude\channels\telegram-lena"
$env:TELEGRAM_ACCESS_MODE = "static"

# 별도 state 디렉토리 생성 + access.json 셋업 (대표님 chat만 허용)
if (-not (Test-Path $env:TELEGRAM_STATE_DIR)) {
    New-Item -ItemType Directory -Path $env:TELEGRAM_STATE_DIR -Force | Out-Null
    New-Item -ItemType Directory -Path "$env:TELEGRAM_STATE_DIR\inbox" -Force | Out-Null
    New-Item -ItemType Directory -Path "$env:TELEGRAM_STATE_DIR\approved" -Force | Out-Null
    # access.json은 BOM 없는 UTF-8로 (Out-File -Encoding UTF8은 BOM 추가됨!)
    $accessJson = '{"dmPolicy":"allowlist","allowFrom":["8708718261"],"groups":{},"pending":{}}'
    [System.IO.File]::WriteAllText("$env:TELEGRAM_STATE_DIR\access.json", $accessJson, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "레나 state 디렉토리 초기화 완료: $env:TELEGRAM_STATE_DIR" -ForegroundColor Green
}

# 4. 레나 시작
Set-Location "C:\Users\info\ClaudeAITeam\Channel_lena"
& "C:\Users\info\AppData\Roaming\npm\claude.cmd" --channels "plugin:telegram@claude-plugins-official" --dangerously-skip-permissions --model opus
