# Coupang Partners Pipeline - Windows Task Scheduler Setup
# 4 scheduled tasks for automated youtuber outreach

$pythonExe = "C:\Users\info\ClaudeAITeam\mcp-server\.venv\Scripts\python.exe"
$pipelineScript = "C:\Users\info\claudeaiteam\marketing\coupang_partners\pipeline.py"
$workDir = "C:\Users\info\claudeaiteam\marketing\coupang_partners"

# 1) Weekly Crawl - Monday 09:00
$action1 = New-ScheduledTaskAction -Execute $pythonExe -Argument "$pipelineScript crawl" -WorkingDirectory $workDir
$trigger1 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am
Register-ScheduledTask -TaskName "CoupangPartners_Crawl" -Action $action1 -Trigger $trigger1 -Description "Weekly YouTube crawl + Haiku screening" -Force

# 2) Daily Send - Weekday 10:00
$action2 = New-ScheduledTaskAction -Execute $pythonExe -Argument "$pipelineScript send" -WorkingDirectory $workDir
$trigger2 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 10am
Register-ScheduledTask -TaskName "CoupangPartners_Send" -Action $action2 -Trigger $trigger2 -Description "Send outreach emails to approved youtubers" -Force

# 3) Daily Reply Check - Weekday 14:00 and 18:00
$action3 = New-ScheduledTaskAction -Execute $pythonExe -Argument "$pipelineScript check" -WorkingDirectory $workDir
$trigger3a = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 2pm
$trigger3b = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 6pm
Register-ScheduledTask -TaskName "CoupangPartners_Check" -Action $action3 -Trigger @($trigger3a, $trigger3b) -Description "Check for youtuber email replies" -Force

Write-Host "Scheduled tasks registered:"
Write-Host "  CoupangPartners_Crawl  - Mon 09:00"
Write-Host "  CoupangPartners_Send   - Weekday 10:00"
Write-Host "  CoupangPartners_Check  - Weekday 14:00, 18:00"
