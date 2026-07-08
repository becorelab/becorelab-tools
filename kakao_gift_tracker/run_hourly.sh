#!/bin/bash
# 카카오 선물하기 시간대 실측 러너 (2026-07-08) — 2h 간격 9~23시 크론에서 호출.
# rank_track.py --hourly: 리뷰상세 생략, 랭킹만(~8초) → rank_snapshots/hourly/YYYY-MM-DD_HHMM.json
cd /Users/macmini_ky/ClaudeAITeam/kakao_gift_tracker || exit 1
mkdir -p logs
LOG="logs/kakao_hourly_$(date +%F).log"
{
  echo "===== $(date '+%F %T') rank_track.py --hourly ====="
  /usr/bin/python3 rank_track.py 40 --hourly
} >> "$LOG" 2>&1
