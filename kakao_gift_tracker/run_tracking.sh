#!/bin/bash
# 카카오 선물하기 추적 통합 러너 (2026-07-03) — 크론 9:50에서 호출.
# track.py(재고차분=경쟁사 판매추정) + rank_track.py(베스트 랭킹=시장서열·주문수) 둘 다 실행.
cd /Users/macmini_ky/ClaudeAITeam/kakao_gift_tracker || exit 1
mkdir -p logs
LOG="logs/kakao_track_$(date +%F).log"
{
  echo "===== $(date '+%F %T') track.py (재고차분 추적) ====="
  /usr/bin/python3 track.py
  echo
  echo "===== $(date '+%F %T') rank_track.py (베스트 랭킹 추적) ====="
  /usr/bin/python3 rank_track.py 40
} >> "$LOG" 2>&1
