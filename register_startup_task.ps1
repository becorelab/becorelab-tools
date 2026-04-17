# 비코어랩 스타트업 Task Scheduler 등록
# 한 번만 실행하면 됨. 이후 로그온 시마다 자동 실행.

$taskName = "Becorelab_Startup"
$scriptPath = "C:\Users\info\claudeaiteam\startup-all.ps1"

Write-Host "=== $taskName Task Scheduler 등록 ===" -ForegroundColor Cyan

# 기존 작업 삭제
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# 액션: PowerShell로 startup-all.ps1 실행
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$scriptPath`""

# 트리거: 현재 사용자 로그온 시
# (지연은 startup-all.ps1 내부의 Start-Sleep으로 처리)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"

# 설정
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

# 등록
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "비코어랩 자동 시작: Chrome CDP(9222) + 두리 + 레나" | Out-Null

Write-Host "$taskName 등록 완료!" -ForegroundColor Green
Write-Host ""
Write-Host "=== 등록 정보 확인 ===" -ForegroundColor Cyan
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State, @{
    N='NextRun'; E={(Get-ScheduledTaskInfo $_).NextRunTime}
}

Write-Host ""
Write-Host "다음 대표님 로그온 시 자동 실행됩니다." -ForegroundColor White
Write-Host "지금 바로 테스트: schtasks /run /tn `"$taskName`"" -ForegroundColor Gray
