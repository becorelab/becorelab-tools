"""승인된 7명 유튜버에게 맞춤 협업 제안 메일 발송"""
import sys
import json
import time

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from naverworks_mail import send_mail

with open("approved_for_send.json", "r", encoding="utf-8") as f:
    candidates = json.load(f)

TEMPLATES = {
    "A": {
        "subject": "{name}님, 구독자분들이 댓글로 물어볼 제품이에요",
        "body": """{name}님 안녕하세요!
쿠팡 건조기 시트 리뷰 7,000개, 패밀리케어 브랜드 iLBiA(일비아)입니다.

{name}님 채널 영상 잘 봤어요.
댓글에 세탁 꿀팁 물어보시는 분들이 많으시던데,
저희가 이번에 새로 출시한 캡슐 표백제가
딱 그 주제로 영상 하나 나올 수 있는 제품이에요.

넣기만 하면 끝이라 영상으로 보여주기도 좋고,
비포/애프터가 확실해서 시청자 반응 좋을 것 같아요.

제품 보내드릴 테니 한번 써보시겠어요?
제품 제공 또는 원고료 등 조건은 편하게 맞춰드릴게요.

비코어랩 마케팅팀""",
    },
    "B": {
        "subject": "{name}님 안녕하세요, 영상 소재 하나 제안드려도 될까요?",
        "body": """{name}님 안녕하세요!
쿠팡 건조기 시트 리뷰 7,000개, 패밀리케어 브랜드 iLBiA입니다.

{name}님 영상 보면서 "이 분한테 저희 신제품 보내드리면
진짜 리얼한 후기가 나오겠다" 싶었어요.

아이 있는 집은 세탁이 전쟁이잖아요.
이번에 새로 나온 캡슐 표백제가 넣기만 하면 되는 거라
비포/애프터 찍으시면 조회수 터질 소재예요.

보내드릴 테니 한번 써보시겠어요?
마음에 안 드시면 영상 안 만드셔도 되고요.
제품 제공 또는 원고료 등 조건은 편하게 맞춰드릴게요.

비코어랩 마케팅팀""",
    },
    "C": {
        "subject": "{name}님, 신제품 캡슐 표백제 첫 리뷰어 되실래요?",
        "body": """{name}님 안녕하세요!
쿠팡 건조기 시트 리뷰 7,000개, 패밀리케어 브랜드 iLBiA입니다.

{name}님이 추천하시는 것들 보면 진짜 써보고 고르신 게 느껴져서
저희 신제품 첫 리뷰를 {name}님한테 맡기고 싶었어요.

이번에 새로 출시한 캡슐 표백제인데,
아직 리뷰 영상이 거의 없어서 선점 효과도 있을 거예요.

제품 보내드리고, 제품 제공 또는 원고료 등 조건은 따로 상의해요.

비코어랩 마케팅팀""",
    },
}

CATEGORY_MAP = {
    "살림템 추천": "A",
    "빨래 꿀팁": "A",
    "살림 꿀템 쿠팡": "A",
    "주방용품 추천": "C",
    "아기 세탁 세제": "B",
}

results = []
for c in candidates:
    ttype = CATEGORY_MAP.get(c["category"], "A")
    tpl = TEMPLATES[ttype]
    name = c["name"]
    subject = tpl["subject"].format(name=name)
    body = tpl["body"].format(name=name)

    print(f"\n📧 발송 중: {name} ({c['email']}) — Type {ttype}")
    try:
        result = send_mail(to=c["email"], subject=subject, body_ko=body)
        result["type"] = ttype
        result["name"] = name
        results.append(result)
        print(f"   ✅ 성공! Message-ID: {result['message_id'][:40]}...")
        time.sleep(2)
    except Exception as e:
        print(f"   ❌ 실패: {e}")
        results.append({"name": name, "email": c["email"], "error": str(e)})

print(f"\n{'='*50}")
print(f"발송 완료: {sum(1 for r in results if 'message_id' in r)}/{len(candidates)}")

with open("send_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("결과 저장: send_results.json")
