"""
골드박스 → 키워드 추출 파이프라인
반복 등장 상품에서 비코어랩 소싱 가능 상품만 필터 + 검색 키워드 2~3개 추출
"""

import json
import re
import os
import sys
import requests
from collections import defaultdict

# 같은 디렉토리의 모듈 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import firestore_db as fdb

# Anthropic API 키 로드
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            if _line.startswith('ANTHROPIC_API_KEY=') and not ANTHROPIC_API_KEY:
                ANTHROPIC_API_KEY = _line.split('=', 1)[1].strip()


def _call_claude(prompt: str, max_tokens: int = 4000) -> str:
    """Claude Haiku API 호출"""
    res = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json={
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': max_tokens,
            'messages': [{'role': 'user', 'content': prompt}],
        },
        timeout=60,
    )
    if res.ok:
        data = res.json()
        content = data.get('content', [])
        if content:
            return content[0].get('text', '')
    print(f'Claude API 에러: {res.status_code} {res.text[:200]}')
    return ''


def load_goldbox_all(days: int = 30) -> list:
    """전체 골드박스 데이터 로드"""
    fdb.init_firestore()
    dates = fdb.get_goldbox_dates(limit=days)
    all_products = []
    for d in dates:
        dt = d['crawled_date'] if isinstance(d, dict) else d
        products = fdb.get_goldbox_by_date(dt)
        all_products.extend(products)
    return all_products


def extract_product_id(url: str) -> str:
    if not url:
        return None
    parts = url.split('/vp/products/')
    if len(parts) > 1:
        return parts[1].split('?')[0]
    return None


def analyze_repeats(all_products: list, min_days: int = 3) -> list:
    """반복 등장 분석 → min_days 이상 반복 상품 리스트"""
    appearances = defaultdict(lambda: {
        'dates': set(), 'names': set(), 'prices': [], 'urls': set()
    })

    for p in all_products:
        pid = extract_product_id(p.get('product_url', ''))
        if not pid:
            continue
        name = p.get('product_name', '').split('\n')[0].strip()
        appearances[pid]['dates'].add(p.get('crawled_date', ''))
        appearances[pid]['names'].add(name)
        appearances[pid]['prices'].append(p.get('price', 0))
        appearances[pid]['urls'].add(p.get('product_url', ''))

    repeated = []
    for pid, info in appearances.items():
        if len(info['dates']) < min_days:
            continue
        name = list(info['names'])[0]
        if '한정수량 마감' in name:
            continue
        avg_price = sum(info['prices']) / len(info['prices']) if info['prices'] else 0
        repeated.append({
            'product_id': pid,
            'name': name,
            'repeat_days': len(info['dates']),
            'avg_price': round(avg_price),
        })

    repeated.sort(key=lambda x: x['repeat_days'], reverse=True)
    return repeated


def extract_keywords_batch(products: list, batch_size: int = 40) -> list:
    """Gemini로 카테고리 필터 + 키워드 추출 (배치 처리)"""
    all_results = []

    for start in range(0, len(products), batch_size):
        batch = products[start:start + batch_size]
        print(f'[배치 {start // batch_size + 1}] {len(batch)}개 상품 처리 중...')

        numbered = '\n'.join(
            f'{i+1}. [{p["repeat_days"]}일 반복] {p["name"]} (₩{p["avg_price"]:,})'
            for i, p in enumerate(batch)
        )

        prompt = f"""쿠팡 골드박스 반복 등장 상품을 분석하세요.

## 판단 기준
비코어랩은 생활용품/소비재를 소싱하는 소규모 브랜드입니다.
- **소싱 가능**: 세제, 욕실용품, 주방소모품, 청소용품, 생활잡화, 뷰티소모품, 수납/정리, 반려동물소모품, 문구류, 디퓨저/방향제, 위생용품
- **소싱 불가**: 대기업 식품/음료(삼다수,동원 등), 신선식품, 가전제품, 브랜드 의류/화장품, 의약품, 전자기기, 가구

## 키워드 추출 규칙
- 브랜드명/용량/수량/모델번호 제거
- 소비자가 쿠팡에서 검색할 때 쓰는 일반명사 2~3단어
- **반드시 후보 2~3개** (띄어쓰기 차이, 동의어 포함)
- 예: "코멧 디퓨저 200ml" → ["디퓨저", "룸디퓨저", "방향제"]

## 응답 형식 (JSON 배열만, 설명 없이)
[
  {{"idx": 1, "sourceable": true, "reason": "생활소모품", "keywords": ["키워드1", "키워드2"]}},
  {{"idx": 2, "sourceable": false, "reason": "대기업 식품"}}
]

## 상품 목록
{numbered}"""

        result = _call_claude(prompt, max_tokens=4000)
        if not result:
            print(f'  ❌ Gemini 응답 없음, 스킵')
            continue

        result = re.sub(r'```json\s*', '', result)
        result = re.sub(r'```\s*', '', result)
        json_match = re.search(r'\[[\s\S]*\]', result)
        if not json_match:
            print(f'  ❌ JSON 파싱 실패')
            continue

        try:
            items = json.loads(json_match.group())
        except json.JSONDecodeError:
            print(f'  ❌ JSON 디코딩 실패')
            continue

        for item in items:
            idx = item.get('idx', 0) - 1
            if 0 <= idx < len(batch):
                batch[idx]['sourceable'] = item.get('sourceable', False)
                batch[idx]['filter_reason'] = item.get('reason', '')
                batch[idx]['keywords'] = item.get('keywords', [])

        all_results.extend(batch)
        sourceable_count = sum(1 for b in batch if b.get('sourceable'))
        print(f'  ✅ 소싱 가능: {sourceable_count}/{len(batch)}')

    return all_results


def filter_existing_scans(results: list) -> tuple:
    """이미 스캔한 키워드 스킵"""
    existing_scans = fdb.list_scans(limit=500)
    existing_kws = set(s.get('keyword', '').strip().lower() for s in existing_scans)

    new_keywords = []
    skipped_keywords = []

    for r in results:
        if not r.get('sourceable'):
            continue
        for kw in r.get('keywords', []):
            kw_lower = kw.strip().lower()
            if kw_lower in existing_kws:
                skipped_keywords.append(kw)
            else:
                new_keywords.append({
                    'keyword': kw,
                    'source_product': r['name'],
                    'repeat_days': r['repeat_days'],
                    'avg_price': r['avg_price'],
                })
                existing_kws.add(kw_lower)

    return new_keywords, skipped_keywords


def run_pipeline(min_days: int = 3, days: int = 30):
    """파이프라인 실행"""
    print('=' * 60)
    print('🔍 골드박스 키워드 추출 파이프라인')
    print('=' * 60)

    # 1. 데이터 로드
    print('\n[1/4] 골드박스 데이터 로드...')
    all_products = load_goldbox_all(days)
    print(f'  총 {len(all_products)}개 상품 (중복 포함)')

    # 2. 반복 등장 분석
    print(f'\n[2/4] 반복 등장 분석 (최소 {min_days}일)...')
    repeated = analyze_repeats(all_products, min_days)
    print(f'  {min_days}일+ 반복 상품: {len(repeated)}개')

    # 3. 카테고리 필터 + 키워드 추출
    print(f'\n[3/4] Gemini 카테고리 필터 + 키워드 추출...')
    results = extract_keywords_batch(repeated)

    sourceable = [r for r in results if r.get('sourceable')]
    not_sourceable = [r for r in results if not r.get('sourceable')]
    print(f'\n  📊 결과: 소싱 가능 {len(sourceable)}개 / 불가 {len(not_sourceable)}개')

    # 4. 기존 스캔 스킵
    print(f'\n[4/4] 기존 스캔 키워드 체크...')
    new_keywords, skipped = filter_existing_scans(results)
    print(f'  신규 키워드: {len(new_keywords)}개 / 기존 스킵: {len(skipped)}개')

    # 리포트
    print('\n' + '=' * 60)
    print('📋 소싱 가능 상품 + 추출 키워드')
    print('=' * 60)
    for r in sourceable:
        kws = ', '.join(r.get('keywords', []))
        print(f'  [{r["repeat_days"]}일] {r["name"][:45]}')
        print(f'         ₩{r["avg_price"]:,} | 키워드: {kws}')

    print('\n' + '=' * 60)
    print('🆕 신규 스캔 대상 키워드')
    print('=' * 60)
    for i, kw in enumerate(new_keywords):
        print(f'  {i+1}. "{kw["keyword"]}" ← {kw["source_product"][:40]} [{kw["repeat_days"]}일]')

    if not_sourceable:
        print(f'\n--- 소싱 불가 ({len(not_sourceable)}개) ---')
        for r in not_sourceable[:10]:
            print(f'  ❌ {r["name"][:45]} ({r.get("filter_reason", "")})')
        if len(not_sourceable) > 10:
            print(f'  ... 외 {len(not_sourceable) - 10}개')

    return {
        'sourceable': sourceable,
        'not_sourceable': not_sourceable,
        'new_keywords': new_keywords,
        'skipped_keywords': skipped,
    }


if __name__ == '__main__':
    min_days = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    result = run_pipeline(min_days=min_days)

    # 결과 JSON 저장
    output_path = os.path.join(os.path.dirname(__file__), 'goldbox_pipeline_result.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f'\n💾 결과 저장: {output_path}')
