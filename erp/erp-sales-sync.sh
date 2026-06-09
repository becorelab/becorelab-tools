#!/bin/bash
# ERP 매출 자동 동기화 (launchd, 매일 09:35) — 맥 절전에 강함
# app.py 내부 asyncio 타이머가 절전 때 9:30을 놓치는 문제 → 외부 크론으로 이관
LOG=/tmp/erp-sales-sync.log
ts() { date '+%Y-%m-%d %H:%M:%S'; }
YESTERDAY=$(date -v-1d '+%Y-%m-%d')

echo "[$(ts)] === ERP 매출 sync 시작 ===" >> "$LOG"

# 1) 최근 14일 중 비어있는 날짜 채우기 (기존 데이터 보존 = 안전)
echo -n "[$(ts)] sync(14d): " >> "$LOG"
curl -s -X POST http://localhost:8085/api/sales/sync \
  -H "Content-Type: application/json" -d '{"days":14}' >> "$LOG" 2>&1
echo "" >> "$LOG"

# 2) 어제 하루만 재동기화 (늦게 잡힌 주문 = 시차 반영. 어제는 물류 데이터 확실)
echo -n "[$(ts)] resync($YESTERDAY): " >> "$LOG"
curl -s -X POST http://localhost:8085/api/sales/resync \
  -H "Content-Type: application/json" \
  -d "{\"date_from\":\"$YESTERDAY\",\"date_to\":\"$YESTERDAY\"}" >> "$LOG" 2>&1
echo "" >> "$LOG"
echo "[$(ts)] === 완료 ===" >> "$LOG"
