"""
instagram_bot.py — iLBiA 인스타그램 공동구매 DM 자동화
Playwright 기반 계정 탐색 + DM 발송
"""

import asyncio
import random
import sqlite3
import json
import logging
import os
import re
from datetime import datetime, date

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# 1차 DM — 매번 조합 생성 (수백 가지 변형)
# ──────────────────────────────────────────
# 각 파트를 랜덤 조합 → 매번 다른 메시지
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
    "iLBiA 일비아 드려요 😊",
    "iLBiA 일비아입니다 😊",
    "일비아(iLBiA)예요 🙂",
    "iLBiA 일비아라고 해요 😊",
    "생활세제 브랜드 일비아예요 🙂",
]

# 이모지 변형 (마지막에 랜덤 추가 or 생략)
DM_EXTRA_EMOJIS = ["", " ☁️", " 🧺", " 🫧", " ✨", ""]


def generate_dm(username):
    """매번 고유한 DM 생성 (7×6×6×5×6 = 7,560가지 조합)"""
    opener = random.choice(DM_OPENERS).replace('{username}', f'@{username}')
    reason = random.choice(DM_REASONS)
    hook = random.choice(DM_HOOKS)
    closer = random.choice(DM_CLOSERS) + random.choice(DM_EXTRA_EMOJIS)
    return f"{opener}\n{reason}\n{hook}\n{closer}"

# 2차 DM — 답장 후 수동 발송용 (대시보드에서 복사)
FOLLOWUP_TEMPLATE = """관심 가져주셔서 감사해요!
저희 iLBiA는 건조기시트, 캡슐세제, 식기세척기세제 등 생활세제 브랜드예요.

공구 조건 간단히 안내드릴게요 👇
- 수수료: 판매가의 20%
- 샘플: 무료 발송
- 상세 이미지/링크 모두 저희가 준비해드려요

진행 방식이나 일정은 {username}님 편하신 대로 맞출게요.
궁금하신 점 있으시면 편하게 물어봐주세요 😊"""

# 탐색할 해시태그
TARGET_HASHTAGS = [
    "주부일상", "살림일기", "살림템", "세제추천", "주부스타그램",
    "살림스타그램", "주방살림", "세탁팁", "건조기", "캡슐세제",
    "살림꿀팁", "육아맘", "신혼살림", "주부생활", "살림노하우",
    "집스타그램", "홈스타그램", "살림고수", "주방용품", "세탁세제",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instagram.db')
SESSION_PATH = os.path.join(BASE_DIR, 'session.json')


# ──────────────────────────────────────────
# DB 헬퍼
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
        'daily_min': '20',
        'daily_max': '30',
        'min_followers': '10000',
        'max_followers': '100000',
        'min_like_rate': '0.005',
        'max_like_rate': '0.02',
        'min_comment_rate': '0.002',
        'max_comment_rate': '0.01',
        'ig_username': '',
        'ig_password': '',
        'bot_active': 'false',
        'dm_template_idx': 'random',
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


def parse_korean_number(text):
    """'1.2만' → 12000, '123,456' → 123456"""
    if not text:
        return 0
    text = text.replace(',', '').strip()
    if '만' in text:
        try:
            return int(float(text.replace('만', '')) * 10000)
        except:
            return 0
    try:
        return int(re.sub(r'[^\d]', '', text))
    except:
        return 0


# ──────────────────────────────────────────
# Instagram Bot
# ──────────────────────────────────────────
class InstagramBot:
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
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ]
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
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except:
            pass

    async def save_session(self):
        state = await self.context.storage_state()
        with open(SESSION_PATH, 'w') as f:
            json.dump(state, f)
        logger.info("세션 저장 완료")

    async def _dismiss_popups(self):
        for text in ['모두 허용', '나중에 하기', '나중에', '건너뛰기']:
            try:
                btn = await self.page.query_selector(f'text={text}')
                if btn:
                    await btn.click()
                    await asyncio.sleep(1)
            except:
                pass

    async def login(self, username, password):
        logger.info(f"로그인 시도: {username}")
        await self.page.goto('https://www.instagram.com/', wait_until='networkidle')
        await asyncio.sleep(random.uniform(2, 4))
        await self._dismiss_popups()

        try:
            await self.page.fill('input[name="username"]', username)
            await asyncio.sleep(random.uniform(0.8, 1.5))
            await self.page.fill('input[name="password"]', password)
            await asyncio.sleep(random.uniform(0.8, 1.5))
            await self.page.click('button[type="submit"]')
            await asyncio.sleep(random.uniform(5, 8))
        except Exception as e:
            logger.error(f"로그인 입력 실패: {e}")
            return False

        await self._dismiss_popups()

        if '/accounts/login/' not in self.page.url:
            await self.save_session()
            logger.info("로그인 성공!")
            return True

        logger.error("로그인 실패")
        return False

    async def is_logged_in(self):
        try:
            await self.page.goto('https://www.instagram.com/', wait_until='networkidle', timeout=15000)
            await asyncio.sleep(2)
            return '/accounts/login/' not in self.page.url
        except:
            return False

    async def get_account_stats(self, username):
        """팔로워·좋아요율·댓글율 분석"""
        try:
            await self.page.goto(f'https://www.instagram.com/{username}/', wait_until='networkidle', timeout=15000)
            await asyncio.sleep(random.uniform(2, 3))

            # 비공개 체크
            if await self.page.query_selector('text=비공개 계정입니다'):
                return None

            # meta 태그에서 팔로워 파싱
            followers = 0
            meta = await self.page.query_selector('meta[name="description"]')
            if meta:
                content = await meta.get_attribute('content') or ''
                m = re.search(r'([\d,\.]+\s*만?)\s*팔로워', content)
                if m:
                    followers = parse_korean_number(m.group(1))
                else:
                    m = re.search(r'([\d,]+)\s*Followers', content)
                    if m:
                        followers = parse_korean_number(m.group(1))

            min_f = int(get_setting('min_followers') or 10000)
            max_f = int(get_setting('max_followers') or 100000)
            if not followers or not (min_f <= followers <= max_f):
                return None

            # 최근 게시물 좋아요·댓글 평균 (최대 6개)
            likes_list, comments_list = [], []
            try:
                post_links = await self.page.query_selector_all('article a[href*="/p/"]')
                for el in post_links[:6]:
                    try:
                        href = await el.get_attribute('href')
                        await self.page.goto(f'https://www.instagram.com{href}', wait_until='networkidle', timeout=10000)
                        await asyncio.sleep(random.uniform(1.5, 2.5))

                        # 좋아요
                        like_el = await self.page.query_selector('section span[class*="html-span"]')
                        if like_el:
                            txt = await like_el.inner_text()
                            n = parse_korean_number(txt)
                            if n:
                                likes_list.append(n)

                        # 댓글 수 (ul li 기준)
                        comment_els = await self.page.query_selector_all('ul > li > div > div > div > span')
                        comments_list.append(len(comment_els))

                        await self.page.go_back(wait_until='networkidle')
                        await asyncio.sleep(random.uniform(1, 2))
                    except:
                        continue
            except:
                pass

            avg_likes = sum(likes_list) / len(likes_list) if likes_list else 0
            avg_comments = sum(comments_list) / len(comments_list) if comments_list else 0

            return {
                'username': username,
                'followers': followers,
                'avg_likes': round(avg_likes, 1),
                'avg_comments': round(avg_comments, 1),
                'like_rate': round(avg_likes / followers, 4) if followers else 0,
                'comment_rate': round(avg_comments / followers, 4) if followers else 0,
            }
        except Exception as e:
            logger.error(f"{username} 분석 오류: {e}")
            return None

    def is_genuine(self, stats):
        """진성 계정 판별 (좋아요 0.5~2%, 댓글 0.2~1%)"""
        min_lr = float(get_setting('min_like_rate') or 0.005)
        max_lr = float(get_setting('max_like_rate') or 0.02)
        min_cr = float(get_setting('min_comment_rate') or 0.002)
        max_cr = float(get_setting('max_comment_rate') or 0.01)
        return (min_lr <= stats['like_rate'] <= max_lr and
                min_cr <= stats['comment_rate'] <= max_cr)

    async def discover_from_hashtag(self, hashtag, limit=20):
        """해시태그에서 계정 수집"""
        usernames = []
        try:
            await self.page.goto(f'https://www.instagram.com/explore/tags/{hashtag}/', wait_until='networkidle', timeout=15000)
            await asyncio.sleep(random.uniform(2, 4))

            posts = await self.page.query_selector_all('article a[href*="/p/"]')
            for post in posts[:limit]:
                try:
                    href = await post.get_attribute('href')
                    await self.page.goto(f'https://www.instagram.com{href}', wait_until='networkidle', timeout=10000)
                    await asyncio.sleep(random.uniform(1, 2))

                    author = await self.page.query_selector('header a[role="link"]')
                    if author:
                        uname = (await author.get_attribute('href') or '').strip('/')
                        if uname and uname not in usernames:
                            usernames.append(uname)

                    await self.page.go_back(wait_until='networkidle')
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                except:
                    continue
        except Exception as e:
            logger.error(f"#{hashtag} 탐색 오류: {e}")
        return usernames

    def _get_message(self, username):
        return generate_dm(username)

    async def send_dm(self, username, message):
        """DM 발송"""
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
    async def run_daily_job(self):
        logger.info("=== 일일 DM 루틴 시작 ===")

        ig_user = get_setting('ig_username')
        ig_pass = get_setting('ig_password')
        has_session = os.path.exists(SESSION_PATH)

        if not has_session and (not ig_user or not ig_pass):
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

        await self.start()
        try:
            if not await self.is_logged_in():
                if ig_user and ig_pass:
                    if not await self.login(ig_user, ig_pass):
                        logger.error("세션 만료 & 재로그인 실패 — login_manual.py로 다시 로그인해주세요")
                        return
                else:
                    logger.error("세션 만료 — login_manual.py로 다시 로그인해주세요")
                    return

            # 대기 계정 확인
            conn = get_db()
            pending = [r['username'] for r in
                       conn.execute("SELECT username FROM accounts WHERE status='pending' LIMIT 100").fetchall()]
            conn.close()

            # 부족하면 해시태그 탐색
            if len(pending) < remaining * 2:
                hashtag = random.choice(TARGET_HASHTAGS)
                logger.info(f"탐색: #{hashtag}")
                new_users = await self.discover_from_hashtag(hashtag, limit=30)

                conn = get_db()
                for u in new_users:
                    conn.execute(
                        'INSERT OR IGNORE INTO accounts (username, status) VALUES (?, "discovered")', (u,)
                    )
                conn.commit()
                conn.close()

                # 진성도 분석
                for u in new_users:
                    stats = await self.get_account_stats(u)
                    conn = get_db()
                    if stats and self.is_genuine(stats):
                        conn.execute('''
                            UPDATE accounts SET followers=?, avg_likes=?, avg_comments=?,
                            like_rate=?, comment_rate=?, status='pending' WHERE username=?
                        ''', (stats['followers'], stats['avg_likes'], stats['avg_comments'],
                              stats['like_rate'], stats['comment_rate'], u))
                        pending.append(u)
                        logger.info(f"✓ @{u} | 팔로워:{stats['followers']:,} | 좋아요율:{stats['like_rate']:.1%}")
                    else:
                        conn.execute("UPDATE accounts SET status='filtered' WHERE username=?", (u,))
                    conn.commit()
                    conn.close()
                    await asyncio.sleep(random.uniform(2, 5))

            # DM 발송
            sent = 0
            random.shuffle(pending)
            for username in pending:
                if sent >= remaining:
                    break
                # 1~5분 랜덤 딜레이
                wait = random.randint(60, 300)
                logger.info(f"⏳ {wait}초 대기 후 @{username}에게 발송...")
                await asyncio.sleep(wait)

                msg = self._get_message(username)
                if await self.send_dm(username, msg):
                    sent += 1

        finally:
            await self.stop()

        logger.info(f"=== 완료: 오늘 총 {get_dm_count_today()}개 발송 ===")


async def run_bot():
    bot = InstagramBot()
    await bot.run_daily_job()


if __name__ == '__main__':
    init_db()
    asyncio.run(run_bot())
