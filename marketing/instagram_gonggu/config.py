"""인스타 공동구매 파이프라인 — 설정 상수"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── 구글 시트 ────────────────────────────────────────────────
KEY_PATH = (
    r"C:\Users\User\claudeaiteam\sourcing\analyzer"
    r"\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
)
SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"
SHEET_NAME = "인스타 공구"

# ── 인스타 계정 (전용 서브 계정) ─────────────────────────────
IG_USERNAME = os.environ.get("IG_USERNAME", "")
IG_PASSWORD = os.environ.get("IG_PASSWORD", "")

# ── DM 발송 설정 ─────────────────────────────────────────────
DAILY_SEND_MIN = 43
DAILY_SEND_MAX = 50
SEND_START_HOUR = 10  # 오전 10시
SEND_END_HOUR = 21    # 오후 9시

# 시간대별 발송 가중치 (합계 = 1.0)
HOURLY_WEIGHTS = {
    10: 0.10, 11: 0.10,           # 오전 (20%)
    12: 0.075, 13: 0.075,         # 점심 (15%)
    14: 0.09, 15: 0.09, 16: 0.09, 17: 0.08,  # 오후 (35%)
    18: 0.10, 19: 0.10, 20: 0.10,             # 저녁 (30%)
}

# DM 간격 (가우시안 분포, 초 단위)
DM_INTERVAL_MEAN = 720   # 평균 12분
DM_INTERVAL_STD = 240    # 표준편차 4분
DM_INTERVAL_MIN = 180    # 최소 3분
DM_INTERVAL_MAX = 1500   # 최대 25분

# 차단 감지
MAX_CONSECUTIVE_FAILURES = 3

# ── 크롤링 설정 ──────────────────────────────────────────────
TARGET_HASHTAGS = [
    "살림스타그램", "주부일상", "청소스타그램", "리빙템", "육아맘",
    "미니멀라이프", "세탁", "건조기", "살림꿀팁", "살림템",
    "주부스타그램", "주방살림", "세제추천", "공동구매", "공구스타그램",
    "홈스타그램", "집스타그램", "살림고수", "신혼살림", "주부생활",
]

# 타겟 팔로워 범위
MIN_FOLLOWERS = 5_000
MAX_FOLLOWERS = 50_000
MIN_ENGAGEMENT_RATE = 0.03  # 3%
MAX_ENGAGEMENT_RATE = 0.20  # 20% 초과 시 좋아요 봇 의심

# ── 가짜 팔로워 감지 임계값 ──────────────────────────────────
# 팔로잉/팔로워 비율 — 1.5 이상이면 맞팔 교환으로 팔로워 부풀린 계정
MAX_FOLLOWING_RATIO = 1.5
# 게시물 수 대비 팔로워 — 게시물당 팔로워 1000명 이상이면 의심
MAX_FOLLOWER_PER_POST = 1000
# 댓글/좋아요 비율 — 정상: 1~5%. 10% 초과 시 댓글 봇 의심
MAX_COMMENT_LIKE_RATIO = 0.10
# 외국인 팔로워 비율 — 30% 이상이면 팔로워 구매 의심
MAX_FOREIGN_FOLLOWER_RATIO = 0.30
FOREIGN_CHECK_SAMPLE = 30

# ── 후보 상태 ────────────────────────────────────────────────
STATUS_SCREENED = "screened"
STATUS_APPROVED = "승인"
STATUS_CONTACTED = "contacted"
STATUS_REPLIED = "replied"
STATUS_NEGOTIATING = "negotiating"
STATUS_CONFIRMED = "gonggu_confirmed"
STATUS_DECLINED = "declined"

# ── Playwright 세션 ──────────────────────────────────────────
SESSION_PATH = str(BASE_DIR / "session.json")
API_SESSION_PATH = str(BASE_DIR / "api_session.json")
DM_LOG_DB = str(BASE_DIR / "dm_log.db")
