"""인스타 해시태그 기반 크롤러 — instagrapi.

기존 instagram_bot.py AccountDiscovery 계승.
해시태그 크롤 → 계정 메트릭 수집 → 룰 필터링.
"""
import logging
import os
import random
import re
import time

from config import (
    API_SESSION_PATH, IG_USERNAME, IG_PASSWORD,
    TARGET_HASHTAGS, MIN_FOLLOWERS, MAX_FOLLOWERS,
    MIN_ENGAGEMENT_RATE, MAX_ENGAGEMENT_RATE,
    MAX_FOLLOWING_RATIO, MAX_FOLLOWER_PER_POST, MAX_COMMENT_LIKE_RATIO,
    MAX_FOREIGN_FOLLOWER_RATIO, FOREIGN_CHECK_SAMPLE,
)

logger = logging.getLogger(__name__)


class InstaCrawler:
    def __init__(self):
        self.cl = None

    def login(self) -> bool:
        from instagrapi import Client
        self.cl = Client()
        self.cl.delay_range = [3, 6]

        username = IG_USERNAME
        password = IG_PASSWORD
        if not username or not password:
            logger.error("IG_USERNAME / IG_PASSWORD 환경변수 미설정")
            return False

        if os.path.exists(API_SESSION_PATH):
            try:
                self.cl.load_settings(API_SESSION_PATH)
                self.cl.login(username, password)
                self.cl.account_info()
                logger.info("instagrapi: 저장된 세션으로 로그인 성공")
                return True
            except Exception:
                logger.info("instagrapi: 세션 만료, 재로그인...")
                from instagrapi import Client
                self.cl = Client()
                self.cl.delay_range = [3, 6]

        try:
            self.cl.login(username, password)
            self.cl.dump_settings(API_SESSION_PATH)
            logger.info("instagrapi: 새 세션으로 로그인 성공")
            return True
        except Exception as e:
            logger.error(f"instagrapi 로그인 실패: {e}")
            return False

    def crawl_hashtags(
        self,
        hashtags: list[str] | None = None,
        max_per_tag: int = 30,
    ) -> list[dict]:
        """해시태그 기반 계정 크롤링. 룰 필터 통과한 계정만 반환."""
        if hashtags is None:
            hashtags = random.sample(TARGET_HASHTAGS, min(5, len(TARGET_HASHTAGS)))

        seen_usernames = set()
        results = []

        for tag in hashtags:
            logger.info(f"#{tag} 크롤 중...")
            try:
                medias = self.cl.hashtag_medias_top(tag, amount=9)
                time.sleep(random.uniform(3, 5))
                medias += self.cl.hashtag_medias_recent(tag, amount=max_per_tag)
                logger.info(f"  #{tag}: {len(medias)}개 게시물 발견")
            except Exception as e:
                logger.error(f"  #{tag} 조회 실패: {e}")
                continue

            for media in medias:
                user_id = media.user.pk
                username = media.user.username
                if username in seen_usernames:
                    continue
                seen_usernames.add(username)

                try:
                    time.sleep(random.uniform(3, 5))
                    user = self.cl.user_info(user_id)
                except Exception as e:
                    logger.error(f"  @{username} 조회 실패: {e}")
                    continue

                if user.is_private:
                    continue

                followers = user.follower_count
                if not (MIN_FOLLOWERS <= followers <= MAX_FOLLOWERS):
                    continue

                # 참여율 계산 (좋아요 숨김 대응 포함)
                avg_likes, avg_comments, captions, likes_hidden = self._calc_engagement(user_id)

                if likes_hidden:
                    # 좋아요 숨긴 계정 → 댓글 기반 참여율 (댓글은 보통 좋아요의 1/10~1/20)
                    # 댓글 참여율 0.3% 이상이면 좋아요 포함 시 3% 이상일 가능성 높음
                    comment_er = round(avg_comments / followers, 4) if followers else 0
                    er = round((avg_likes + avg_comments) / followers, 4) if followers else 0
                    if comment_er < 0.003 and er < MIN_ENGAGEMENT_RATE:
                        continue
                else:
                    if not avg_likes:
                        continue
                    er = round((avg_likes + avg_comments) / followers, 4) if followers else 0
                    if er < MIN_ENGAGEMENT_RATE:
                        continue

                # ── 가짜 팔로워/참여 감지 ──
                fake_flags = []
                following = user.following_count
                post_count = user.media_count

                # 1) 팔로잉/팔로워 비율 — 맞팔 교환 의심
                if followers > 0 and following / followers > MAX_FOLLOWING_RATIO:
                    fake_flags.append(f"팔로잉비율 {following/followers:.1f}")

                # 2) 참여율 상한 — 좋아요 봇 의심
                if not likes_hidden and er > MAX_ENGAGEMENT_RATE:
                    fake_flags.append(f"참여율 비정상 {er:.1%}")

                # 3) 게시물 대비 팔로워 — 콘텐츠 없이 팔로워만 많음
                if post_count > 0 and followers / post_count > MAX_FOLLOWER_PER_POST:
                    fake_flags.append(f"게시물당 팔로워 {followers/post_count:.0f}")

                # 4) 댓글/좋아요 비율 — 댓글 봇 의심
                if not likes_hidden and avg_likes > 0:
                    cl_ratio = avg_comments / avg_likes
                    if cl_ratio > MAX_COMMENT_LIKE_RATIO:
                        fake_flags.append(f"댓글/좋아요 {cl_ratio:.1%}")

                # 2개 이상 걸리면 컷
                if len(fake_flags) >= 2:
                    logger.info(f"  ✗ @{username} 가짜 의심 SKIP: {', '.join(fake_flags)}")
                    continue

                # 이메일 추출 (바이오에서)
                bio = user.biography or ""
                email = self._extract_email(bio)

                # 공구 경험 키워드 감지
                gonggu_keywords = ["공구", "공동구매", "오픈", "마감"]
                has_gonggu = any(
                    any(kw in cap for kw in gonggu_keywords)
                    for cap in captions
                )

                account = {
                    "username": username,
                    "user_id": str(user_id),
                    "bio": bio,
                    "followers": followers,
                    "following": following,
                    "post_count": post_count,
                    "avg_likes": round(avg_likes, 1),
                    "avg_comments": round(avg_comments, 1),
                    "engagement_rate": er,
                    "likes_hidden": likes_hidden,
                    "email": email,
                    "has_gonggu_experience": has_gonggu,
                    "recent_captions": captions,
                    "profile_url": f"https://www.instagram.com/{username}/",
                    "fake_flags": fake_flags,
                }

                results.append(account)
                hidden_tag = " [좋아요숨김]" if likes_hidden else ""
                logger.info(
                    f"  ✓ @{username} | 팔로워:{followers:,} | "
                    f"ER:{er:.1%}{hidden_tag} | 이메일:{'O' if email else 'X'} | "
                    f"공구경험:{'O' if has_gonggu else 'X'}"
                )

            time.sleep(random.uniform(5, 10))

        logger.info(f"크롤 완료: {len(results)}명 적격")
        return results

    def _calc_engagement(self, user_id, sample: int = 6):
        """최근 게시물에서 좋아요/댓글 평균 + 캡션 수집.

        좋아요 숨김 대응: like_count=0이 절반 이상이면
        0인 게시물을 평균에서 제외하고, likes_hidden 플래그 반환.
        """
        try:
            medias = self.cl.user_medias(user_id, amount=sample)
        except Exception:
            return 0, 0, [], False
        if not medias:
            return 0, 0, [], False

        all_likes = [m.like_count for m in medias]
        comments = [m.comment_count for m in medias]
        captions = [(m.caption_text or "") for m in medias]

        zero_count = sum(1 for lk in all_likes if lk == 0)
        likes_hidden = zero_count >= len(medias) / 2

        if likes_hidden:
            visible = [lk for lk in all_likes if lk > 0]
            avg_likes = sum(visible) / len(visible) if visible else 0
        else:
            avg_likes = sum(all_likes) / len(all_likes)

        avg_comments = sum(comments) / len(comments)
        return avg_likes, avg_comments, captions, likes_hidden

    def check_foreign_followers(self, user_id: str, sample: int = None) -> dict:
        """팔로워 샘플에서 외국인 비율 추정.

        한국어(가-힣) 포함 여부로 판단:
        username 또는 full_name에 한글이 없으면 외국인으로 간주.
        Haiku 스크리닝 통과 후보만 대상으로 호출 (API 부하 절감).
        """
        if sample is None:
            sample = FOREIGN_CHECK_SAMPLE

        try:
            time.sleep(random.uniform(3, 5))
            followers = self.cl.user_followers(int(user_id), amount=sample)
        except Exception as e:
            logger.warning(f"팔로워 목록 조회 실패 (user_id={user_id}): {e}")
            return {"foreign_ratio": None, "checked": False}

        if not followers:
            return {"foreign_ratio": None, "checked": False}

        korean_re = re.compile(r'[가-힣]')
        foreign_count = 0
        total = 0

        for uid, user in followers.items():
            total += 1
            username = user.username or ""
            full_name = user.full_name or ""
            if not korean_re.search(username) and not korean_re.search(full_name):
                foreign_count += 1

        ratio = round(foreign_count / total, 2) if total > 0 else 0
        logger.info(
            f"  외국인 팔로워: {foreign_count}/{total} ({ratio:.0%})"
        )
        return {
            "foreign_ratio": ratio,
            "foreign_count": foreign_count,
            "sample_total": total,
            "checked": True,
            "is_suspicious": ratio > MAX_FOREIGN_FOLLOWER_RATIO,
        }

    @staticmethod
    def _extract_email(bio: str) -> str:
        """바이오에서 이메일 추출."""
        match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', bio)
        return match.group(0) if match else ""
