@echo off
schtasks /create /tn "비코어랩 소싱콕" /tr "C:\Users\User\ClaudeAITeam\sourcing\start_market_finder.bat" /sc ONLOGON /ru "%USERNAME%" /rl LIMITED /f
