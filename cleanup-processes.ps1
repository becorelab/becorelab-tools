# cleanup-processes.ps1
# 기존 프로세스 정리 스크립트 (becorelab-start.vbs 및 startup-all.ps1에서 호출)

$ErrorActionPreference = "Continue"

# 1. 포트 기반 중복 체크 — 이미 해당 포트에서 실행 중이면 kill
@(8000, 8082, 8090, 9222) | ForEach-Object {
    $port = $_
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $conn | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

# 2. PID 파일 기반 정리 (두리/레나)
@(
    "C:\Users\info\ClaudeAITeam\Channel_doori\doori.pid",
    "C:\Users\info\ClaudeAITeam\Channel_lena\lena.pid"
) | ForEach-Object {
    if (Test-Path $_) {
        $oldPid = Get-Content $_ -ErrorAction SilentlyContinue
        if ($oldPid) {
            taskkill /PID $oldPid /T /F 2>$null | Out-Null
        }
        Remove-Item $_ -Force -ErrorAction SilentlyContinue
    }
}

# 3. 고아 claude/bun 프로세스 정리
Get-WmiObject Win32_Process | Where-Object {
    ($_.CommandLine -match 'claude\.cmd.*telegram' -or $_.CommandLine -match 'bun.*telegram') -and
    -not (Get-Process -Id $_.ParentProcessId -ErrorAction SilentlyContinue)
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2
