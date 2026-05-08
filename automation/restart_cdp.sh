#!/bin/bash
# CDP Chrome 재시작 — 탭 정리 + 캐시 삭제 + 렌더러 정리
# 매일 03:45 실행 (morning_collect 03:50 전)

LOG="/Users/macmini_ky/ClaudeAITeam/logs/chrome-cdp-restart.log"

# 1. CDP API로 열린 탭 모두 닫기 (graceful)
for target_id in $(curl -s http://localhost:9222/json/list 2>/dev/null | python3 -c "
import sys,json
try:
    data=json.load(sys.stdin)
    for d in data:
        if d.get('type') == 'page':
            print(d['id'])
except: pass
" 2>/dev/null); do
    curl -s "http://localhost:9222/json/close/$target_id" >/dev/null 2>&1
done
sleep 2

# 2. Chrome CDP 프로세스 전부 종료
pkill -f "user-data-dir=/Users/macmini_ky/ChromeCDP" 2>/dev/null
sleep 3

# 3. Singleton 락 + 캐시 정리
rm -f /Users/macmini_ky/ChromeCDP/SingletonLock /Users/macmini_ky/ChromeCDP/SingletonSocket /Users/macmini_ky/ChromeCDP/SingletonCookie 2>/dev/null
rm -rf /Users/macmini_ky/ChromeCDP/Default/Cache/Cache_Data/* 2>/dev/null
rm -rf /Users/macmini_ky/ChromeCDP/Default/Code\ Cache/* 2>/dev/null
rm -rf /Users/macmini_ky/ChromeCDP/Crashpad/completed/* 2>/dev/null

# 4. launchd로 재시작
launchctl kickstart -k "gui/$(id -u)/com.becorelab.chrome-cdp" 2>/dev/null

echo "$(date '+%Y-%m-%d %H:%M:%S') CDP restarted (tabs closed, cache cleaned)" >> "$LOG"
