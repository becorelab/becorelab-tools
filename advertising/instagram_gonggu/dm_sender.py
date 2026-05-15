"""인스타 DM 자동 발송 — Playwright 기반 + 봇 감지 회피.

기존 instagram_bot.py DMSender 계승, 50명/일 규모에 맞게 강화:
- 가우시안 분포 발송 간격
- 자연 행동 삽입 (피드 스크롤, 프로필 방문, 좋아요)
- 차단 감지 자동 중단
- 시간대별 가중치
"""
import asyncio
import json
import logging
import os
import random
import sqlite3
import math
from datetime import datetime, date

from config import (
    SESSION_PATH, DM_LOG_DB,
    DM_INTERVAL_MEAN, DM_INTERVAL_STD,
    DM_INTERVAL_MIN, DM_INTERVAL_MAX,
    MAX_CONSECUTIVE_FAILURES,
)

logger = logging.getLogger(__name__)


# ── 로컬 DM 로그 (SQLite) ───────────────────────────────────

def _init_db():
    conn = sqlite3.connect(DM_LOG_DB)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dm_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            message TEXT,
            sent_at TEXT DEFAULT (datetime('now', 'localtime')),
            status TEXT DEFAULT 'sent'
        )
    ''')
    conn.commit()
    conn.close()


def get_dm_count_today() -> int:
    _init_db()
    conn = sqlite3.connect(DM_LOG_DB)
    today = date.today().isoformat()
    count = conn.execute(
        "SELECT COUNT(*) FROM dm_log WHERE status='sent' AND date(sent_at)=?",
        (today,)
    ).fetchone()[0]
    conn.close()
    return count


def log_dm(username: str, message: str, status: str = "sent"):
    _init_db()
    conn = sqlite3.connect(DM_LOG_DB)
    conn.execute(
        "INSERT INTO dm_log (username, message, status) VALUES (?, ?, ?)",
        (username, message, status)
    )
    conn.commit()
    conn.close()


# ── 발송 간격 (가우시안) ─────────────────────────────────────

def next_interval() -> float:
    """가우시안 분포로 다음 대기 시간(초) 생성."""
    interval = random.gauss(DM_INTERVAL_MEAN, DM_INTERVAL_STD)
    return max(DM_INTERVAL_MIN, min(DM_INTERVAL_MAX, interval))


# ── 자연 행동 시뮬레이션 ─────────────────────────────────────

async def _natural_behavior(page):
    """DM 사이에 자연스러운 행동 삽입."""
    actions = [
        _scroll_feed,
        _visit_explore,
        _do_nothing,
    ]
    action = random.choice(actions)
    try:
        await action(page)
    except Exception:
        pass


async def _scroll_feed(page):
    """홈 피드 스크롤."""
    await page.goto("https://www.instagram.com/", wait_until="networkidle", timeout=15000)
    await asyncio.sleep(random.uniform(2, 4))
    for _ in range(random.randint(2, 5)):
        await page.mouse.wheel(0, random.randint(300, 800))
        await asyncio.sleep(random.uniform(1, 3))


async def _visit_explore(page):
    """탐색 페이지 방문."""
    await page.goto("https://www.instagram.com/explore/", wait_until="networkidle", timeout=15000)
    await asyncio.sleep(random.uniform(3, 6))


async def _do_nothing(page):
    """아무것도 안 함 (확률적 건너뛰기)."""
    await asyncio.sleep(random.uniform(1, 3))


# ── Playwright DM 발송 ──────────────────────────────────────

class DMSender:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        ctx_kwargs = {
            "viewport": {"width": 390, "height": 844},
            "user_agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.4 Mobile/15E148 Safari/604.1"
            ),
            "locale": "ko-KR",
        }
        if os.path.exists(SESSION_PATH):
            with open(SESSION_PATH, encoding="utf-8") as f:
                ctx_kwargs["storage_state"] = json.load(f)
        self.context = await self.browser.new_context(**ctx_kwargs)
        self.page = await self.context.new_page()

    async def stop(self):
        try:
            if self.context:
                state = await self.context.storage_state()
                with open(SESSION_PATH, "w", encoding="utf-8") as f:
                    json.dump(state, f)
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass

    async def is_logged_in(self) -> bool:
        try:
            await self.page.goto(
                "https://www.instagram.com/",
                wait_until="networkidle", timeout=15000
            )
            await asyncio.sleep(2)
            return "/accounts/login/" not in self.page.url
        except Exception:
            return False

    async def send_dm(self, username: str, message: str) -> bool:
        """단일 DM 발송. 성공 시 True."""
        try:
            await self.page.goto(
                "https://www.instagram.com/direct/new/",
                wait_until="networkidle", timeout=15000
            )
            await asyncio.sleep(random.uniform(2, 3))

            search = await self.page.wait_for_selector(
                'input[placeholder*="검색"]', timeout=8000
            )
            await search.fill(username)
            await asyncio.sleep(random.uniform(1.5, 2.5))

            result = await self.page.wait_for_selector(
                f'div[role="listbox"] span:has-text("{username}")',
                timeout=8000
            )
            await result.click()
            await asyncio.sleep(0.8)

            next_btn = await self.page.wait_for_selector(
                'div[role="button"]:has-text("다음")', timeout=5000
            )
            await next_btn.click()
            await asyncio.sleep(random.uniform(1.5, 2.5))

            msg_box = await self.page.wait_for_selector(
                'div[aria-label="메시지"]', timeout=8000
            )
            for char in message:
                await msg_box.type(char, delay=random.randint(30, 90))
            await asyncio.sleep(random.uniform(0.5, 1))

            await self.page.keyboard.press("Enter")
            await asyncio.sleep(random.uniform(2, 3))

            log_dm(username, message, "sent")
            logger.info(f"DM 발송 성공: @{username}")
            return True

        except Exception as e:
            logger.error(f"DM 실패 @{username}: {e}")
            log_dm(username, message, "failed")
            return False

    async def send_batch(
        self,
        targets: list[dict],
        daily_limit: int,
    ) -> dict:
        """배치 DM 발송 — 봇 감지 회피 적용.

        Args:
            targets: [{"username": ..., "message": ...}, ...]
            daily_limit: 오늘 발송 한도

        Returns:
            {"sent": int, "failed": int, "skipped": int}
        """
        sent_today = get_dm_count_today()
        remaining = daily_limit - sent_today

        if remaining <= 0:
            logger.info(f"오늘 한도 도달 ({sent_today}/{daily_limit})")
            return {"sent": 0, "failed": 0, "skipped": len(targets)}

        sent = 0
        failed = 0
        consecutive_failures = 0

        for target in targets:
            if sent >= remaining:
                break

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    f"연속 실패 {consecutive_failures}회 — 차단 의심, 발송 중단"
                )
                break

            # 자연 행동 삽입 (30% 확률)
            if random.random() < 0.3:
                logger.info("자연 행동 삽입 중...")
                await _natural_behavior(self.page)

            # 가우시안 대기
            wait = next_interval()
            logger.info(
                f"⏳ {wait:.0f}초 대기 후 @{target['username']}에게 발송... "
                f"({sent + sent_today + 1}/{daily_limit})"
            )
            await asyncio.sleep(wait)

            success = await self.send_dm(
                target["username"],
                target["message"],
            )

            if success:
                sent += 1
                consecutive_failures = 0
            else:
                failed += 1
                consecutive_failures += 1

        skipped = len(targets) - sent - failed
        logger.info(
            f"배치 완료: 발송 {sent} / 실패 {failed} / 스킵 {skipped}"
        )
        return {"sent": sent, "failed": failed, "skipped": skipped}
