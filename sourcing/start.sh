#!/bin/bash
# 비코어랩 소싱 매니저 — 자동 재시작 런처
# 사용법: ./start.sh (또는 bash start.sh)
# 종료: Ctrl+C

cd "$(dirname "$0")"

# macOS App Nap 비활성화
export NSAppSleepDisabled=YES

echo "  비코어랩 소싱 매니저 런처"
echo "  서버가 죽으면 5초 후 자동 재시작합니다."
echo "  종료하려면 Ctrl+C"
echo ""

cleanup() {
    echo ""
    echo "  소싱 매니저 종료"
    kill $SERVER_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

while true; do
    python3 sourcing_app.py &
    SERVER_PID=$!
    wait $SERVER_PID
    EXIT_CODE=$?
    echo ""
    echo "  [!] 서버 종료됨 (코드: $EXIT_CODE) — 5초 후 재시작..."
    sleep 5
done
