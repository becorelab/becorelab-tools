@echo off
:: 비코어랩 마켓 파인더 자동 시작
cd /d C:\Users\info\ClaudeAITeam\sourcing
start /min python analyzer\app.py >> market_finder.log 2>&1
