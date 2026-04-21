@echo off
:: 비코어랩 소싱콕 자동 시작
cd /d C:\Users\User\ClaudeAITeam\sourcing
start /min python analyzer\app.py >> market_finder.log 2>&1
