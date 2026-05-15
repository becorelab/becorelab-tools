"""Haiku 기반 인스타 공구 진행자 스크리닝.

입력: 크롤러가 수집한 인스타 계정 데이터
출력: {match_score 0~100, category, gonggu_experience, rationale, personal_hook, verdict}
"""
import json
import anthropic


SCREENER_PROMPT = """너는 비코어랩(iLBiA) 인스타 공동구매 진행자 1차 스크리닝 담당이야.
아래 인스타 계정 데이터를 보고 공구 적합도를 평가해줘.

## 브랜드 & 제품
iLBiA(일비아) — 패밀리케어 생활세제 브랜드:
- 건조기 시트 (코튼블루 / 베이비크림 / 바이올렛 머스크)
- 식기세척기 세제
- 캡슐 세제
- 얼룩 제거제

## 이상적인 공구 진행자
- 카테고리: 살림·청소·육아·주방·미니멀라이프·리빙
- 팔로워 5천~5만 (마이크로·미드)
- 참여율(좋아요+댓글÷팔로워) 3% 이상
- 공구 경험 있으면 우대
- 실생활 콘텐츠, 진정성 있는 톤

## 부적합 신호
- 광고·협찬 과다 (전체 게시물의 50% 이상)
- 팔로워 대비 참여율 극히 낮음 (가짜 팔로워 의심)
- 카테고리 불일치 (뷰티 색조·게임·여행·정치·투자)
- 최근 활동 없음

## 개인화 훅(personal_hook) 생성
- 최근 게시물 중 가장 관련성 높은 것 하나를 구체적으로 언급
- 예: "최근 올리신 '세탁조 청소' 게시물 보고 연락드리게 됐어요."
- 한국어 1문장, 담백하게. 적절한 게시물 없으면 "" 반환

## 출력 (반드시 JSON만)
{{
  "match_score": 0~100 정수,
  "category": "살림/육아/리뷰/기타",
  "gonggu_experience": true/false,
  "matched_products": ["건조기 시트", ...],
  "rationale": "한국어 1~2문장",
  "personal_hook": "위 규칙대로 생성한 한 문장 또는 빈 문자열",
  "verdict": "approved" | "rejected" | "maybe",
  "red_flags": []
}}

verdict 기준:
- approved: score >= 60, 매칭 제품 1개 이상, red_flag 없음
- rejected: score <= 25 또는 카테고리 완전 불일치
- maybe: 그 외

## 계정 데이터
{account_json}

JSON만 출력. 설명 금지."""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def screen_account(account: dict, model: str = "claude-haiku-4-5-20251001") -> dict:
    """단일 인스타 계정 스크리닝."""
    trimmed = {
        "username": account.get("username"),
        "bio": (account.get("bio") or "")[:500],
        "followers": account.get("followers"),
        "following": account.get("following"),
        "post_count": account.get("post_count"),
        "engagement_rate": account.get("engagement_rate"),
        "likes_hidden": account.get("likes_hidden", False),
        "following_ratio": round(account.get("following", 0) / max(account.get("followers", 1), 1), 2),
        "fake_flags": account.get("fake_flags", []),
        "recent_captions": [
            c[:200] for c in (account.get("recent_captions") or [])[:5]
        ],
        "has_email": bool(account.get("email")),
    }
    prompt = SCREENER_PROMPT.format(
        account_json=json.dumps(trimmed, ensure_ascii=False, indent=2),
    )
    resp = _client().messages.create(
        model=model,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {
            "match_score": 0,
            "category": "unknown",
            "gonggu_experience": False,
            "matched_products": [],
            "rationale": f"파서 실패: {text[:200]}",
            "personal_hook": "",
            "verdict": "maybe",
            "red_flags": ["screener_parse_error"],
        }

    parsed.setdefault("match_score", 0)
    parsed.setdefault("category", "기타")
    parsed.setdefault("gonggu_experience", False)
    parsed.setdefault("matched_products", [])
    parsed.setdefault("rationale", "")
    parsed.setdefault("personal_hook", "")
    parsed.setdefault("verdict", "maybe")
    parsed.setdefault("red_flags", [])
    parsed["model"] = model
    return parsed
