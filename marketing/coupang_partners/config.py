"""쿠팡 파트너스 유튜버 컨택 파이프라인 — 설정 상수"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
PORT = 8083

# Firestore 컬렉션
COLL_CANDIDATES = "coupang_partners_candidates"
COLL_THREADS = "coupang_partners_threads"
COLL_GHOST_QUEUE = "coupang_partners_ghost_queue"

# YouTube Data API
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# 네이버웍스 메일 (SMTP SSL 465 / IMAP SSL 993)
NAVERWORKS_SMTP_HOST = "smtp.worksmobile.com"
NAVERWORKS_SMTP_PORT = 465  # SSL (not STARTTLS)
NAVERWORKS_IMAP_HOST = "imap.worksmobile.com"
NAVERWORKS_IMAP_PORT = 993  # SSL
NAVERWORKS_CRED_PATH = str(BASE_DIR / "credentials" / "naverworks.json")
NAVERWORKS_FROM_NAME = "비코어랩 마케팅팀"

# 쿠팡 파트너스 유튜버 답장 전용 폴더 (웹메일 필터 규칙으로 라우팅)
PARTNERS_INBOX_MAILBOX = "유튜브 협찬 메일"
# 발송 제목 접두사 — 웹메일 필터 규칙의 트리거로도 사용
PARTNERS_SUBJECT_PREFIX = "[iLBiA 쿠팡 파트너스]"

# 스크리닝 임계값
MIN_SUBSCRIBERS = 5_000
MAX_SUBSCRIBERS = 100_000
MAX_UPLOAD_DAYS = 30

# 아웃리치 워밍업 (2026-04-18 시작, 주간 단계적 증가 로드맵)
#   1주차 (4/18~4/24): 10통/일  ← 현재
#   2주차 (4/27~5/1) : 15통/일
#   3주차 (5/4~5/8)  : 20통/일
#   4주차 (5/11~)    : 30통/일 (목표)
# 이유: becorelab.kr 신규 도메인 스팸 reputation 워밍업 + 승인/회신 처리 부담 고려.
# 대표님이 매주 월요일 상황 보고 수동 조정 (자동 증가 X).
DAILY_SEND_LIMIT = 10

# 잠수 감지 (일 단위)
GHOST_NO_REPLY_DAYS = 7
GHOST_NO_ADDRESS_DAYS = 3
GHOST_NO_UPLOAD_WEEKS = 4
GHOST_NO_FIX_DAYS = 3

# 후보 상태 enum
STATUS_DISCOVERED = "discovered"
STATUS_SCREENED = "screened"
STATUS_APPROVED = "approved"
STATUS_CONTACTED = "contacted"
STATUS_REPLIED = "replied"
STATUS_SAMPLE_SENT = "sample_sent"
STATUS_UPLOADED = "uploaded"
STATUS_GHOSTED = "ghosted"
STATUS_REJECTED = "rejected"
STATUS_BLACKLISTED = "blacklisted"
