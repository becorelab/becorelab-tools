#!/bin/bash
# CDP Chrome 재시작 — 누적 렌더러 프로세스 정리
# 매일 03:45 실행 (morning_collect 03:50 전)
pkill -f "user-data-dir=/Users/macmini_ky/ChromeCDP" 2>/dev/null
sleep 3
# Singleton 락 파일 삭제 (새 Chrome 띄울 때 "기존 세션 사용 중" 에러 방지)
rm -f /Users/macmini_ky/ChromeCDP/SingletonLock /Users/macmini_ky/ChromeCDP/SingletonSocket /Users/macmini_ky/ChromeCDP/SingletonCookie 2>/dev/null
launchctl kickstart -k "gui/$(id -u)/com.becorelab.chrome-cdp" 2>/dev/null
echo "$(date '+%Y-%m-%d %H:%M:%S') CDP Chrome restarted (lock files cleaned)" >> /Users/macmini_ky/ClaudeAITeam/logs/chrome-cdp-restart.log
