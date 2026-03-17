$ws = New-Object -ComObject WScript.Shell
$startupPath = [System.IO.Path]::Combine($env:APPDATA, "Microsoft\Windows\Start Menu\Programs\Startup\MarketFinder.lnk")
$shortcut = $ws.CreateShortcut($startupPath)
$shortcut.TargetPath = "C:\Users\info\ClaudeAITeam\sourcing\start_market_finder.bat"
$shortcut.WorkingDirectory = "C:\Users\info\ClaudeAITeam\sourcing"
$shortcut.WindowStyle = 7
$shortcut.Save()
Write-Host "OK: Startup shortcut created at $startupPath"
