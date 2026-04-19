"""미오 툴 파이프라인 테스트 — 배수구 트랩 상위 판매자 분석"""
import json
import sys
sys.path.insert(0, '.')
from tools import coupang_search_top, coupang_get_detail, search_1688, find_1688_detail

KEYWORD = "배수구트랩"

# 1) 쿠팡 상위 상품 검색
print(f"=== 1단계: 쿠팡 '{KEYWORD}' 상위 상품 검색 ===\n")
search_result = coupang_search_top(KEYWORD, max_products=10)
if search_result.get('error'):
    print(f"Error: {search_result['error']}")
    sys.exit(1)

urls = search_result.get('product_urls', [])
print(f"상위 상품 {len(urls)}개 발견")
print(f"Raw text (500자):\n{search_result.get('raw_text', '')[:500]}\n")

# 2) 상위 3개 상세페이지 읽기
print(f"=== 2단계: 상위 3개 상세페이지 분석 ===\n")
details = []
for i, url in enumerate(urls[:3], 1):
    print(f"  [{i}] {url[:80]}")
    detail = coupang_get_detail(url)
    if detail.get('success'):
        text = detail.get('raw_text', '')[:1500]
        details.append({'url': url, 'text': text})
        print(f"      -> {len(text)}자 수집")
    else:
        print(f"      -> Error: {detail.get('error')}")

# 3) 1688 검색
print(f"\n=== 3단계: 1688에서 동일 제품 검색 ===\n")
result_1688 = search_1688("地漏防臭器 防虫 多口径", page=1, size=5)
if result_1688.get('success'):
    items = result_1688.get('items', [])
    print(f"1688 검색 결과: {len(items)}개")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item['titleEn'][:60]} | Y{item['price']} | sales:{item.get('sales_volume','')}")
else:
    print(f"1688 검색 실패: {result_1688.get('error')}")

# 4) 상위 1개 상세 조회
if result_1688.get('success') and result_1688.get('items'):
    pid = result_1688['items'][0]['id']
    print(f"\n=== 4단계: 1688 상세 조회 (ID: {pid}) ===\n")
    detail_1688 = find_1688_detail(pid)
    if detail_1688.get('success'):
        print(f"제품: {detail_1688['titleEn'][:80]}")
        print(f"MOQ: {detail_1688['moq']} | 판매량: {detail_1688['sold']} | 재고: {detail_1688['quantity']}")
        print(f"SKU {detail_1688['sku_count']}개:")
        for s in detail_1688.get('skus', [])[:5]:
            print(f"  Y{s['price']}: {s['option'][:60]}")
    else:
        print(f"상세 조회 실패: {detail_1688}")

print("\n=== 테스트 완료 ===")
