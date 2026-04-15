$action = New-ScheduledTaskAction `
    -Execute "C:\Users\info\AppData\Local\Python\pythoncore-3.14-64\python.exe" `
    -Argument "-u C:\Users\info\ClaudeAITeam\automation\morning_brief.py" `
    -WorkingDirectory "C:\Users\info\ClaudeAITeam\automation"
$trigger = New-ScheduledTaskTrigger -Daily -At "05:40"
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable
Register-ScheduledTask -TaskName "Becorelab Morning Brief" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force
Write-Host "Done!"
Get-ScheduledTask -TaskName "Becorelab Morning Brief" | Select-Object TaskName, State
Get-ScheduledTask -TaskName "Becorelab Morning Brief" | Select-Object -ExpandProperty Settings | Select-Object WakeToRun, StartWhenAvailable
