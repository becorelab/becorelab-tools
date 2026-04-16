"""Haiku 기반 유튜버 1차 스크리닝.

입력: 크롤러가 수집한 채널 데이터 (제목·설명·최근 영상 5개)
출력: {match_score 0~10, matched_products[], rationale, verdict}
  verdict: "approved" | "rejected" | "maybe"

비용 원칙 (미오 비용 3원칙):
  - 1차 스크리닝은 Haiku (저비용)
  - Opus는 pitch_write / 답장 분류에서만 사용
"""
import os
import json
import anthropic

PRODUCT_CATALOG = """iLBiA (생활세제 브랜드):
- 건조기 시트 (코튼블루 / 베이비크림 / 바이올렛 머스크) — 건조기 쓰는 가정
- 식기세척기 세제 — 식세기 사용자
- 캡슐 세제 — 세탁용
- 얼룩 제거제 — 육아/반려동물 가정
- 섬유 탈취제 (준비 중)

Omomo (아이디어 유통 브랜드):
- 주방·욕실·생활편의 아이템 (시즌별 변동)

타깃 채널 프로필:
- 주부/살림/인테리어/육아/반려동물/자취/미니멀 라이프
- 협업 가능성 낮음: 게임·음식 먹방·여행·뷰티(색조)·정치·투자"""


SCREENER_PROMPT = """너는 비코어랩(iLBiA/Omomo) 쿠팡 파트너스 유튜버 1차 스크리닝 담당이야.
아래 채널 데이터를 보고 협업 적합도를 평가해.

## 제품 카탈로그
{catalog}

## 평가 기준
1. 채널 주제가 타깃 프로필과 일치하는가? (가족·살림·육아·생활팁·자취)
2. 구독자 1만~10만 범위인가?
3. 최근 30일 업로드 활동 있는가?
4. 제품 카탈로그 중 자연스럽게 매칭되는 게 있는가?
5. 경쟁 브랜드(타사 세제) 광고 이력 의심되는가?

## 출력 (반드시 JSON만)
{{
  "match_score": 0~10 정수,
  "matched_products": ["제품명1", "제품명2"],
  "rationale": "한국어 1~2문장",
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


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def screen_channel(channel: dict, model: str = "claude-haiku-4-5-20251001") -> dict:
    """단일 채널 스크리닝. 반환: screen result dict."""
    # 입력 최소화 (토큰 절약)
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
    resp = _client().messages.create(
        model=model,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    # JSON만 추출 (코드펜스 대비)
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
    # 필수 필드 보강
    parsed.setdefault("matched_products", [])
    parsed.setdefault("red_flags", [])
    parsed.setdefault("verdict", "maybe")
    parsed.setdefault("match_score", 0)
    parsed.setdefault("rationale", "")
    parsed["model"] = model
    return parsed


def screen_batch(channels: list[dict], model: str = "claude-haiku-4-5-20251001") -> list[dict]:
    """N개 채널 연속 스크리닝 (순차 — 레이트리밋 회피 목적)."""
    results = []
    for ch in channels:
        try:
            result = screen_channel(ch, model=model)
        except Exception as e:
            result = {
                "match_score": 0,
                "matched_products": [],
                "rationale": f"스크리닝 실패: {e}",
                "verdict": "maybe",
                "red_flags": ["screener_exception"],
            }
        results.append({"channel": ch, "screen": result})
    return results


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    _dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(_dir, "..", "..", "sourcing", "analyzer", ".env"))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # 샘플 테스트 — API 키 없이도 프롬프트 생성만 확인 가능
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
