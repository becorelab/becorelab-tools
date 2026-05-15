#!/bin/bash
# 스크리닝 재시도 — 성공하면 자동 종료
cd /Users/macmini_ky/ClaudeAITeam/marketing/coupang_partners
source venv/bin/activate
export GEMINI_API_KEY=AIzaSyCQOLdR3yRi1BjUX2m25gD_kTMf2nBDoI4

MAX_ATTEMPTS=8
INTERVAL=7200  # 2시간

for i in $(seq 1 $MAX_ATTEMPTS); do
    echo "[$(date '+%Y-%m-%d %H:%M')] 시도 $i/$MAX_ATTEMPTS"
    OUTPUT=$(python screener.py 2>&1)
    echo "$OUTPUT" | tail -5
    
    # 성공 건이 있으면 종료
    if echo "$OUTPUT" | grep -q "성공 [1-9]"; then
        echo "[$(date '+%Y-%m-%d %H:%M')] ✅ 스크리닝 완료!"
        exit 0
    fi
    
    # 재시도 대상 0개면 (이미 다 됨) 종료
    if echo "$OUTPUT" | grep -q "재시도 대상: 0개\|재스크리닝 대상: 0개"; then
        echo "[$(date '+%Y-%m-%d %H:%M')] ✅ 재시도 대상 없음 — 완료!"
        exit 0
    fi
    
    if [ $i -lt $MAX_ATTEMPTS ]; then
        echo "  → 2시간 후 재시도..."
        sleep $INTERVAL
    fi
done
echo "[$(date '+%Y-%m-%d %H:%M')] ⚠️ $MAX_ATTEMPTS회 시도 후에도 미완료"
