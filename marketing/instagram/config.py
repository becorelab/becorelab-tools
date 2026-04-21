"""인스타그램 공동구매 파이프라인 — 설정 상수"""
from pathlib import Path

BASE_DIR = Path(__file__).parent

# 구글 시트 (쿠팡 파트너스와 동일 스프레드시트, 별도 워크시트)
KEY_PATH = r"C:\Users\User\claudeaiteam\sourcing\analyzer\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"
CANDIDATE_SHEET_NAME = "인스타 공구 후보"

# 스크리닝 기준 (instagram_bot.py settings DB 기본값과 동기)
MIN_FOLLOWERS = 10_000
MAX_FOLLOWERS = 100_000
MIN_LIKE_RATE = 0.005
MAX_LIKE_RATE = 0.05
MIN_COMMENT_RATE = 0.001

# 아웃리치 워밍업 (1주차 10통/일, 이후 대표님 수동 조정)
DAILY_SEND_LIMIT = 10

# 페르소나
SENDER_NAME = "비코어랩 마케팅팀"
