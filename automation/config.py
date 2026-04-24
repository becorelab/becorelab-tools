"""비코어랩 새벽 자동화 설정"""
import os
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = "/Users/macmini_ky/ClaudeAITeam"
PYTHON_EXE = "/usr/bin/python3"

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

# 텔레그램 (두리 봇으로 보고)
TELEGRAM_BOT_TOKEN = "8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"
TELEGRAM_CHAT_ID = "8708718261"

# API 키
DEEPSEEK_API_KEY = "sk-b2ea74046efa48648527ec9d5f2ac366"

# 메타 광고 API
META_ACCESS_TOKEN = "EAA8FG3lEZC18BRF9zom757dImMO9LwK5hF2Deja0tez1GTnHPoaZAZCuAFPLN7EZArT5UOozqcIcjBt8ngFmvs0ls3YKcosOx0JVmHbkYKRQ7ROio2wio7ZA0PuzgYotDrZAxPNtb9uuRq0S64yfncvj4Hf49uAorOZA0Gqy0mhH0ed99ic45hlFA58cFKJS9wxeAZDZD"
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
OBSIDIAN_VAULT = os.path.expanduser("~/Documents/비코어랩")
OBSIDIAN_AD_DIR = os.path.join(OBSIDIAN_VAULT, "01. Becorelab AI Agent Team", "2️⃣ Areas", "📢 Ad Performance")
OBSIDIAN_SALES_DIR = os.path.join(OBSIDIAN_VAULT, "01. Becorelab AI Agent Team", "2️⃣ Areas", "📊 Sales Report", "일일")
OBSIDIAN_STOCK_DIR = os.path.join(OBSIDIAN_VAULT, "01. Becorelab AI Agent Team", "2️⃣ Areas", "📦 Stock & Order")


def yesterday_str():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
