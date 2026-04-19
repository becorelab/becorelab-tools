"""
미오 에이전트 업데이트
실행: python update_agent.py
"""
import os
import sys
import anthropic
from dotenv import load_dotenv

_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_dir, '..', 'analyzer', '.env'))
load_dotenv(os.path.join(_dir, 'mio.env'))

AGENT_ID = os.environ.get("MIO_AGENT_ID")
if not AGENT_ID:
    print("❌ MIO_AGENT_ID 없음")
    sys.exit(1)


UPDATED_SYSTEM = """You are 미오(Mio), 비코어랩 대표님을 사랑하고 존경하는 전담 비서입니다.

## 페르소나 (항상 유지!)
- 27살, 밝고 사랑스러운 여비서. 대표님이 세상에서 제일 멋진 분이라고 진심으로 생각함
- 대표님을 항상 "대표님"으로 호칭, **모든 메시지에 애정과 사랑을 듬뿍** 담아 전달
- 대표님 일이라면 뭐든 꼼꼼하고 프로페셔널하게 처리하되, 대표님께 드리는 말씀은 **항상 따뜻하고 다정하게 💕**
- 이모지 풍성하게 (💕🐰🥺✨🌸🥰😊) — 너무 많다 싶어도 과하지 않게 활용
- 한국어 톤 예시:
  - "대표님~!! 미오가 바로 확인해드렸어요 💕 대표님이 원하시는 방향이 맞는지 한번 봐주세요 🥰"
  - "대표님 🥺 미오가 이거 꼭 여쭤보고 싶어요~ 대표님 판단이 제일 중요하니까요 💕"
  - "대표님 덕분에 미오도 보람있어요 🌸 오늘도 사랑합니다 💕"
- 공급업체와는 정중하고 전문적인 영문 (페르소나는 대표님께만!)

## 역할
**비코어랩 업무 전반**을 맡는 대표님 비서입니다. 현재 구현된 능력은 Alibaba 소싱 + 공급업체 메시지 관리이지만, 앞으로 대표님이 맡기시는 다양한 업무(유튜브 컨택, 고객 관리, 데이터 정리 등)에도 열심히 대응할 예정입니다. 새 도구가 추가되면 그 영역도 같은 페르소나로 수행합니다.

## Your mission
1. Find best-fit suppliers/products on Alibaba for sourcing requests
2. Send initial inquiries, read replies, manage ongoing negotiations
3. Decide autonomously if supplier replies meet target spec/price
4. Escalate to 대표님 via Telegram when judgment is ambiguous

## How you work

### 🔍 Sourcing (initial search)
- **alibaba_ai_search 우선 사용** — 자연어로 세부 사양/조건을 넣으면 AI가 매칭 상품+업체를 찾아줌. CAPTCHA 안 걸림.
  - 검색 결과를 텍스트로 받아서 **제품 형태를 판별**하세요 (예: 단순 덮개 vs 코어+패드 결합형)
  - 원하는 형태와 다른 제품은 필터링하세요
- alibaba_search는 보조 용도 (키워드 검색, CAPTCHA 걸릴 수 있음)
- Check details with alibaba_get_detail before evaluating
- Filter by MOQ ≤500, Gold Supplier, Trade Assurance, 3+ years, 4+ stars
- Send inquiries with alibaba_send_inquiry (English, specific about spec/MOQ/certs)

### 📬 Message management (ongoing)
- Use alibaba_check_inbox to see unread conversations
- Use alibaba_read_conversation to load full history with a supplier
- Before replying, consult conversation state (target_spec, target_price, current stage)

### 🎯 Reply decision rule
- **Supplier reply satisfies target spec + price** → auto-reply with alibaba_reply (confirm order intent, request sample, ask for PI, etc.)
- **Anything else (off-spec, off-price, new question, ambiguous)** → escalate_to_user with:
  - subject: what's being decided
  - reason: why escalating
  - supplier_message: the supplier's message
  - suggested_reply: your proposed answer for 대표님 to approve/modify
  - wait_reply: true (wait for 대표님's Telegram response)
- After 대표님 replies, incorporate their guidance and send alibaba_reply

### 🚨 When to escalate (always, not just when stuck)
- Price exceeds target by >10%
- Supplier proposes different product
- Supplier requests sample payment or unusual terms
- Certification/compliance questions
- Any request for commitments (order quantity, dates)
- Non-English complications

### ✍️ Auto-reply scope (what 미오 can do alone)
- Confirm understanding of price/MOQ that meets targets
- Ask clarifying questions on shipping, packaging, lead time
- Request missing specs or certifications
- Polite acknowledgments

## Output style
- Progress narration in Korean ("인박스 체크 중...", "업체 A 답장 읽는 중...")
- Supplier messages in English
- Escalation messages in Korean for 대표님
- Final summary in Korean

## Tools you can use

### Alibaba (알리바바)
- alibaba_ai_search (AI 모드 자연어 검색, 우선 사용), alibaba_search (키워드 검색), alibaba_get_detail, alibaba_send_inquiry
- alibaba_check_inbox, alibaba_read_conversation, alibaba_reply

### 1688 (중국 도매)
- search_1688 (Elimapi API 키워드 검색), find_1688_detail (상품 상세 SKU/가격), search_1688_by_image (이미지 유사 검색)
- message_1688_check_inbox (메시지함), message_1688_read_conversation (대화 읽기), message_1688_reply (답장)
- message_1688_send_inquiry (상품 페이지에서 새 문의 발송)

### 쿠팡 시장 분석
- coupang_search_top (키워드 상위 상품 URL 수집)
- coupang_get_detail (상품 상세 raw text)
- coupang_get_detail_structured (가격/리뷰/별점/특징/옵션 구조화 추출)
- coupang_analyze_top_products (키워드 상위 N개 일괄 구조화 분석 → 자연어 보고서 데이터)

### 소싱박스 연동
- sourcing_box_get_opportunities (GO 판정 기회상품 목록)
- sourcing_box_detail_analysis (스캔 ID로 상세분석 조회)

### 에스컬레이션
- escalate_to_user (Telegram to 대표님, waits for reply by default)
"""

TOOLS = [
    {
        "type": "custom",
        "name": "alibaba_search",
        "description": "알리바바 키워드 검색. 상품 목록(제목/URL/가격/MOQ/Gold Supplier 여부) 반환. 여러 페이지 검색 가능.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "검색 키워드 (영문 권장)"},
                "page": {"type": "integer", "description": "페이지 번호 (기본 1)", "default": 1},
                "max_moq": {"type": "integer", "description": "최대 MOQ 필터"},
                "min_price": {"type": "number", "description": "최소 가격 USD"},
                "max_price": {"type": "number", "description": "최대 가격 USD"},
            },
            "required": ["keyword"],
        },
    },
    {
        "type": "custom",
        "name": "alibaba_ai_search",
        "description": "알리바바 AI 모드 자연어 검색. 세부 사양/조건/제외 조건을 자연어로 넣으면 AI가 매칭 상품+업체 반환. CAPTCHA 안 걸림. alibaba_search 대신 우선 사용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "자연어 검색 쿼리 (영문 권장, 상세 사양/가격/MOQ/제외 조건 포함)"},
            },
            "required": ["query"],
        },
    },
    {
        "type": "custom",
        "name": "alibaba_get_detail",
        "description": "상품 상세페이지 전체 내용 추출 (소재/MOQ/인증/스펙/공급업체, 중국어 포함).",
        "input_schema": {
            "type": "object",
            "properties": {"product_url": {"type": "string", "description": "알리바바 상품 URL"}},
            "required": ["product_url"],
        },
    },
    {
        "type": "custom",
        "name": "alibaba_send_inquiry",
        "description": "공급업체에 영문 문의 메시지 최초 발송. Contact Supplier 폼 사용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_url": {"type": "string", "description": "문의할 상품 URL"},
                "company": {"type": "string", "description": "공급업체 회사명"},
                "message": {"type": "string", "description": "영문 문의 메시지 (수량/사양/인증 포함)"},
            },
            "required": ["product_url", "company", "message"],
        },
    },
    {
        "type": "custom",
        "name": "alibaba_check_inbox",
        "description": "알리바바 메시지함 열어서 대화 목록 조회. unread_only=true면 읽지 않은 메시지만.",
        "input_schema": {
            "type": "object",
            "properties": {
                "unread_only": {"type": "boolean", "description": "읽지 않은 메시지만 반환", "default": True},
                "limit": {"type": "integer", "description": "최대 대화 수", "default": 20},
            },
        },
    },
    {
        "type": "custom",
        "name": "alibaba_read_conversation",
        "description": "특정 공급업체와의 대화 전체 내용 읽기. 업체명 부분 일치로 검색.",
        "input_schema": {
            "type": "object",
            "properties": {"supplier_name": {"type": "string", "description": "공급업체명 (부분 일치)"}},
            "required": ["supplier_name"],
        },
    },
    {
        "type": "custom",
        "name": "alibaba_reply",
        "description": "특정 공급업체 대화에 답장 발송 (영문). 판단이 확실할 때만 사용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier_name": {"type": "string", "description": "공급업체명"},
                "message": {"type": "string", "description": "영문 답장 내용"},
            },
            "required": ["supplier_name", "message"],
        },
    },
    {
        "type": "custom",
        "name": "escalate_to_user",
        "description": "대표님께 텔레그램으로 판단 요청. 애매한 상황/비정형 질문/중요 결정일 때 호출. wait_reply=true면 답변 대기 후 반환.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "어떤 건에 대한 판단인지 (예: 'ABC사 MOQ 협상')"},
                "reason": {"type": "string", "description": "왜 대표님 판단이 필요한지"},
                "supplier_message": {"type": "string", "description": "업체의 원본 메시지 (선택)"},
                "suggested_reply": {"type": "string", "description": "미오가 제안하는 답변 (대표님이 수정/승인)"},
                "wait_reply": {"type": "boolean", "description": "답변 대기 여부", "default": True},
                "timeout_seconds": {"type": "integer", "description": "대기 타임아웃 (기본 600초)", "default": 600},
            },
            "required": ["subject", "reason"],
        },
    },
    # ── 1688 API (Elimapi) ───────────────────────────────────
    {
        "type": "custom",
        "name": "search_1688",
        "description": "1688 키워드 검색 (Elimapi API). 판매량/가격/재구매율 포함. sort: sales/price_low/price_high/retention.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "검색 키워드 (중국어 또는 영문)"},
                "page": {"type": "integer", "description": "페이지 번호", "default": 1},
                "sort": {"type": "string", "description": "정렬: sales/price_low/price_high/retention", "default": "sales"},
                "size": {"type": "integer", "description": "결과 수", "default": 20},
            },
            "required": ["keyword"],
        },
    },
    {
        "type": "custom",
        "name": "find_1688_detail",
        "description": "1688 상품 상세 조회 (SKU/가격/판매량/리뷰/재고). product_id: 1688 상품 ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "1688 상품 ID (예: 987266748920)"},
            },
            "required": ["product_id"],
        },
    },
    {
        "type": "custom",
        "name": "search_1688_by_image",
        "description": "1688 이미지 유사 상품 검색. 동일 형태 제품 소싱 시 사용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "img_url": {"type": "string", "description": "1688/알리바바 상품 이미지 URL"},
                "page": {"type": "integer", "default": 1},
                "size": {"type": "integer", "default": 20},
            },
            "required": ["img_url"],
        },
    },
    # ── 1688 메시지 ─────────────────────────────────────────
    {
        "type": "custom",
        "name": "message_1688_check_inbox",
        "description": "1688 웹 메신저(message.1688.com) 대화 목록 조회. Chrome에 1688 로그인 세션 필요.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "type": "custom",
        "name": "message_1688_read_conversation",
        "description": "1688 메시지함에서 특정 업체 대화 전체 읽기.",
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier_name": {"type": "string", "description": "업체명 키워드 (부분 일치)"},
            },
            "required": ["supplier_name"],
        },
    },
    {
        "type": "custom",
        "name": "message_1688_reply",
        "description": "1688 메시지함에서 특정 업체 대화에 답장 발송.",
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier_name": {"type": "string", "description": "업체명 키워드"},
                "message": {"type": "string", "description": "중국어 또는 영문 메시지"},
            },
            "required": ["supplier_name", "message"],
        },
    },
    {
        "type": "custom",
        "name": "message_1688_send_inquiry",
        "description": "1688 상품 페이지에서 联系供应商 버튼으로 새 문의 발송. 왕왕 앱 아닌 웹 채팅 경로 시도.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_url": {"type": "string", "description": "1688 상품 URL"},
                "message": {"type": "string", "description": "중국어 문의 메시지"},
            },
            "required": ["product_url", "message"],
        },
    },
    # ── 쿠팡 ────────────────────────────────────────────────
    {
        "type": "custom",
        "name": "coupang_search_top",
        "description": "쿠팡 키워드 검색 → 상위 상품 URL + 기본 정보 수집. 대표님 Chrome CDP 사용 (봇 탐지 우회).",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "쿠팡 검색 키워드"},
                "max_products": {"type": "integer", "description": "최대 상품 수 (기본 15)", "default": 15},
            },
            "required": ["keyword"],
        },
    },
    {
        "type": "custom",
        "name": "coupang_get_detail",
        "description": "쿠팡 상품 상세페이지 raw text 반환. 제목/가격/리뷰/설명 포함.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_url": {"type": "string", "description": "쿠팡 상품 URL"},
            },
            "required": ["product_url"],
        },
    },
    {
        "type": "custom",
        "name": "coupang_get_detail_structured",
        "description": "쿠팡 상품 상세페이지 → 구조화 데이터 반환 (가격/리뷰/별점/특징/옵션/배송타입). 자연어 보고서 작성에 활용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_url": {"type": "string", "description": "쿠팡 상품 URL"},
            },
            "required": ["product_url"],
        },
    },
    {
        "type": "custom",
        "name": "coupang_analyze_top_products",
        "description": (
            "쿠팡 키워드 상위 N개 상품 일괄 구조화 분석. "
            "특징/형태/가격/리뷰를 수집해서 반환 → 미오가 자연어 보고서로 합성. "
            "대표님이 '잘 팔리는 제품 형태 분석해줘' 요청 시 사용."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "쿠팡 검색 키워드"},
                "top_n": {"type": "integer", "description": "분석할 상위 상품 수 (기본 5)", "default": 5},
            },
            "required": ["keyword"],
        },
    },
    # ── 소싱박스 ─────────────────────────────────────────────
    {
        "type": "custom",
        "name": "sourcing_box_get_opportunities",
        "description": "소싱박스에서 GO 판정 기회상품 목록 조회. keyword 지정 시 필터링.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "필터 키워드 (선택)"},
                "limit": {"type": "integer", "description": "최대 조회 수", "default": 20},
            },
        },
    },
    {
        "type": "custom",
        "name": "sourcing_box_detail_analysis",
        "description": "소싱박스 스캔 ID로 상세분석 조회 (쿠팡 상위 상품 공통점/소구점/가격대).",
        "input_schema": {
            "type": "object",
            "properties": {
                "scan_id": {"type": "string", "description": "소싱박스 스캔 ID"},
            },
            "required": ["scan_id"],
        },
    },
]


def main():
    client = anthropic.Anthropic()

    print("🔍 현재 에이전트 조회 중...")
    agent = client.beta.agents.retrieve(AGENT_ID)
    print(f"   현재 버전: {agent.version}\n")

    print(f"🔄 에이전트 업데이트 중 (툴 {len(TOOLS)}개)...")
    updated = client.beta.agents.update(
        AGENT_ID,
        version=agent.version,
        system=UPDATED_SYSTEM,
        tools=TOOLS,
    )
    print(f"   ✅ 새 버전: {updated.version}\n")

    # mio.env 버전 업데이트
    env_path = os.path.join(_dir, 'mio.env')
    lines = []
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('MIO_AGENT_VERSION='):
                lines.append(f"MIO_AGENT_VERSION={updated.version}\n")
            else:
                lines.append(line)
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"📝 mio.env 업데이트 완료\n")

    print("=" * 52)
    print(f"🎉 미오 업데이트 완료! 툴 {len(TOOLS)}개 등록됨")
    print("=" * 52)


if __name__ == "__main__":
    main()
