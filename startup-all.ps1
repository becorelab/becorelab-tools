# Becorelab Auto-Startup Script
# Called by Task Scheduler at logon (can also run manually)
# Order: Cleanup -> Chrome CDP -> Doori -> Lena

chcp 65001 > $null
$ErrorActionPreference = "Continue"

# Wait for network/drive after logon
Start-Sleep -Seconds 10

Write-Host "=== Becorelab Startup ===" -ForegroundColor Cyan
Write-Host ""

# --- 0. Cleanup: Kill previous sessions before starting new ones ---
Write-Host "[0/3] Cleaning up previous sessions..." -ForegroundColor Yellow
& "C:\Users\info\ClaudeAITeam\cleanup-processes.ps1"
Write-Host "  Cleanup done" -ForegroundColor Green
Write-Host ""

# --- 1. Chrome CDP (port 9222) ---
Write-Host "[1/3] Chrome CDP (9222)..." -ForegroundColor Yellow
$chromeExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$mioProfile = "$env:LOCALAPPDATA\Google\Chrome\User Data - Mio"

# Kill existing process on port 9222
$existing = Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    $existing | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

Start-Process -FilePath $chromeExe -WindowStyle Minimized -ArgumentList @(
    "--remote-debugging-port=9222",
    "--user-data-dir=`"$mioProfile`"",
    "--no-first-run",
    "--no-default-browser-check",
    "--start-minimized"
)
Write-Host "  Chrome CDP started (minimized)" -ForegroundColor Green
Start-Sleep -Seconds 3

# --- 2. Doori session (separate window) ---
Write-Host "[2/3] Doori session..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", "C:\Users\info\claudeaiteam\start-doori.ps1"
)
Write-Host "  Doori window launched" -ForegroundColor Green
Start-Sleep -Seconds 5

# --- 3. Lena session (separate window) ---
Write-Host "[3/3] Lena session..." -ForegroundColor Yellow
$lenaProc = Start-Process cmd -ArgumentList @(
    "/k",
    "C:\Users\info\claudeaiteam\Channel_lena\run_lena.bat"
) -PassThru
# Save Lena PID for cleanup next time
if ($lenaProc) { $lenaProc.Id | Set-Content $LenaPidFile }
Write-Host "  Lena window launched" -ForegroundColor Green

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
Write-Host "All sessions loading in their windows..." -ForegroundColor White
Write-Host "This window closes in 10 seconds." -ForegroundColor Gray
Start-Sleep -Seconds 10
