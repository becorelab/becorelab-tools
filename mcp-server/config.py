"""비코어랩 MCP 서버 설정"""
import os

# 사무실 맥미니 Tailscale IP (환경변수로 오버라이드 가능)
# 맥미니 로컬에서는 OFFICE_IP=localhost 로 오버라이드
OFFICE_IP = os.environ.get("OFFICE_IP", "100.105.211.14")

# 앱별 베이스 URL
LOGISTICS_BASE = f"http://{OFFICE_IP}:8082"
SOURCING_BASE = f"http://{OFFICE_IP}:8090"

# HTTP 요청 타임아웃 (초)
TIMEOUT = 30

# 채널톡 API
CHANNEL_TALK_ACCESS_KEY = os.environ.get("CHANNEL_TALK_ACCESS_KEY", "6a0554c104ba3b33e314")
CHANNEL_TALK_ACCESS_SECRET = os.environ.get("CHANNEL_TALK_ACCESS_SECRET", "2e28464ac91692df0fcb9dc269d56b2b")
