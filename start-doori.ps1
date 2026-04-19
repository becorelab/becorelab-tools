# Doori (Claude Channel) Startup Script
# Lena-identical: foreground execution in dedicated PowerShell window
# PID tracking: launcher saves this PowerShell's PID → taskkill /T kills entire tree

$DooriWorkDir = "C:\Users\info\ClaudeAITeam\Channel_doori"
$DooriToken = "8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"
$StateDir = "C:\Users\info\.claude\channels\telegram-doori"
$PidFile = "$DooriWorkDir\doori.pid"

Write-Host "=== Doori Startup ===" -ForegroundColor Cyan

# Save this PowerShell's PID (taskkill /T on this kills claude+bun tree)
$PID | Set-Content $PidFile

# 1. Cleanup orphan bun processes (parent dead)
Get-WmiObject Win32_Process -Filter "Name='bun.exe'" | Where-Object {
    $_.CommandLine -match 'telegram.*start' -and
    -not (Get-Process -Id $_.ParentProcessId -ErrorAction SilentlyContinue)
} | ForEach-Object {
    Write-Host "Cleaning orphan bun: PID $($_.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

# 2. Telegram bot status check
Write-Host "Checking telegram bot status..." -ForegroundColor Yellow
try {
    $result = Invoke-RestMethod "https://api.telegram.org/bot$DooriToken/getMe" -TimeoutSec 5
    if ($result.ok) {
        Write-Host "Doori bot OK: @$($result.result.username)" -ForegroundColor Green
    }
} catch {
    Write-Host "Telegram check failed, continuing anyway..." -ForegroundColor Yellow
}

# 3. Environment variables — doori-specific token + isolated state directory
$env:TELEGRAM_BOT_TOKEN = $DooriToken
$env:TELEGRAM_STATE_DIR = $StateDir
$env:TELEGRAM_ACCESS_MODE = "static"

# State directory setup + access.json
if (-not (Test-Path $StateDir)) {
    New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
    New-Item -ItemType Directory -Path "$StateDir\inbox" -Force | Out-Null
    New-Item -ItemType Directory -Path "$StateDir\approved" -Force | Out-Null
    $accessJson = '{"dmPolicy":"allowlist","allowFrom":["8708718261"],"groups":{},"pending":{}}'
    [System.IO.File]::WriteAllText("$StateDir\access.json", $accessJson, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "Doori state directory initialized: $StateDir" -ForegroundColor Green
}

# 4. Start doori foreground (lena-identical: claude.cmd direct call)
Set-Location $DooriWorkDir
Write-Host "Starting doori session (foreground)..." -ForegroundColor Cyan
& "C:\Users\info\AppData\Roaming\npm\claude.cmd" --channels "plugin:telegram@claude-plugins-official" --dangerously-skip-permissions --model haiku
