"""
instagram_bot.py — iLBiA 인스타그램 공동구매 DM 자동화
탐색: instagrapi (HTTP API, 빠르고 안정적)
DM 발송: Playwright (브라우저, 자연스러움)
"""

import asyncio
import random
import sqlite3
import json
import logging
import os
import re
import time
from datetime import datetime, date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# 1차 DM — 매번 조합 생성 (수백 가지 변형)
# ──────────────────────────────────────────
DM_OPENERS = [
    "{username}님 피드 보다가 멈췄어요.",
    "{username}님 피드 구경하다가 연락드려요.",
    "{username}님 계정 보다가 눈에 딱 들어왔어요.",
    "{username}님 피드 분위기가 너무 좋아서 용기 내서 연락드려요.",
    "{username}님 게시물 보다가 저도 모르게 팔로우 눌렀어요.",
    "{username}님 피드 보면서 이 분이다 싶었어요.",
    "{username}님 계정 우연히 발견했는데 분위기가 너무 좋아서요.",
]
DM_REASONS = [
    "저희가 만드는 세제랑 분위기가 너무 잘 맞아서요.",
    "저희 브랜드랑 느낌이 딱이라 멈출 수가 없었어요.",
    "저희 브랜드 감성이랑 정말 잘 어울릴 것 같아서요.",
    "생활용품 공구하시면 반응 좋을 것 같은 느낌이 확 와서요.",
    "팔로워분들이 좋아하실 것 같은 제품이 있어서요.",
    "저희 세제 브랜드랑 피드 톤이 잘 맞는 것 같아서요.",
]
DM_HOOKS = [
    "혹시 공동구매 해보신 적 있으신가요?",
    "공동구매 경험 있으세요?",
    "생활세제 공동구매 혹시 관심 있으실까요?",
    "혹시 공구 해보신 적 있으세요?",
    "생활용품 공구 관심 있으실까 해서요.",
    "혹시 공구에 관심 있으실지 여쭤보고 싶었어요.",
]
DM_CLOSERS = [
    "비코어랩 마케팅팀이에요 😊",
    "비코어랩 마케팅팀입니다 🙂",
    "iLBiA 만드는 비코어랩이에요 😊",
    "iLBiA 브랜드 비코어랩 마케팅팀이에요 🙂",
    "생활세제 브랜드 iLBiA, 비코어랩이에요 😊",
]
DM_EXTRA_EMOJIS = ["", " ☁️", " 🧺", " 🫧", " ✨", ""]

FOLLOWUP_TEMPLATE = """관심 가져주셔서 감사해요!
저희 iLBiA는 건조기시트, 캡슐세제, 식기세척기세제 등 생활세제 브랜드예요.

공구 조건은 {username}님 채널 특성에 맞게 함께 조율하고 싶어요 😊
- 샘플: 무료 발송
- 상세 이미지/링크 모두 저희가 준비해드려요
- 진행 방식·일정 모두 {username}님 편하신 대로 맞출게요

궁금하신 점 편하게 물어봐주세요!
비코어랩 마케팅팀 드림"""

TARGET_HASHTAGS = [
    "주부일상", "살림일기", "살림템", "세제추천", "주부스타그램",
    "살림스타그램", "주방살림", "세탁팁", "건조기", "캡슐세제",
    "살림꿀팁", "육아맘", "신혼살림", "주부생활", "살림노하우",
    "집스타그램", "홈스타그램", "살림고수", "주방용품", "세탁세제",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instagram.db')
SESSION_PATH = os.path.join(BASE_DIR, 'session.json')
API_SESSION_PATH = os.path.join(BASE_DIR, 'api_session.json')


def generate_dm(username):
    opener = random.choice(DM_OPENERS).replace('{username}', f'@{username}')
    reason = random.choice(DM_REASONS)
    hook = random.choice(DM_HOOKS)
    closer = random.choice(DM_CLOSERS) + random.choice(DM_EXTRA_EMOJIS)
    return f"{opener}\n{reason}\n{hook}\n{closer}"


# ──────────────────────────────────────────
# DB
# ──────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            followers INTEGER DEFAULT 0,
            avg_likes REAL DEFAULT 0,
            avg_comments REAL DEFAULT 0,
            like_rate REAL DEFAULT 0,
            comment_rate REAL DEFAULT 0,
            discovered_at TEXT DEFAULT (datetime('now', 'localtime')),
            status TEXT DEFAULT 'discovered',
            dm_sent_at TEXT,
            replied_at TEXT,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS dm_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            message TEXT,
            sent_at TEXT DEFAULT (datetime('now', 'localtime')),
            status TEXT DEFAULT 'sent',
            reply TEXT,
            reply_at TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    ''')
    defaults = {
        'daily_min': '20', 'daily_max': '30',
        'min_followers': '10000', 'max_followers': '100000',
        'min_like_rate': '0.005', 'max_like_rate': '0.02',
        'min_comment_rate': '0.002', 'max_comment_rate': '0.01',
        'ig_username': '', 'ig_password': '',
        'bot_active': 'false',
    }
    for k, v in defaults.items():
        conn.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v))
    conn.commit()
    conn.close()


def get_setting(key):
    conn = get_db()
    row = conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    conn.close()
    return row['value'] if row else None


def get_dm_count_today():
    conn = get_db()
    today = date.today().isoformat()
    count = conn.execute(
        "SELECT COUNT(*) as cnt FROM dm_log WHERE status='sent' AND date(sent_at)=?", (today,)
    ).fetchone()['cnt']
    conn.close()
    return count


# ──────────────────────────────────────────
# 계정 탐색 (instagrapi — HTTP API)
# ──────────────────────────────────────────
class AccountDiscovery:
    def __init__(self):
        self.cl = None

    def login(self, username, password):
        from instagrapi import Client
        self.cl = Client()
        self.cl.delay_range = [2, 5]

        if os.path.exists(API_SESSION_PATH):
            try:
                self.cl.load_settings(API_SESSION_PATH)
                self.cl.login(username, password)
                self.cl.account_info()
                logger.info("instagrapi: 저장된 세션으로 로그인 성공")
                return True
            except Exception:
                logger.info("instagrapi: 세션 만료, 재로그인...")
                self.cl = Client()
                self.cl.delay_range = [2, 5]

        try:
            self.cl.login(username, password)
            self.cl.dump_settings(API_SESSION_PATH)
            logger.info("instagrapi: 새 세션으로 로그인 성공")
            return True
        except Exception as e:
            logger.error(f"instagrapi 로그인 실패: {e}")
            return False

    def discover_hashtag(self, hashtag, amount=20):
        """해시태그에서 계정 탐색 + 메트릭 수집"""
        results = []
        seen = set()

        try:
            medias = self.cl.hashtag_medias_top(hashtag, amount=9)
            time.sleep(random.uniform(2, 4))
            medias += self.cl.hashtag_medias_recent(hashtag, amount=amount)
            logger.info(f"#{hashtag}: {len(medias)}개 게시물 발견")
        except Exception as e:
            logger.error(f"#{hashtag} 조회 실패: {e}")
            return results

        min_f = int(get_setting('min_followers') or 10000)
        max_f = int(get_setting('max_followers') or 100000)
        min_lr = float(get_setting('min_like_rate') or 0.005)
        max_lr = float(get_setting('max_like_rate') or 0.02)
        min_cr = float(get_setting('min_comment_rate') or 0.002)
        max_cr = float(get_setting('max_comment_rate') or 0.01)

        for media in medias:
            user_id = media.user.pk
            if user_id in seen:
                continue
            seen.add(user_id)

            try:
                time.sleep(random.uniform(2, 4))
                user = self.cl.user_info(user_id)

                if user.is_private:
                    continue

                followers = user.follower_count
                if not (min_f <= followers <= max_f):
                    continue

                # 최근 게시물에서 좋아요/댓글 평균
                avg_likes, avg_comments = self._calc_engagement(user_id)
                if not avg_likes:
                    continue

                like_rate = round(avg_likes / followers, 4) if followers else 0
                comment_rate = round(avg_comments / followers, 4) if followers else 0

                if not (min_lr <= like_rate <= max_lr and min_cr <= comment_rate <= max_cr):
                    # 기준 미달 — filtered
                    results.append({
                        'username': user.username, 'followers': followers,
                        'avg_likes': avg_likes, 'avg_comments': avg_comments,
                        'like_rate': like_rate, 'comment_rate': comment_rate,
                        'genuine': False,
                    })
                    continue

                results.append({
                    'username': user.username, 'followers': followers,
                    'avg_likes': round(avg_likes, 1), 'avg_comments': round(avg_comments, 1),
                    'like_rate': like_rate, 'comment_rate': comment_rate,
                    'genuine': True,
                })
                logger.info(f"✓ @{user.username} | 팔로워:{followers:,} | 좋아요율:{like_rate:.1%} | 댓글율:{comment_rate:.1%}")

            except Exception as e:
                logger.error(f"유저 {user_id} 조회 오류: {e}")
                continue

        genuine = sum(1 for r in results if r['genuine'])
        logger.info(f"#{hashtag} 결과: {len(results)}명 분석, {genuine}명 진성")
        return results

    def _calc_engagement(self, user_id, sample=6):
        try:
            medias = self.cl.user_medias(user_id, amount=sample)
        except Exception:
            return 0, 0
        if not medias:
            return 0, 0
        likes = [m.like_count for m in medias]
        comments = [m.comment_count for m in medias]
        return sum(likes) / len(likes), sum(comments) / len(comments)


# ──────────────────────────────────────────
# DM 발송 (Playwright — 브라우저)
# ──────────────────────────────────────────
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
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage']
        )
        ctx_kwargs = {
            'viewport': {'width': 390, 'height': 844},
            'user_agent': (
                'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
                'AppleWebKit/605.1.15 (KHTML, like Gecko) '
                'Version/16.6 Mobile/15E148 Safari/604.1'
            ),
            'locale': 'ko-KR',
        }
        if os.path.exists(SESSION_PATH):
            with open(SESSION_PATH) as f:
                ctx_kwargs['storage_state'] = json.load(f)
        self.context = await self.browser.new_context(**ctx_kwargs)
        self.page = await self.context.new_page()

    async def stop(self):
        try:
            if self.browser: await self.browser.close()
            if self.playwright: await self.playwright.stop()
        except:
            pass

    async def is_logged_in(self):
        try:
            await self.page.goto('https://www.instagram.com/', wait_until='networkidle', timeout=15000)
            await asyncio.sleep(2)
            return '/accounts/login/' not in self.page.url
        except:
            return False

    async def send_dm(self, username, message):
        try:
            await self.page.goto('https://www.instagram.com/direct/new/', wait_until='networkidle', timeout=15000)
            await asyncio.sleep(random.uniform(2, 3))

            search = await self.page.wait_for_selector('input[placeholder*="검색"]', timeout=8000)
            await search.fill(username)
            await asyncio.sleep(random.uniform(1.5, 2.5))

            result = await self.page.wait_for_selector(
                f'div[role="listbox"] span:has-text("{username}")', timeout=8000
            )
            await result.click()
            await asyncio.sleep(0.8)

            next_btn = await self.page.wait_for_selector('div[role="button"]:has-text("다음")', timeout=5000)
            await next_btn.click()
            await asyncio.sleep(random.uniform(1.5, 2.5))

            msg_box = await self.page.wait_for_selector('div[aria-label="메시지"]', timeout=8000)
            for char in message:
                await msg_box.type(char, delay=random.randint(30, 90))
            await asyncio.sleep(random.uniform(0.5, 1))

            await self.page.keyboard.press('Enter')
            await asyncio.sleep(random.uniform(2, 3))

            conn = get_db()
            conn.execute("UPDATE accounts SET status='dm_sent', dm_sent_at=? WHERE username=?",
                         (datetime.now().isoformat(), username))
            conn.execute("INSERT INTO dm_log (username, message, status) VALUES (?, ?, 'sent')",
                         (username, message))
            conn.commit()
            conn.close()
            logger.info(f"✅ DM 발송: @{username}")
            return True

        except Exception as e:
            logger.error(f"DM 실패 @{username}: {e}")
            conn = get_db()
            conn.execute("INSERT INTO dm_log (username, message, status) VALUES (?, ?, 'failed')",
                         (username, message))
            conn.commit()
            conn.close()
            return False


# ──────────────────────────────────────────
# 메인 루틴
# ──────────────────────────────────────────
async def run_bot():
    logger.info("=== 일일 DM 루틴 시작 ===")

    ig_user = get_setting('ig_username')
    ig_pass = get_setting('ig_password')
    has_session = os.path.exists(SESSION_PATH)

    if not ig_user or not ig_pass:
        if not has_session:
            logger.error("인스타 계정 미설정 — login_manual.py로 먼저 로그인해주세요")
            return

    daily_target = random.randint(
        int(get_setting('daily_min') or 20),
        int(get_setting('daily_max') or 30)
    )
    sent_today = get_dm_count_today()
    remaining = daily_target - sent_today

    if remaining <= 0:
        logger.info(f"오늘 목표 이미 달성 ({sent_today}/{daily_target})")
        return

    logger.info(f"목표: {daily_target}개 | 완료: {sent_today} | 남은: {remaining}")

    # ── 1단계: 대기 계정 확인 ──
    conn = get_db()
    pending = [r['username'] for r in
               conn.execute("SELECT username FROM accounts WHERE status='pending' LIMIT 100").fetchall()]
    conn.close()

    # ── 2단계: 부족하면 instagrapi로 탐색 ──
    if len(pending) < remaining * 2:
        logger.info("=== 계정 탐색 시작 (instagrapi) ===")
        discovery = AccountDiscovery()

        if ig_user and ig_pass:
            if not discovery.login(ig_user, ig_pass):
                logger.error("instagrapi 로그인 실패")
                if not pending:
                    return
            else:
                hashtag = random.choice(TARGET_HASHTAGS)
                logger.info(f"탐색: #{hashtag}")
                results = discovery.discover_hashtag(hashtag, amount=30)

                conn = get_db()
                for r in results:
                    status = 'pending' if r['genuine'] else 'filtered'
                    conn.execute('''
                        INSERT OR IGNORE INTO accounts (username, followers, avg_likes, avg_comments,
                        like_rate, comment_rate, status) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (r['username'], r['followers'], r['avg_likes'], r['avg_comments'],
                          r['like_rate'], r['comment_rate'], status))
                    if r['genuine'] and r['username'] not in pending:
                        pending.append(r['username'])
                conn.commit()
                conn.close()

    if not pending:
        logger.info("발송 대기 계정 없음 — 탐색을 더 해야 합니다")
        return

    # ── 3단계: Playwright로 DM 발송 ──
    logger.info(f"=== DM 발송 시작 (Playwright) — 대기: {len(pending)}명 ===")
    sender = DMSender()
    await sender.start()

    try:
        if not await sender.is_logged_in():
            logger.error("Playwright 세션 만료 — login_manual.py로 다시 로그인해주세요")
            return

        sent = 0
        random.shuffle(pending)
        for username in pending:
            if sent >= remaining:
                break

            wait = random.randint(60, 300)
            logger.info(f"⏳ {wait}초 대기 후 @{username}에게 발송...")
            await asyncio.sleep(wait)

            msg = generate_dm(username)
            if await sender.send_dm(username, msg):
                sent += 1

    finally:
        await sender.stop()

    logger.info(f"=== 완료: 오늘 총 {get_dm_count_today()}개 발송 ===")


if __name__ == '__main__':
    init_db()
    asyncio.run(run_bot())
