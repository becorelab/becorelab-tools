# Instagram 공동구매 파이프라인 - Windows Task Scheduler 등록

$pythonExe = "C:\Users\info\ClaudeAITeam\mcp-server\.venv\Scripts\python.exe"
$pipelineScript = "C:\Users\info\claudeaiteam\marketing\instagram\pipeline.py"
$workDir = "C:\Users\info\claudeaiteam\marketing\instagram"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

# 1) 크롤 — 평일 09:30 (쿠팡파트너스 크롤 30분 후)
$action1 = New-ScheduledTaskAction -Execute $pythonExe -Argument "$pipelineScript crawl" -WorkingDirectory $workDir
$trigger1 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 9:30am
Register-ScheduledTask -TaskName "InstaGonggu_Crawl" -Action $action1 -Trigger $trigger1 -Settings $settings -Description "Instagram 공구 파트너 크롤 + Haiku 스크리닝" -Force

# 2) 발송 — 평일 10:30 (쿠팡파트너스 발송 30분 후)
$action2 = New-ScheduledTaskAction -Execute $pythonExe -Argument "$pipelineScript send" -WorkingDirectory $workDir
$trigger2 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 10:30am
Register-ScheduledTask -TaskName "InstaGonggu_Send" -Action $action2 -Trigger $trigger2 -Settings $settings -Description "승인된 인스타 계정에 DM 발송" -Force

# 3) 상태 확인 — 평일 18:00
$action3 = New-ScheduledTaskAction -Execute $pythonExe -Argument "$pipelineScript check" -WorkingDirectory $workDir
$trigger3 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 6pm
Register-ScheduledTask -TaskName "InstaGonggu_Check" -Action $action3 -Trigger $trigger3 -Settings $settings -Description "DM 답장 현황 확인" -Force

Write-Host ""
Write-Host "등록 완료:"
Write-Host "  InstaGonggu_Crawl — 평일 09:30"
Write-Host "  InstaGonggu_Send  — 평일 10:30"
Write-Host "  InstaGonggu_Check — 평일 18:00"
Write-Host ""
Write-Host "주의: InstaGonggu_Send는 session.json 없으면 자동 스킵됩니다."
Write-Host "  → 사무실에서 python login_manual.py 실행 후 로그인 먼저!"
