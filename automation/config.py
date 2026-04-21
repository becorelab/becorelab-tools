"""비코어랩 새벽 자동화 설정"""
import os
from datetime import datetime, timedelta

PROJECT_ROOT = r"C:\Users\User\ClaudeAITeam"
PYTHON_EXE = r"C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe"
OPENCLAW_CMD = r"C:\Users\User\AppData\Roaming\npm\openclaw.cmd"

# 서버 정보
SERVICES = {
    "logistics": {
        "name": "물류서버",
        "url": "http://localhost:8082",
        "health_path": "/",
        "start_cmd": [PYTHON_EXE, "logistics/logistics_app.py"],
        "cwd": PROJECT_ROOT,
    },
    "sourcing": {
        "name": "소싱앱",
        "url": "http://localhost:8090",
        "health_path": "/",
        "start_cmd": [PYTHON_EXE, "analyzer/app.py"],
        "cwd": os.path.join(PROJECT_ROOT, "sourcing"),
    },
    "openclaw": {
        "name": "오픈클로",
        "url": "http://localhost:18789",
        "health_path": "/",
        "start_cmd": [OPENCLAW_CMD, "gateway", "start"],
        "cwd": PROJECT_ROOT,
    },
    "pixie": {
        "name": "픽시봇",
        "url": None,
        "process_keyword": "pixie_bot.py",
        "start_cmd": [PYTHON_EXE, "-u", "pixie_bot.py"],
        "cwd": os.path.join(PROJECT_ROOT, "pixie-bot"),
    },
    "chrome_cdp": {
        "name": "Chrome CDP",
        "url": "http://localhost:9222",
        "health_path": "/json/version",
        "start_cmd": [
            "cmd", "/c",
            os.path.join(PROJECT_ROOT, "automation", "start_chrome_cdp.bat"),
        ],
        "cwd": PROJECT_ROOT,
    },
    "remote_mcp": {
        "name": "Remote MCP",
        "url": "http://localhost:8500",
        "health_path": "/sse",
        "start_cmd": [
            "cmd", "/c",
            os.path.join(PROJECT_ROOT, "automation", "start_remote_mcp.bat"),
        ],
        "cwd": PROJECT_ROOT,
    },
}

# 텔레그램 (보리 봇으로 에러 알림)
TELEGRAM_BOT_TOKEN = "8385451689:AAG1ixwV8E_yaidNpEZ16iZpAi9K55yUbRM"
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
OBSIDIAN_VAULT = r"C:\Users\User\Documents\비코어랩"
OBSIDIAN_AD_DIR = os.path.join(OBSIDIAN_VAULT, "01. Becorelab AI Agent Team", "2️⃣ Areas", "📢 Ad Performance")
OBSIDIAN_SALES_DIR = os.path.join(OBSIDIAN_VAULT, "01. Becorelab AI Agent Team", "2️⃣ Areas", "📊 Sales Report", "일일")
OBSIDIAN_STOCK_DIR = os.path.join(OBSIDIAN_VAULT, "01. Becorelab AI Agent Team", "2️⃣ Areas", "📦 Stock & Order")


def yesterday_str():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
