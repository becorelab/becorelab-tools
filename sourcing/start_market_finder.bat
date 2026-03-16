@echo off
:: 비코어랩 마켓 파인더 자동 시작
:: 위치: sourcing/start_market_finder.bat

cd /d C:\Users\info\ClaudeAITeam\sourcing
python analyzer\app.py >> C:\Users\info\ClaudeAITeam\sourcing\market_finder.log 2>&1
