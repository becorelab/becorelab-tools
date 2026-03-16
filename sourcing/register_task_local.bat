@echo off
schtasks /create /tn "비코어랩 마켓파인더" /tr "C:\Users\info\ClaudeAITeam\sourcing\start_market_finder.bat" /sc ONLOGON /ru "%USERNAME%" /rl LIMITED /f
