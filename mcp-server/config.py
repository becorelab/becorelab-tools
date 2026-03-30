"""비코어랩 MCP 서버 설정"""
import os

# 사무실 PC Tailscale IP (환경변수로 오버라이드 가능)
OFFICE_IP = os.environ.get("OFFICE_IP", "100.83.96.49")

# 앱별 베이스 URL
LOGISTICS_BASE = f"http://{OFFICE_IP}:8082"
SOURCING_BASE = f"http://{OFFICE_IP}:8090"

# HTTP 요청 타임아웃 (초)
TIMEOUT = 30
