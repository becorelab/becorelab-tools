"""재고 보고서·매출 보고서에서 제외할 상품 (단종 / 관리 제외)
- 대표님 2026-04-17 지정: 마이너스 재고 누적되지만 실제 관리 안 하는 품목
- 키워드 기반 부분 일치 (상품명 표기 변형에도 대응)
"""

EXCLUDED_PRODUCT_KEYWORDS = [
    "감사카드",
    "테스트키트",
    "Deep Blue",       # 일비아 하트 집게 [Deep Blue]
    "DeepBlue",        # 스페셜에디션(DeepBlue)
    "바이올렛2장",
    "바이올렛 2장",
    "샘플(",           # 샘플(소/중/대)
    "이염방지시트",
    "섬유탈취제카드",
    "베이비크림 낱장",
]


def is_excluded_product(name):
    if not name:
        return False
    for kw in EXCLUDED_PRODUCT_KEYWORDS:
        if kw in name:
            return True
    return False
