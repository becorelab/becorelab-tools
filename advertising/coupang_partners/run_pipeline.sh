#!/bin/bash
# 쿠팡 파트너스 유튜버 컨택 파이프라인 — macOS launchd 래퍼
# 평일(월~금)만 실행, 주말이면 스킵
# 사용법: ./run_pipeline.sh <command>  (crawl|send|check|status)

COMMAND="${1:-status}"
WORKDIR="/Users/macmini_ky/ClaudeAITeam/marketing/coupang_partners"
PYTHON="${WORKDIR}/venv/bin/python3"
PIPELINE="${WORKDIR}/pipeline.py"
LOGDIR="${WORKDIR}/logs"

# 평일 체크 (1=월 ~ 5=금)
DOW=$(date +%u)
if [ "$DOW" -gt 5 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M')] 주말 — 스킵"
    exit 0
fi

# 로그 디렉토리 확인
mkdir -p "${LOGDIR}"

# 날짜별 로그 파일
LOGFILE="${LOGDIR}/${COMMAND}_$(date +%Y-%m-%d).log"

echo "========================================" >> "${LOGFILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${COMMAND} 시작" >> "${LOGFILE}"
echo "========================================" >> "${LOGFILE}"

cd "${WORKDIR}" && "${PYTHON}" "${PIPELINE}" "${COMMAND}" >> "${LOGFILE}" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${COMMAND} 완료 (exit: $?)" >> "${LOGFILE}"
echo "" >> "${LOGFILE}"
