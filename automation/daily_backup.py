"""
비코어랩 일일 백업 스크립트
PC 로컬 데이터를 OneDrive에 자동 백업

백업 대상:
- 보리 workspace (SOUL.md, MEMORY.md 등)
- 픽시 workspace (SOUL.md)
- 오픈클로 설정 (openclaw.json, 크론)
- 하치 메모리
- 하치 대화 이력 (전체 세션)
- 픽시봇 SOUL.md
- API 키 (.env)
- 매출 캐시
- morning_data.json
"""
import os
import shutil
import logging
from datetime import datetime

# 설정
BACKUP_BASE = os.path.expanduser("~/Library/CloudStorage/OneDrive-개인/(주)비코어랩/Claude-Setup/backups")
HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "ClaudeAITeam")

# 백업 대상 (소스 → 백업 하위 폴더)
BACKUP_TARGETS = [
    # 하치 메모리
    {
        "src": os.path.join(HOME, ".claude", "projects", "-Users-macmini-ky", "memory"),
        "dst": "claude/memory",
        "type": "dir",
    },
    # CLAUDE.md
    {
        "src": os.path.join(HOME, "CLAUDE.md"),
        "dst": "claude/CLAUDE.md",
        "type": "file",
    },
    # 픽시봇 SOUL.md
    {
        "src": os.path.join(PROJECT, "Channel_pixie", "SOUL.md"),
        "dst": "pixie-bot/SOUL.md",
        "type": "file",
    },
    # 픽시봇 코드
    {
        "src": os.path.join(PROJECT, "Channel_pixie", "pixie_bot.py"),
        "dst": "pixie-bot/pixie_bot.py",
        "type": "file",
    },
    # API 키
    {
        "src": os.path.join(PROJECT, "sourcing", "analyzer", ".env"),
        "dst": "secrets/sourcing-env",
        "type": "file",
    },
    # 매출 캐시
    {
        "src": os.path.join(PROJECT, "logistics", "data"),
        "dst": "logistics-data",
        "type": "dir",
    },
    # morning_data
    {
        "src": os.path.join(PROJECT, "data", "morning_data.json"),
        "dst": "data/morning_data.json",
        "type": "file",
    },
    # 자동화 스크립트
    {
        "src": os.path.join(PROJECT, "automation"),
        "dst": "automation",
        "type": "dir",
    },
    # MCP 서버
    {
        "src": os.path.join(PROJECT, "mcp-server"),
        "dst": "mcp-server",
        "type": "dir",
    },
]

# 로깅
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backup")


def backup_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def backup_dir(src, dst, pattern=None):
    if pattern:
        os.makedirs(dst, exist_ok=True)
        import glob
        for f in glob.glob(os.path.join(src, pattern)):
            shutil.copy2(f, os.path.join(dst, os.path.basename(f)))
    else:
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, dirs_exist_ok=True)


def run_backup():
    today = datetime.now().strftime("%Y-%m-%d")
    backup_dir_today = os.path.join(BACKUP_BASE, today)
    os.makedirs(backup_dir_today, exist_ok=True)

    log.info(f"백업 시작 → {backup_dir_today}")
    success = 0
    failed = 0

    for target in BACKUP_TARGETS:
        src = target["src"]
        dst = os.path.join(backup_dir_today, target["dst"])
        btype = target["type"]
        pattern = target.get("pattern")

        try:
            if not os.path.exists(src):
                log.warning(f"  SKIP (없음): {src}")
                continue

            if btype == "file":
                backup_file(src, dst)
            elif btype == "dir":
                backup_dir(src, dst, pattern)

            log.info(f"  OK: {target['dst']}")
            success += 1
        except Exception as e:
            log.error(f"  FAIL: {target['dst']} — {e}")
            failed += 1

    # 최근 7일만 유지 (오래된 백업 삭제)
    try:
        all_backups = sorted([
            d for d in os.listdir(BACKUP_BASE)
            if os.path.isdir(os.path.join(BACKUP_BASE, d)) and d[:4] == "2026"
        ])
        if len(all_backups) > 7:
            for old in all_backups[:-7]:
                old_path = os.path.join(BACKUP_BASE, old)
                shutil.rmtree(old_path)
                log.info(f"  오래된 백업 삭제: {old}")
    except Exception as e:
        log.warning(f"  백업 정리 실패: {e}")

    log.info(f"백업 완료: 성공 {success}건, 실패 {failed}건")
    return success, failed


if __name__ == "__main__":
    run_backup()
