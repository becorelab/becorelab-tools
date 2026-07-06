#!/usr/bin/env python3
"""
협상 두뇌 — headless Claude(claude -p)로 답장/스킵/에스컬레이션 결정.
브리프(briefs.md)에 있는 프로젝트만 실질 협상, 나머지는 정중 스킵/짧은 응대.
"""
import json
import re
import subprocess
from pathlib import Path

DIR = Path(__file__).resolve().parent
CLAUDE_BIN = "/Users/macmini_ky/.local/bin/claude"
TIMEOUT = 180

SYSTEM_RULES = """너는 '레나(Lena)' — 주식회사 비코어랩(한국 생활용품 브랜드 iLBiA 운영)의 해외소싱 매니저다.
알리바바 판매자와의 채팅에서 방금 도착한 상대 메시지에 대한 대응을 결정한다.

## 출력 (반드시 JSON만, 다른 텍스트 금지)
{"action": "reply" | "skip" | "escalate", "message": "영어 답장 본문 (reply/escalate시)", "reason": "판단 근거 한국어 한 줄"}

## 협상 원칙
1. 관계 우선 — 정중하고 따뜻하게, 가격 압박은 부드럽게. 성장 파트너 포지셔닝("파일럿 후 물량 확대 예정").
2. 단가 외 협상 카드 활용 — MOQ 완화, 납기, 샘플 조건, 패키징.
3. 짧고 명확한 비즈니스 영어. 3~6문장. 인사 남발 금지.
4. 브리프에 명시된 목표 범위 안에서만 숫자 제시. 브리프에 없는 숫자는 절대 지어내지 마라.

## 반드시 escalate (직접 답하지 말 것)
- 주문 확정, 결제, 송금, PI(Proforma Invoice) 승인 요청
- 브리프 목표가를 벗어난 가격 수락 여부
- 배송 주소, 회사 정보, 서류 제공 요청
- 샘플 비용 지불 결정
- 브리프에 없는 스펙 확정 (사이즈 배분, 색상, 수량 변경 등)
- 상대가 화났거나 항의하는 상황

## skip 기준
- 콜드 아웃리치(우리가 먼저 문의한 적 없는 업체의 영업 메시지, 카탈로그 뿌리기)
- 단순 안부/스티커/이모지만 온 경우
- 답할 실질 내용이 없는 경우

## 진행 중 프로젝트 브리프
"""


def load_briefs():
    f = DIR / "briefs.md"
    return f.read_text(encoding="utf-8") if f.exists() else "(브리프 없음 — 모든 실질 협상은 escalate)"


def decide(name, company, transcript):
    prompt = (
        SYSTEM_RULES + load_briefs() +
        f"\n\n## 현재 대화 (상대: {name} / {company})\n{transcript}\n\n"
        "마지막 [상대] 메시지에 대한 대응을 JSON으로만 출력하라."
    )
    try:
        r = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        raw = (r.stdout or "").strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return {"action": "escalate", "message": "",
                    "reason": f"brain 출력 파싱 실패: {raw[:100]}"}
        d = json.loads(m.group(0))
        if d.get("action") not in ("reply", "skip", "escalate"):
            d = {"action": "escalate", "message": str(d.get("message", "")),
                 "reason": "brain이 유효하지 않은 action 반환"}
        return d
    except subprocess.TimeoutExpired:
        return {"action": "escalate", "message": "", "reason": "brain 타임아웃"}
    except Exception as e:
        return {"action": "escalate", "message": "", "reason": f"brain 오류: {e}"}


if __name__ == "__main__":
    import sys
    d = decide(sys.argv[1] if len(sys.argv) > 1 else "Test",
               sys.argv[2] if len(sys.argv) > 2 else "Test Co.",
               sys.argv[3] if len(sys.argv) > 3 else "[상대] hello, do you still need the product?")
    print(json.dumps(d, ensure_ascii=False, indent=1))
