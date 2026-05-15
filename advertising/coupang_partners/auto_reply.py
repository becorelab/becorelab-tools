"""유튜버 회신 자동 분류 + 답장 모듈.

회신 내용을 Haiku로 분류 → 카테고리별 자동 답장 or 에스컬레이션.
pipeline.py reply 커맨드에서 호출.
"""
import sys
import os
import json
from datetime import datetime, timezone
from typing import Optional

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import anthropic
from naverworks_mail import send_mail, fetch_unseen
from config import PARTNERS_SUBJECT_PREFIX

HAIKU_MODEL = "claude-haiku-4-5-20251001"

REPLY_TEMPLATES = {
    "interested": {
        "subject": "Re: {original_subject}",
        "body": """{name}님 안녕하세요! 비코어랩 마케팅팀입니다 😊

관심 가져주셔서 정말 감사해요!

제안 조건 안내드릴게요:

📦 제공 내용
• iLBiA 제품 풀세트 무료 제공 (건조기 시트 + 캡슐 표백제 + 얼룩 제거제 등)
  → 소비자가 5~7만원 상당
• 쿠팡 파트너스 수수료: 기본 3% (유튜브 쇼핑 제휴 시 6.7%)
• 반응 좋으시면 정식 원고료 계약도 논의 가능해요

📮 샘플 발송을 위해 아래 정보 회신 부탁드려요:
1. 받으실 분 성함
2. 연락처 (핸드폰)
3. 배송 주소 (우편번호 포함)

편하게 답장 주세요!

비코어랩 마케팅팀""",
    },
    "ask_fee": {
        "subject": "Re: {original_subject}",
        "body": """{name}님 안녕하세요! 비코어랩 마케팅팀입니다 😊

문의 주셔서 감사해요!

현재 저희 제안 조건은:
• 제품 풀세트 무료 제공 (소비자가 5~7만원 상당)
• 쿠팡 파트너스 수수료 수익
• 월 매출 30만원 초과 시 성과 보너스 5만원

원고료는 첫 협업 후 반응을 보고 논의드리는 걸 제안드려요.
반응 좋은 채널은 30~50만원대 정식 계약으로 전환하고 있어요.

관심 있으시면 샘플 받아보실 주소 알려주세요!

비코어랩 마케팅팀""",
    },
    "send_address": {
        "subject": "Re: {original_subject}",
        "body": """{name}님 감사합니다! 😊

주소 확인했어요! 빠르게 발송 준비할게요.
발송 완료되면 송장번호 안내드릴게요.

혹시 영상 관련 궁금한 점 있으시면 편하게 물어봐주세요!

비코어랩 마케팅팀""",
    },
}

CLASSIFY_PROMPT = """당신은 비코어랩 마케팅팀의 메일 분류 AI입니다.
유튜버에게 협업 제안 메일을 보냈고, 아래는 유튜버의 답장입니다.

답장을 아래 카테고리 중 하나로 분류하세요:

- "interested": 관심 있다, 조건 알려달라, 해보고 싶다 등 긍정 반응
- "ask_fee": 원고료/비용/조건 관련 질문
- "send_address": 주소/배송 정보를 보내옴
- "decline": 거절, 관심 없다, 바쁘다 등
- "question": 분류가 애매한 질문이나 기타 내용
- "auto_reply": 자동응답/부재중 메일

JSON으로만 답하세요:
{"category": "...", "confidence": 0.0~1.0, "summary": "한줄 요약"}

유튜버 답장:
{reply_body}"""


def classify_reply(reply_body: str) -> dict:
    """Haiku로 회신 내용 분류."""
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": CLASSIFY_PROMPT.replace("{reply_body}", reply_body[:2000]),
        }],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"category": "question", "confidence": 0.0, "summary": text[:100]}


DOORI_TOKEN = "8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U"
DOORI_CHAT_ID = "8708718261"


def _notify_doori(message: str):
    """두리 봇으로 대표님께 텔레그램 알림 전송."""
    import requests
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{DOORI_TOKEN}/sendMessage",
            json={"chat_id": DOORI_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.ok
    except Exception as e:
        print(f"[WARN] 두리 텔레그램 전송 실패: {e}")
        return False


def _load_send_results() -> dict:
    """send_results.json에서 이메일 → 발송 정보 매핑."""
    path = os.path.join(_DIR, "send_results.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        results = json.load(f)
    return {r["to"]: r for r in results}


def _load_processed() -> set:
    """이미 처리한 message_id 로드."""
    path = os.path.join(_DIR, "credentials", "reply_processed.json")
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(json.load(f))


def _save_processed(processed: set):
    """처리한 message_id 저장."""
    path = os.path.join(_DIR, "credentials", "reply_processed.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(processed), f)


def process_replies() -> dict:
    """회신 체크 → 분류 → 자동 답장 or 에스컬레이션. 메인 루틴."""
    send_map = _load_send_results()
    processed = _load_processed()

    try:
        unseen = fetch_unseen(mailbox="유튜브 협찬 메일")
    except Exception:
        unseen = fetch_unseen()

    stats = {"total": 0, "notified": 0, "skipped": 0}

    for mail in unseen:
        msg_id = mail.get("message_id", "")
        if msg_id in processed:
            stats["skipped"] += 1
            continue

        stats["total"] += 1
        from_addr = mail.get("from", "")
        from_name = mail.get("from_name", "")
        subject = mail.get("subject", "")
        body = mail.get("body", "")

        sender_info = send_map.get(from_addr, {})
        youtuber_name = sender_info.get("name", from_name.split("<")[0].strip())

        print(f"\n📬 회신: {youtuber_name} ({from_addr})")
        print(f"   제목: {subject}")
        print(f"   내용: {body[:100]}...")

        result = classify_reply(body)
        category = result.get("category", "question")
        confidence = result.get("confidence", 0)
        summary = result.get("summary", "")

        print(f"   분류: {category} (확신도: {confidence})")
        print(f"   요약: {summary}")

        # 카테고리별 이모지/라벨
        labels = {
            "interested":   ("📩", "관심 있음"),
            "ask_fee":      ("💰", "원고료/조건 문의"),
            "send_address": ("📦", "주소 보내옴"),
            "decline":      ("🙅", "거절"),
            "auto_reply":   ("🤖", "자동응답"),
            "question":     ("❓", "기타 문의"),
        }
        emoji, label = labels.get(category, ("📬", category))

        # 두리를 통해 대표님께 알림 — 답장 여부는 대표님이 결정
        msg = (
            f"{emoji} <b>유튜버 회신 도착!</b>\n\n"
            f"<b>채널:</b> {youtuber_name}\n"
            f"<b>이메일:</b> {from_addr}\n"
            f"<b>분류:</b> {label} (확신도 {int(confidence*100)}%)\n"
            f"<b>요약:</b> {summary}\n\n"
            f"<b>원문:</b>\n{body[:400]}"
            + ("…" if len(body) > 400 else "")
            + f"\n\n네이버웍스에서 직접 답장해 주세요 🙏"
        )
        _notify_doori(msg)
        stats["notified"] += 1
        print(f"   ✅ 두리로 알림 전송 완료")

        processed.add(msg_id)

    _save_processed(processed)

    print(f"\n{'='*50}")
    print(f"[REPLY] 처리 완료")
    print(f"  수신: {stats['total']}건")
    print(f"  두리 알림: {stats['notified']}건")
    print(f"  이미 처리됨: {stats['skipped']}건")

    return stats


if __name__ == "__main__":
    process_replies()
