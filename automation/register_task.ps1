$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\Users\info\ClaudeAITeam\automation\morning_brief.py" -WorkingDirectory "C:\Users\info\ClaudeAITeam\automation"
$trigger = New-ScheduledTaskTrigger -Daily -At "05:40"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -StartWhenAvailable
Register-ScheduledTask -TaskName "Becorelab Morning Brief" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force
Write-Host "Done!"
Get-ScheduledTask -TaskName "Becorelab Morning Brief" | Select-Object TaskName, State
