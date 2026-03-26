Set WshShell = CreateObject("WScript.Shell")

' Check if already running
Dim checkCmd
checkCmd = "powershell -WindowStyle Hidden -NoProfile -Command ""if(Get-NetTCPConnection -LocalPort 8082 -State Listen -ErrorAction SilentlyContinue){exit 0}else{exit 1}"""
Dim exitCode
exitCode = WshShell.Run(checkCmd, 0, True)
If exitCode = 0 Then
    WScript.Quit 0
End If

' Start logistics server silently
WshShell.Run "powershell -WindowStyle Hidden -NoProfile -Command ""Start-Process -FilePath 'C:\Users\info\AppData\Local\Python\pythoncore-3.14-64\python.exe' -ArgumentList 'C:\Users\info\ClaudeAITeam\logistics\logistics_app.py' -WindowStyle Hidden""", 0, False
