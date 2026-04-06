"""비코어랩 새벽 자동화 설정"""
import os
from datetime import datetime, timedelta

PROJECT_ROOT = r"C:\Users\info\ClaudeAITeam"
PYTHON_EXE = r"C:\Users\info\AppData\Local\Python\pythoncore-3.14-64\python.exe"
OPENCLAW_CMD = r"C:\Users\info\AppData\Roaming\npm\openclaw.cmd"

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
}

# 텔레그램 (보리 봇으로 에러 알림)
TELEGRAM_BOT_TOKEN = "8385451689:AAG1ixwV8E_yaidNpEZ16iZpAi9K55yUbRM"
TELEGRAM_CHAT_ID = "8708718261"

# API 키
DEEPSEEK_API_KEY = "sk-b2ea74046efa48648527ec9d5f2ac366"

# 데이터 저장 경로
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_JSON = os.path.join(DATA_DIR, "morning_data.json")
LOG_FILE = os.path.join(DATA_DIR, "morning_collect.log")


def yesterday_str():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
