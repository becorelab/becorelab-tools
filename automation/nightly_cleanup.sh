#!/bin/bash
# 새벽 메모리 정리 — 03:30 실행 (CDP 03:45, morning_collect 03:50 전)
# 목적: 밤새 누적된 프로세스 정리 → 크론 실행 시 OOM 방지

LOG="/Users/macmini_ky/ClaudeAITeam/logs/nightly-cleanup.log"
TS=$(date '+%Y-%m-%d %H:%M:%S')

echo "==========================================" >> "$LOG"
echo "$TS 새벽 정리 시작" >> "$LOG"

# 1. Notion 종료 (새벽엔 불필요, 출근 시 재실행)
if pgrep -f "Notion.app" >/dev/null 2>&1; then
    pkill -f "Notion.app" 2>/dev/null
    echo "$TS [KILL] Notion 종료" >> "$LOG"
fi

# 2. 활성 상태 보기 종료
pkill -f "Activity Monitor" 2>/dev/null

# 3. 고아 Claude 프로세스 정리 (PPID=1)
for pid in $(ps -eo pid,ppid,command | grep -i "claude" | grep -v grep | awk '$2==1 {print $1}'); do
    RSS=$(ps -o rss= -p $pid 2>/dev/null)
    RSS_MB=$((${RSS:-0} / 1024))
    echo "$TS [KILL] 고아 Claude PID=$pid (${RSS_MB}MB)" >> "$LOG"
    kill -TERM $pid 2>/dev/null
done

# 4. 고아 node 프로세스 정리 (>100MB, PPID=1, VS Code/Notion 제외)
for pid in $(ps -eo pid,ppid,rss,command | grep "node" | grep -v grep | grep -v "Code Helper" | grep -v "Notion" | awk '$2==1 && $3>102400 {print $1}'); do
    RSS=$(ps -o rss= -p $pid 2>/dev/null)
    RSS_MB=$((${RSS:-0} / 1024))
    echo "$TS [KILL] 고아 node PID=$pid (${RSS_MB}MB)" >> "$LOG"
    kill -TERM $pid 2>/dev/null
done

# 5. OneDrive 메모리 누수 체크 (>600MB면 재시작)
ONEDRIVE_PID=$(pgrep -x "OneDrive" 2>/dev/null)
if [ -n "$ONEDRIVE_PID" ]; then
    ONEDRIVE_RSS=$(ps -o rss= -p $ONEDRIVE_PID 2>/dev/null | tr -d ' ')
    if [ -n "$ONEDRIVE_RSS" ] && [ "$ONEDRIVE_RSS" -gt 614400 ]; then
        ONEDRIVE_MB=$((ONEDRIVE_RSS / 1024))
        echo "$TS [RESTART] OneDrive ${ONEDRIVE_MB}MB > 600MB, 재시작" >> "$LOG"
        pkill -f "OneDrive.app" 2>/dev/null
        sleep 5
        open -a "OneDrive" 2>/dev/null
    fi
fi

# 6. Spotlight 프로세스 우선순위 최저로
for pid in $(pgrep -f "mds_stores|mdworker"); do
    renice 20 $pid 2>/dev/null
done

# 7. mediaanalysisd 일시정지 (새벽 크론 보호)
MEDIA_PID=$(pgrep -f mediaanalysisd)
if [ -n "$MEDIA_PID" ]; then
    kill -STOP $MEDIA_PID 2>/dev/null
    echo "$TS [STOP] mediaanalysisd 일시정지" >> "$LOG"
fi

echo "$TS 새벽 정리 완료" >> "$LOG"
echo "==========================================" >> "$LOG"

# 로그 관리 (최근 500줄만 유지)
tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG" 2>/dev/null
