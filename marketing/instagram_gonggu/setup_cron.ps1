# Instagram Gonggu Pipeline - Windows Task Scheduler Setup
# DM auto-send runs hourly 10:00~20:00 (last batch at 20:00, completes before 21:00)
# Crawl runs weekly Monday 08:00

$pythonExe = "C:\Users\info\ClaudeAITeam\mcp-server\.venv\Scripts\python.exe"
$pipelineScript = "C:\Users\info\claudeaiteam\marketing\instagram_gonggu\pipeline.py"
$workDir = "C:\Users\info\claudeaiteam\marketing\instagram_gonggu"

# Common settings
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

# 1) Weekly Crawl - Monday 08:00
$action1 = New-ScheduledTaskAction -Execute $pythonExe -Argument "$pipelineScript crawl" -WorkingDirectory $workDir
$trigger1 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 8am
Register-ScheduledTask -TaskName "InstaGonggu_Crawl" -Action $action1 -Trigger $trigger1 -Settings $settings -Description "Weekly Instagram hashtag crawl + Haiku screening" -Force

# 2) Hourly Send - Daily 10:00~20:00 (every hour)
$action2 = New-ScheduledTaskAction -Execute $pythonExe -Argument "$pipelineScript send" -WorkingDirectory $workDir
$triggers = @()
for ($h = 10; $h -le 20; $h++) {
    $triggers += New-ScheduledTaskTrigger -Daily -At "$($h):00"
}
Register-ScheduledTask -TaskName "InstaGonggu_Send" -Action $action2 -Trigger $triggers -Settings $settings -Description "Hourly DM send batch (10:00~20:00, bot-safe pacing)" -Force

Write-Host ""
Write-Host "Scheduled tasks registered:"
Write-Host "  InstaGonggu_Crawl  - Monday 08:00 (weekly)"
Write-Host "  InstaGonggu_Send   - Daily 10:00~20:00 (hourly)"
Write-Host ""
Write-Host "DM pacing: 43~50/day, gaussian interval (~12min avg), natural behavior injection"
