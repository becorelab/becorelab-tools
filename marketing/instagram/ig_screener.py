"""Haiku 기반 인스타그램 계정 1차 스크리닝.

입력: AccountDiscovery가 수집한 계정 데이터
출력: {match_score, rationale, verdict, personal_note}
  verdict: "approved" | "rejected" | "maybe"
"""
import json
import anthropic

PRODUCT_CATALOG = """iLBiA (생활세제 브랜드):
- 건조기 시트 (코튼블루 / 베이비크림 / 바이올렛 머스크) — 건조기 쓰는 가정
- 식기세척기 세제 — 식세기 사용자
- 캡슐 세제 — 세탁용
- 얼룩 제거제 — 육아/반려동물 가정
- 섬유 탈취제 (준비 중)

타깃 계정 프로필:
- 주부/살림/인테리어/육아/반려동물/자취/신혼 일상
- 적합하지 않음: 뷰티(색조)/여행/음식 먹방/게임/투자"""

SCREENER_PROMPT = """너는 비코어랩(iLBiA) 인스타그램 공동구매 파트너 1차 스크리닝 담당이야.
아래 계정 데이터를 보고 공동구매 협업 적합도를 평가해줘.

## 제품 카탈로그
{catalog}

## 평가 기준
1. 계정 주제가 생활/살림/주부/육아 관련인가?
2. 팔로워 1만~10만 범위인가?
3. 좋아요율·댓글율이 진성 팔로워 지표를 나타내는가?
4. 제품 카탈로그와 자연스럽게 매칭되는 카테고리인가?
5. 경쟁 브랜드 협찬 이력이 의심되는가? (발견 해시태그 기반)

## 출력 (반드시 JSON만)
{{
  "match_score": 0~10 정수,
  "matched_products": ["제품명"],
  "rationale": "한국어 1~2문장",
  "verdict": "approved" | "rejected" | "maybe",
  "red_flags": ["있으면 이슈"]
}}

verdict 기준:
- approved: score >= 7, 매칭 제품 1개 이상, red_flag 없음
- rejected: score <= 3 또는 완전 주제 불일치
- maybe: 그 외

## 계정 데이터
{account_json}

JSON만 출력. 설명 금지."""


def screen_account(account: dict, model: str = "claude-haiku-4-5-20251001") -> dict:
    trimmed = {
        "username": account.get("username"),
        "followers": account.get("followers"),
        "like_rate": account.get("like_rate"),
        "comment_rate": account.get("comment_rate"),
        "discovered_hashtag": account.get("discovered_hashtag", ""),
    }
    prompt = SCREENER_PROMPT.format(
        catalog=PRODUCT_CATALOG,
        account_json=json.dumps(trimmed, ensure_ascii=False, indent=2),
    )
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {
            "match_score": 0, "matched_products": [],
            "rationale": f"파서 실패: {text[:200]}",
            "verdict": "maybe", "red_flags": ["screener_parse_error"],
        }
    parsed.setdefault("matched_products", [])
    parsed.setdefault("red_flags", [])
    parsed.setdefault("verdict", "maybe")
    parsed.setdefault("match_score", 0)
    parsed.setdefault("rationale", "")
    parsed["model"] = model
    return parsed
