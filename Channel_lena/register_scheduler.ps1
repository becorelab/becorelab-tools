# 레나 자동화 스케줄러 등록
# - 폴러: 5분마다
# - 정기 보고: 매일 11:00, 17:00
# 관리자 권한 필요 없음 (사용자 영역 작업)

$pythonExe = "C:\Users\info\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"  # 콘솔창 없이 백그라운드 실행
$lenaDir = "C:\Users\info\ClaudeAITeam\Channel_lena"

# 1. 기존 작업 삭제 (재등록 대비)
Unregister-ScheduledTask -TaskName "Lena_Poller" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "Lena_Summary_AM" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "Lena_Summary_PM" -Confirm:$false -ErrorAction SilentlyContinue

# 공통 액션 빌더
function New-LenaAction($script) {
    New-ScheduledTaskAction `
        -Execute $pythonExe `
        -Argument "$lenaDir\$script" `
        -WorkingDirectory $lenaDir
}

# 2. 폴러 — 5분 주기
$pollerAction = New-LenaAction "lena_poller.py"
$pollerTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)
$pollerSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "Lena_Poller" `
    -Action $pollerAction `
    -Trigger $pollerTrigger `
    -Settings $pollerSettings `
    -Description "레나 알리바바 인박스 폴링 (5분 주기)" | Out-Null

Write-Host "Lena_Poller 등록 완료 (5분 주기)" -ForegroundColor Green

# 3. 오전 보고 — 11:00
$amAction = New-LenaAction "lena_summary.py"
$amTrigger = New-ScheduledTaskTrigger -Daily -At 11:00am
Register-ScheduledTask `
    -TaskName "Lena_Summary_AM" `
    -Action $amAction `
    -Trigger $amTrigger `
    -Settings $pollerSettings `
    -Description "레나 오전 11시 정기 보고" | Out-Null

Write-Host "Lena_Summary_AM 등록 완료 (매일 11:00)" -ForegroundColor Green

# 4. 오후 보고 — 17:00
$pmAction = New-LenaAction "lena_summary.py"
$pmTrigger = New-ScheduledTaskTrigger -Daily -At 5:00pm
Register-ScheduledTask `
    -TaskName "Lena_Summary_PM" `
    -Action $pmAction `
    -Trigger $pmTrigger `
    -Settings $pollerSettings `
    -Description "레나 오후 17시 정기 보고" | Out-Null

Write-Host "Lena_Summary_PM 등록 완료 (매일 17:00)" -ForegroundColor Green
Write-Host ""
Write-Host "=== 등록된 레나 작업 목록 ===" -ForegroundColor Cyan
Get-ScheduledTask -TaskName "Lena_*" | Select-Object TaskName, State, @{N='NextRun';E={(Get-ScheduledTaskInfo $_).NextRunTime}}
