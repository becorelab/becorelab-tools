# Doori (Claude Channel) Startup Script
# Prevents duplicate processes + cleans orphan bun processes
# Strategy: PID file + taskkill /T (terminate child process tree)

$PIDFile = "C:\Users\info\ClaudeAITeam\Channel_doori\doori.pid"
$DooriWorkDir = "C:\Users\info\ClaudeAITeam\Channel_doori"
$DooriToken = "8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"

Write-Host "=== Doori Startup ===" -ForegroundColor Cyan
chcp 65001 > $null

# 1. Kill existing doori process tree (PID file based)
if (Test-Path $PIDFile) {
    $oldPid = (Get-Content $PIDFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($oldPid -match '^\d+$') {
        $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Killing old doori tree: PID $oldPid (with children)" -ForegroundColor Yellow
            & taskkill.exe /F /T /PID $oldPid 2>&1 | Out-Null
            Start-Sleep -Seconds 2
        } else {
            Write-Host "Old PID already dead" -ForegroundColor Gray
        }
    }
}

# 2. Cleanup orphan telegram bun processes (parent dead)
$orphanBuns = Get-WmiObject Win32_Process -Filter "Name='bun.exe'" | Where-Object {
    $_.CommandLine -match 'telegram.*start' -and
    -not (Get-Process -Id $_.ParentProcessId -ErrorAction SilentlyContinue)
}

foreach ($b in $orphanBuns) {
    Write-Host "Cleaning orphan bun: PID $($b.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $b.ProcessId -Force -ErrorAction SilentlyContinue
}

# 3. Telegram 409 conflict check
Write-Host "Checking telegram bot status..." -ForegroundColor Yellow
$url = "https://api.telegram.org/bot" + $DooriToken + "/getUpdates?limit=1" + [char]38 + "timeout=2"
try {
    $result = Invoke-RestMethod $url -TimeoutSec 5
    if ($result.ok) {
        Write-Host "Telegram OK, starting doori..." -ForegroundColor Green
    }
} catch {
    Write-Host "Telegram check failed, continuing anyway..." -ForegroundColor Yellow
}

# 4. Start doori via cmd.exe + run_doori.bat
Write-Host "Starting doori session..." -ForegroundColor Cyan
$proc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "$DooriWorkDir\run_doori.bat" `
    -WorkingDirectory $DooriWorkDir `
    -WindowStyle Minimized `
    -PassThru

# 5. Save launcher PID to file (cmd.exe PID, used for taskkill /T later)
if ($proc -and $proc.Id) {
    $proc.Id | Out-File $PIDFile -Encoding ascii
    Write-Host "Doori started: launcher PID $($proc.Id)" -ForegroundColor Green
    Write-Host "PID file: $PIDFile" -ForegroundColor Gray
} else {
    Write-Host "Doori start FAILED - Start-Process returned no PID" -ForegroundColor Red
}
