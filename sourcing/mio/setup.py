"""
미오 에이전트 1회 생성 스크립트
실행하면 Agent + Environment를 만들고 mio.env에 저장합니다.

사용법:
    python setup.py
"""
import os
import sys
import anthropic
from dotenv import load_dotenv

_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_dir, '..', 'analyzer', '.env'))

MIO_ENV_PATH = os.path.join(_dir, 'mio.env')


def main():
    if os.path.exists(MIO_ENV_PATH):
        print("⚠️  mio.env 이미 존재합니다.")
        print("   기존 에이전트를 그대로 쓰려면 run.py를 실행하세요.")
        print("   새로 만들려면 mio.env를 삭제 후 다시 실행하세요.")
        sys.exit(0)

    client = anthropic.Anthropic()

    print("🚀 미오 에이전트 설정 시작...\n")

    # ── 1. 환경 생성 ───────────────────────────────────────
    print("1️⃣  환경 생성 중...")
    env = client.beta.environments.create(
        name="mio-alibaba-env",
        config={
            "type": "cloud",
            "networking": {"type": "unrestricted"},   # 알리바바 접속 필요
        },
    )
    print(f"   ✅ {env.id}\n")

    # ── 2. 에이전트 생성 ────────────────────────────────────
    print("2️⃣  미오 에이전트 생성 중...")
    agent = client.beta.agents.create(
        name="미오 소싱 에이전트",
        model="claude-opus-4-6",
        system="""You are 미오(Mio), a professional Alibaba sourcing specialist for Becorelab (비코어랩), a Korean e-commerce brand.

## Your mission
Find the best-fit suppliers and products on Alibaba for the given sourcing request.

## How you work
1. **Search broadly** — start with English keywords, try Chinese/Korean variants if results are poor
2. **Never stop at page 1** — paginate until strong candidates found or market fit confirmed poor
3. **Always check detail pages** — use alibaba_get_detail on every promising listing before evaluating
4. **Filter strictly** — skip wrong specs, excessive MOQ, or no Gold Supplier / Trade Assurance
5. **Compare and rank** — present top 3-5 candidates in a markdown comparison table

## Evaluation criteria
- MOQ: ≤500 units preferred (unless 대표님 specifies otherwise)
- Price: Verify against the target FOB price given by 대표님
- Quality signals: Gold Supplier, Trade Assurance, 3+ years operation, 4+ star rating
- Certifications: CE, FDA, REACH, KC — note which are present
- Specs: Read and interpret Chinese text in product detail pages when present

## Progress narration (in Korean)
- "1페이지 검색 중..."
- "상세 확인 중: [제품명]..."
- "가격/MOQ 조건 미충족, 스킵"

## Output
- Respond in Korean to 대표님
- Final results as a markdown table: 제품명 | 가격 | MOQ | 인증 | Gold? | URL
- Write inquiry messages in English when using alibaba_send_inquiry""",
        tools=[
            {
                "type": "custom",
                "name": "alibaba_search",
                "description": (
                    "알리바바 키워드 검색. 상품 목록(제목/URL/가격/MOQ/Gold Supplier 여부)을 반환. "
                    "여러 페이지 검색 가능 (page 파라미터 사용)."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "검색 키워드 (영문 권장, 예: 'drain trap kitchen sink stainless')",
                        },
                        "page": {
                            "type": "integer",
                            "description": "페이지 번호 (기본값 1)",
                            "default": 1,
                        },
                        "max_moq": {
                            "type": "integer",
                            "description": "최대 MOQ 필터 (선택, 예: 500)",
                        },
                        "min_price": {
                            "type": "number",
                            "description": "최소 가격 USD (선택)",
                        },
                        "max_price": {
                            "type": "number",
                            "description": "최대 가격 USD (선택)",
                        },
                    },
                    "required": ["keyword"],
                },
            },
            {
                "type": "custom",
                "name": "alibaba_get_detail",
                "description": (
                    "알리바바 상품 상세페이지 전체 내용 추출. "
                    "소재/MOQ/인증/스펙/공급업체 정보 포함. 중국어 스펙 텍스트도 처리."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "product_url": {
                            "type": "string",
                            "description": "알리바바 상품 URL",
                        },
                    },
                    "required": ["product_url"],
                },
            },
            {
                "type": "custom",
                "name": "alibaba_send_inquiry",
                "description": (
                    "공급업체에 영문 문의 메시지 발송. "
                    "Contact Supplier 폼을 통해 전송. 회사명과 전문적인 영문 메시지 필요."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "product_url": {
                            "type": "string",
                            "description": "문의할 상품 URL",
                        },
                        "company": {
                            "type": "string",
                            "description": "공급업체 회사명",
                        },
                        "message": {
                            "type": "string",
                            "description": "영문 문의 메시지 (전문적이고 구체적으로: 수량/사양/인증 요구사항 포함)",
                        },
                    },
                    "required": ["product_url", "company", "message"],
                },
            },
        ],
    )
    print(f"   ✅ {agent.id}")
    print(f"   버전: {agent.version}\n")

    # ── 3. mio.env에 저장 ──────────────────────────────────
    with open(MIO_ENV_PATH, 'w', encoding='utf-8') as f:
        f.write(f"MIO_AGENT_ID={agent.id}\n")
        f.write(f"MIO_AGENT_VERSION={agent.version}\n")
        f.write(f"MIO_ENVIRONMENT_ID={env.id}\n")

    print("3️⃣  mio.env 저장 완료\n")
    print("=" * 52)
    print("🎉 미오 세팅 완료!")
    print(f"   Agent ID    : {agent.id}")
    print(f"   Environment : {env.id}")
    print("=" * 52)
    print("\n실행 방법:")
    print("  python run.py '배수구 트랩 소싱해줘'")
    print("  python run.py '스테인리스 식기 건조대, MOQ 200개 이하'")


if __name__ == "__main__":
    main()
