Set WshShell = CreateObject("WScript.Shell")

' Check if already running
Dim checkCmd
checkCmd = "powershell -WindowStyle Hidden -NoProfile -Command ""if(Get-NetTCPConnection -LocalPort 8500 -State Listen -ErrorAction SilentlyContinue){exit 0}else{exit 1}"""
Dim exitCode
exitCode = WshShell.Run(checkCmd, 0, True)
If exitCode = 0 Then
    WScript.Quit 0
End If

' Start remote MCP server silently
WshShell.Run "powershell -WindowStyle Hidden -NoProfile -Command ""Set-Location 'C:\Users\User\ClaudeAITeam\mcp-server'; & 'C:\Users\User\ClaudeAITeam\mcp-server\.venv\Scripts\python.exe' server_remote.py""", 0, False
