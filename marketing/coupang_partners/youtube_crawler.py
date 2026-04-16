"""YouTube Data API v3 래퍼 — 마이크로 유튜버 탐색.

사용 API:
  - search.list          채널 검색
  - channels.list        구독자/업로드 플레이리스트 조회
  - playlistItems.list   최근 업로드 영상

인증: Google Cloud API Key (YOUTUBE_API_KEY 또는 GEMINI_API_KEY fallback).
     프로젝트에 YouTube Data API v3 활성화 필요.
"""
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import MIN_SUBSCRIBERS, MAX_SUBSCRIBERS, MAX_UPLOAD_DAYS


def _api_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "YOUTUBE_API_KEY (or GEMINI_API_KEY) 환경변수 없음. "
            "sourcing/analyzer/.env 또는 mio.env에 설정."
        )
    return key


_client = None


def _yt():
    global _client
    if _client is None:
        _client = build("youtube", "v3", developerKey=_api_key(), cache_discovery=False)
    return _client


def search_channels_by_keyword(keyword: str, max_pages: int = 2,
                                region: str = "KR", lang: str = "ko") -> list[str]:
    """키워드로 영상 검색 → 채널 ID 중복 제거. 보통 페이지당 50 videos → ~30 unique channels."""
    yt = _yt()
    channel_ids: dict[str, None] = {}
    page_token = None
    for _ in range(max_pages):
        req = yt.search().list(
            q=keyword,
            part="snippet",
            type="video",
            maxResults=50,
            order="relevance",
            regionCode=region,
            relevanceLanguage=lang,
            pageToken=page_token,
        )
        resp = req.execute()
        for item in resp.get("items", []):
            cid = (item.get("snippet") or {}).get("channelId")
            if cid:
                channel_ids.setdefault(cid, None)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return list(channel_ids.keys())


def enrich_channels(channel_ids: list[str]) -> list[dict]:
    """channels.list 일괄 호출 (50개씩). 각 채널의 통계·업로드 플레이리스트 반환."""
    yt = _yt()
    results = []
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i + 50]
        resp = yt.channels().list(
            id=",".join(batch),
            part="snippet,statistics,contentDetails,brandingSettings",
        ).execute()
        for ch in resp.get("items", []):
            stats = ch.get("statistics") or {}
            snippet = ch.get("snippet") or {}
            content = ch.get("contentDetails") or {}
            branding = (ch.get("brandingSettings") or {}).get("channel") or {}
            subs = int(stats.get("subscriberCount", 0)) if not stats.get("hiddenSubscriberCount") else 0
            results.append({
                "channel_id": ch.get("id"),
                "title": snippet.get("title"),
                "description": snippet.get("description") or "",
                "country": snippet.get("country") or "",
                "published_at": snippet.get("publishedAt"),
                "thumbnail": (snippet.get("thumbnails") or {}).get("default", {}).get("url"),
                "subscriber_count": subs,
                "video_count": int(stats.get("videoCount", 0)),
                "view_count": int(stats.get("viewCount", 0)),
                "uploads_playlist": (content.get("relatedPlaylists") or {}).get("uploads"),
                "keywords": branding.get("keywords") or "",
                "custom_url": snippet.get("customUrl") or "",
            })
    return results


def recent_uploads(uploads_playlist_id: str, max_results: int = 5) -> list[dict]:
    """업로드 플레이리스트의 최근 영상. 제목·조회수·업로드일."""
    if not uploads_playlist_id:
        return []
    yt = _yt()
    resp = yt.playlistItems().list(
        playlistId=uploads_playlist_id,
        part="snippet,contentDetails",
        maxResults=max_results,
    ).execute()
    video_ids = [
        (it.get("contentDetails") or {}).get("videoId")
        for it in resp.get("items", [])
    ]
    video_ids = [v for v in video_ids if v]
    if not video_ids:
        return []
    stats_resp = yt.videos().list(
        id=",".join(video_ids),
        part="snippet,statistics",
    ).execute()
    out = []
    for v in stats_resp.get("items", []):
        snip = v.get("snippet") or {}
        stats = v.get("statistics") or {}
        out.append({
            "video_id": v.get("id"),
            "title": snip.get("title"),
            "published_at": snip.get("publishedAt"),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "url": f"https://www.youtube.com/watch?v={v.get('id')}",
        })
    return out


def _find_contact_email(description: str) -> Optional[str]:
    """채널 설명에서 이메일 추출 (비즈니스 문의용)."""
    import re
    if not description:
        return None
    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", description)
    return m.group(0) if m else None


def is_fresh_channel(channel: dict) -> bool:
    """최근 MAX_UPLOAD_DAYS일 이내 업로드 있으면 True (폴러 개념 — '잠수 아님')."""
    uploads = channel.get("recent_videos") or []
    if not uploads:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_UPLOAD_DAYS)
    for v in uploads:
        pub = v.get("published_at")
        if not pub:
            continue
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if dt >= cutoff:
                return True
        except Exception:
            continue
    return False


def is_in_tier(channel: dict) -> bool:
    """구독자 MIN~MAX 범위 (PRD §5)."""
    subs = channel.get("subscriber_count", 0)
    return MIN_SUBSCRIBERS <= subs <= MAX_SUBSCRIBERS


def enrich_full(channel_id: str) -> dict:
    """단일 채널 전체 수집 (stats + recent videos + contact email)."""
    base_list = enrich_channels([channel_id])
    if not base_list:
        raise ValueError(f"채널 조회 실패: {channel_id}")
    ch = base_list[0]
    ch["recent_videos"] = recent_uploads(ch.get("uploads_playlist") or "")
    ch["contact_email"] = _find_contact_email(ch.get("description") or "")
    ch["is_in_tier"] = is_in_tier(ch)
    ch["is_fresh"] = is_fresh_channel(ch)
    ch["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return ch


if __name__ == "__main__":
    import sys
    import json
    from dotenv import load_dotenv
    _dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(_dir, "..", "..", "sourcing", "analyzer", ".env"))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("usage: python youtube_crawler.py <keyword-or-UCxxxx>")
        sys.exit(1)
    arg = sys.argv[1]
    if arg.startswith("UC"):
        data = enrich_full(arg)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        cids = search_channels_by_keyword(arg)
        print(f"found {len(cids)} channels for keyword '{arg}'")
        for c in cids[:10]:
            print(f"  {c}")
