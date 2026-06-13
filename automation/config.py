"""비코어랩 새벽 자동화 설정"""
import os
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = "/Users/macmini_ky/ClaudeAITeam"
PYTHON_EXE = "/usr/bin/python3"


# 시크릿은 automation/.env(gitignore)에서 로드 — 코드에 평문 토큰 없음
def _load_env(path=os.path.join(PROJECT_ROOT, "automation", ".env")):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

# 서버 정보
SERVICES = {
    "logistics": {
        "name": "물류서버",
        "url": "http://localhost:8082",
        "health_path": "/",
        "start_cmd": ["launchctl", "start", "com.becorelab.logistics"],
    },
    "sourcing": {
        "name": "소싱앱",
        "url": "http://localhost:8090",
        "health_path": "/",
        "start_cmd": ["launchctl", "start", "com.becorelab.sourcing"],
    },
    "hub": {
        "name": "허브대시보드",
        "url": "http://localhost:8000",
        "health_path": "/",
        "start_cmd": ["launchctl", "start", "com.becorelab.hub"],
    },
    "pixie": {
        "name": "픽시봇",
        "url": None,
        "process_keyword": "pixie_bot.py",
        "start_cmd": [PYTHON_EXE, "-u", "pixie_bot.py"],
        "cwd": os.path.join(PROJECT_ROOT, "Channel_pixie"),
    },
}

# 텔레그램 (두리 봇으로 보고) — .env에서 로드
TELEGRAM_BOT_TOKEN = os.environ.get("DOORI_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("DOORI_CHAT_ID", "")

# API 키 — .env에서 로드
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# 메타 광고 API — .env에서 로드
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_AD_ACCOUNTS = {
    "ilbia": "act_939432264476274",
    "laundry": "act_1374146073384332",
}
META_API_VERSION = "v21.0"

# 데이터 저장 경로
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_JSON = os.path.join(DATA_DIR, "morning_data.json")
LOG_FILE = os.path.join(DATA_DIR, "morning_collect.log")

# 옵시디언 볼트 경로
OBSIDIAN_VAULT = os.path.expanduser("~/Library/CloudStorage/GoogleDrive-cky2833@gmail.com/내 드라이브/앱/remotely-save/비코어랩")
OBSIDIAN_AD_DIR = os.path.join(OBSIDIAN_VAULT, "01. Becorelab AI Agent Team", "2️⃣ Areas", "📢 Marketing", "📢 Ad Performance")
OBSIDIAN_SALES_DIR = os.path.join(OBSIDIAN_VAULT, "01. Becorelab AI Agent Team", "2️⃣ Areas", "📊 Operations", "📊 Sales Report", "일일")
OBSIDIAN_STOCK_DIR = os.path.join(OBSIDIAN_VAULT, "01. Becorelab AI Agent Team", "2️⃣ Areas", "📊 Operations", "📦 Stock & Order")


def yesterday_str():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
