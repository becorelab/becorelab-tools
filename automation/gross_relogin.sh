#!/bin/bash
# 그로스 세션 재로그인 — 헤드풀 크롬 띄워 대표님 로그인 → 쿠키 백업 → 헤드리스 복귀
# 사용: 크론이 "세션 만료" 알리면 실행. (자동화 크롬 화면에 떠요)
set -e
UID_=$(id -u)
PROFILE="/Users/macmini_ky/ChromeCDP"
CFT="/Users/macmini_ky/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
BACKUP="/Users/macmini_ky/ClaudeAITeam/automation/gross_session_cookies.json"

echo "1) 헤드리스 CDP 정지..."
launchctl bootout gui/$UID_/com.becorelab.chrome-cdp 2>/dev/null || true
sleep 2; pkill -f "user-data-dir=$PROFILE" 2>/dev/null || true; sleep 2

echo "2) 로그인용 크롬 띄우는 중... (화면에 떠요)"
"$CFT" --remote-debugging-port=9222 --remote-allow-origins='*' --user-data-dir="$PROFILE" --no-first-run \
  "https://wing.coupang.com/tenants/business-insight/sales-analysis" >/dev/null 2>&1 &
sleep 6
echo ""
echo "   👉 뜬 크롬에서 채움컴퍼니 Wing 로그인하세요."
echo -n "   로그인 끝나면 엔터: "
read _

echo "3) 쿠키 백업..."
python3 -c "
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.connect_over_cdp('http://127.0.0.1:9222', timeout=30000)
    json.dump(b.contexts[0].cookies(), open('$BACKUP','w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print('   쿠키 백업 완료')
"
echo "4) 헤드리스 복귀..."
pkill -f "user-data-dir=$PROFILE" 2>/dev/null || true; sleep 3
launchctl bootstrap gui/$UID_ ~/Library/LaunchAgents/com.becorelab.chrome-cdp.plist
sleep 5
echo "✅ 완료! 헤드리스 상주 + 백업쿠키 갱신됨. 이제 매일 무인 작동해요."
