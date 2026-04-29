"""Gemini Flash 기반 유튜버 1차 스크리닝.

입력: 크롤러가 수집한 채널 데이터 (제목·설명·최근 영상 5개)
출력: {match_score 0~10, matched_products[], rationale, verdict}
  verdict: "approved" | "rejected" | "maybe"

비용 원칙:
  - 1차 스크리닝은 Gemini Flash (무료 티어)
  - Opus는 pitch_write / 답장 분류에서만 사용
"""
import os
import json
import requests

_DIR = os.path.dirname(os.path.abspath(__file__))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    _env_path = os.path.join(_DIR, "..", "..", "sourcing", "analyzer", ".env")
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                if _line.startswith("GEMINI_API_KEY=") and not GEMINI_API_KEY:
                    GEMINI_API_KEY = _line.split("=", 1)[1].strip()

PRODUCT_CATALOG = """iLBiA (생활세제 브랜드):
- 건조기 시트 (코튼블루 / 베이비크림 / 바이올렛 머스크) — 건조기 쓰는 가정, 세탁 루틴, 빨래 관리
- 식기세척기 세제 — 식세기 사용자, 주방 살림, 홈카페
- 캡슐 세제 — 세탁용, 자취생, 원룸, 미니멀 살림
- 얼룩 제거제 — 육아/반려동물 가정, 캠핑/아웃도어, 세탁 꿀팁
- 섬유 탈취제 (준비 중) — 반려동물, 자취, 겨울옷 관리, 원룸

Omomo (아이디어 유통 브랜드):
- 주방·욕실·생활편의 아이템 (시즌별 변동)

타깃 채널 프로필 (넓게 평가):
- 핵심: 살림/육아/세탁/빨래/청소
- 확장: 자취/원룸/신혼/이사/홈인테리어/미니멀 라이프
- 니치: 반려동물/캠핑/홈카페/정리수납/주방/욕실
- 협업 가능성 낮음: 게임·음식 먹방·여행전문·뷰티(색조)·정치·투자·IT리뷰"""


SCREENER_PROMPT = """너는 비코어랩(iLBiA/Omomo) 쿠팡 파트너스 유튜버 1차 스크리닝 담당이야.
아래 채널 데이터를 보고 협업 적합도 평가 + 개인화 인사 문장을 생성해줘.

## 제품 카탈로그
{catalog}

## 평가 기준 (넓게 보되, 매칭 근거를 구체적으로)
1. 채널 주제가 타깃 프로필과 겹치는가?
   - 핵심 매칭: 살림·육아·세탁·빨래·청소 → 높은 점수
   - 확장 매칭: 자취·원룸·신혼·이사·홈인테리어·미니멀 라이프 → 중간 점수
   - 니치 매칭: 반려동물·캠핑·홈카페·정리수납·주방·욕실 → 제품 연결 시 중간 점수
2. 구독자 1만~10만 범위인가?
3. 최근 30일 업로드 활동 있는가?
4. 제품 카탈로그 중 자연스럽게 매칭되는 게 있는가?
   - 건조기 시트: 건조기 후기, 빨래 루틴, 세탁팁
   - 식기세척기 세제: 주방정리, 식세기 후기, 홈카페
   - 캡슐 세제: 자취 살림, 세탁법, 원룸 살림
   - 얼룩 제거제: 육아 빨래, 반려동물 생활, 캠핑 세탁
   - 섬유 탈취제: 반려동물 냄새, 자취방 관리, 겨울옷
5. 경쟁 브랜드(타사 세제) 광고 이력 의심되는가?

## 개인화 훅(personal_hook) 생성 규칙
- 최근 영상 중 가장 인상적/관련성 높은 영상 제목 하나를 구체적으로 언급
- 형식 예시: "특히 최근 올리신 '○○○' 영상 재밌게 봤어요." / "'○○○' 영상 보면서 실제 쓰는 입장에서 잘 정리하신다 싶었어요."
- 영상 제목은 그대로 인용 (줄여서 요점만 가능, 하지만 원문 느낌 유지)
- 한국어 1문장, 아첨·과장 금지, 담백하게
- 제품 카탈로그와 연관 있는 영상 우선 선택
- 적절한 영상이 없으면 "" (빈 문자열) 반환

## 출력 (반드시 JSON만)
{{
  "match_score": 0~10 정수,
  "matched_products": ["제품명1", "제품명2"],
  "rationale": "한국어 1~2문장",
  "personal_hook": "위 규칙대로 생성한 한 문장 또는 빈 문자열",
  "verdict": "approved" | "rejected" | "maybe",
  "red_flags": ["있으면 이슈 목록"]
}}

verdict 기준:
- approved: score >= 7, 매칭 제품 1개 이상, red_flag 없음
- rejected: score <= 3 또는 채널 주제 완전 불일치
- maybe: 그 외 (대표님 검토 필요)

## 채널 데이터
{channel_json}

JSON만 출력. 설명 금지."""


GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def _call_gemini(prompt: str, max_retries: int = 3) -> str:
    """Gemini REST API 호출. 429/503 시 재시도."""
    import time
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다")
    for attempt in range(max_retries):
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": 1024,
                    "temperature": 0.1,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
            timeout=60,
        )
        if resp.ok:
            break
        if resp.status_code in (429, 503) and attempt < max_retries - 1:
            time.sleep(5 * (attempt + 1))
            continue
        raise RuntimeError(f"Gemini API {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        if parts:
            return parts[0].get("text", "")
    raise RuntimeError(f"Gemini 빈 응답: {json.dumps(data)[:200]}")


def screen_channel(channel: dict, model: str = GEMINI_MODEL) -> dict:
    """단일 채널 스크리닝. 반환: screen result dict."""
    trimmed = {
        "channel_id": channel.get("channel_id"),
        "title": channel.get("title"),
        "description": (channel.get("description") or "")[:500],
        "subscriber_count": channel.get("subscriber_count"),
        "video_count": channel.get("video_count"),
        "is_in_tier": channel.get("is_in_tier"),
        "is_fresh": channel.get("is_fresh"),
        "keywords": channel.get("keywords") or "",
        "recent_videos": [
            {"title": v.get("title"), "views": v.get("view_count")}
            for v in (channel.get("recent_videos") or [])[:5]
        ],
    }
    prompt = SCREENER_PROMPT.format(
        catalog=PRODUCT_CATALOG,
        channel_json=json.dumps(trimmed, ensure_ascii=False, indent=2),
    )
    text = _call_gemini(prompt).strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {
            "match_score": 0,
            "matched_products": [],
            "rationale": f"파서 실패: {text[:200]}",
            "verdict": "maybe",
            "red_flags": ["screener_parse_error"],
        }
    parsed.setdefault("matched_products", [])
    parsed.setdefault("red_flags", [])
    parsed.setdefault("verdict", "maybe")
    parsed.setdefault("match_score", 0)
    parsed.setdefault("rationale", "")
    parsed.setdefault("personal_hook", "")
    parsed["model"] = model
    return parsed


def screen_batch(channels: list[dict], model: str = GEMINI_MODEL) -> list[dict]:
    """N개 채널 연속 스크리닝 (순차 — 레이트리밋 회피 목적)."""
    results = []
    for ch in channels:
        try:
            result = screen_channel(ch, model=model)
        except Exception as e:
            result = {
                "match_score": 0,
                "matched_products": [],
                "rationale": "스크리닝 재시도 필요",
                "verdict": "retry",
                "red_flags": ["screener_exception"],
                "_error_detail": str(e)[:200],
            }
        results.append({"channel": ch, "screen": result})
    return results


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    sample = {
        "channel_id": "UCsample",
        "title": "살림하는 엄마",
        "description": "두 아이 엄마의 정리수납 · 주방살림 브이로그. 건조기·세탁 팁.",
        "subscriber_count": 35000,
        "video_count": 120,
        "is_in_tier": True,
        "is_fresh": True,
        "recent_videos": [
            {"title": "건조기 사용 3년 후기 💦", "view_count": 8200},
            {"title": "식세기 세제 비교해봤어요", "view_count": 5400},
        ],
    }
    result = screen_channel(sample)
    print(json.dumps(result, ensure_ascii=False, indent=2))
