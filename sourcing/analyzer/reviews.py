"""
쿠팡 리뷰 수집 + 분석
1. 상위 상품들의 리뷰를 쿠팡 API로 수집
2. Claude API로 분석 (장단점/인기 형태/소싱 포인트)
"""

import re
import json
import logging
import requests
from collections import Counter

logger = logging.getLogger(__name__)

import os

REVIEW_API = 'https://www.coupang.com/next-api/review'

# API 키 로드 (.env 파일 지원)
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            if _line.startswith('ANTHROPIC_API_KEY=') and not ANTHROPIC_API_KEY:
                ANTHROPIC_API_KEY = _line.split('=', 1)[1].strip()
            elif _line.startswith('GEMINI_API_KEY=') and not GEMINI_API_KEY:
                GEMINI_API_KEY = _line.split('=', 1)[1].strip()


def _call_gemini(prompt: str, max_tokens: int = 4000) -> str:
    """Gemini 2.0 Flash API 호출 (무료 티어)"""
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}'
    res = requests.post(url, json={
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'maxOutputTokens': max_tokens,
            'thinkingConfig': {'thinkingBudget': 0},
        },
    }, timeout=60)
    if res.ok:
        data = res.json()
        candidates = data.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            if parts:
                return parts[0].get('text', '')
    logger.error(f'Gemini API 에러: {res.status_code} {res.text[:200]}')
    return ''


def collect_reviews_from_browser(page, product_url: str, max_reviews: int = 50) -> list:
    """
    Playwright 브라우저에서 쿠팡 리뷰 API 호출.
    product_url에서 productId 추출 → review API 호출
    """
    # productId 추출
    pid_match = re.search(r'products/(\d+)', product_url)
    if not pid_match:
        return []
    pid = pid_match.group(1)

    reviews = []
    page_size = 20
    pages = (max_reviews // page_size) + 1

    for p in range(1, pages + 1):
        try:
            result = page.evaluate(f'''() => {{
                return new Promise(resolve => {{
                    fetch('/next-api/review?productId={pid}&page={p}&size={page_size}&sortBy=DATE_DESC&ratingSummary=true', {{
                        credentials: 'include',
                        headers: {{ 'accept': 'application/json' }}
                    }})
                    .then(r => r.json())
                    .then(d => resolve(d))
                    .catch(e => resolve({{error: e.toString()}}));
                }});
            }}''')

            if result.get('error'):
                break

            data = result.get('data', {})
            review_list = data.get('reviews', [])

            for r in review_list:
                reviews.append({
                    'rating': r.get('rating', 0),
                    'headline': r.get('headline', ''),
                    'content': r.get('content', ''),
                    'created': r.get('createdAt', ''),
                    'helpful_count': r.get('helpfulCount', 0),
                    'photos': len(r.get('photos', [])),
                })

            if len(review_list) < page_size:
                break  # 마지막 페이지

        except Exception as e:
            logger.error(f'리뷰 수집 에러 (pid={pid}, page={p}): {e}')
            break

    return reviews


def collect_reviews_for_scan(wing_send, products: list, max_per_product: int = 30) -> dict:
    """
    스캔 결과의 상위 상품들에서 리뷰 수집.
    wing_send: wing.py의 _send 함수
    products: 상위 상품 리스트 (product_url 필요)
    """
    # 상위 10개 상품에서 리뷰 수집
    all_reviews = []
    product_reviews = {}

    for p in products[:10]:
        if not p.get('product_url'):
            continue
        pid_match = re.search(r'products/(\d+)', p['product_url'])
        if not pid_match:
            continue

        pid = pid_match.group(1)
        try:
            reviews = wing_send('collect_reviews', {
                'product_url': p['product_url'],
                'max_reviews': max_per_product
            })
            if reviews:
                product_reviews[p.get('product_name', pid)] = reviews
                all_reviews.extend(reviews)
        except Exception as e:
            logger.error(f'리뷰 수집 실패: {p.get("product_name", "")[:20]} — {e}')

    return {
        'total_reviews': len(all_reviews),
        'products_analyzed': len(product_reviews),
        'all_reviews': all_reviews,
        'by_product': product_reviews,
    }


def analyze_reviews_basic(reviews: list, keyword: str = '') -> dict:
    """
    기본 리뷰 분석 (API 없이)
    - 평점 분포
    - 자주 나오는 키워드
    - 긍정/부정 비율
    """
    if not reviews:
        return {'error': '리뷰가 없습니다'}

    # 평점 분포
    ratings = [r.get('rating', 0) for r in reviews]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    rating_dist = Counter(ratings)

    # 텍스트 합치기
    all_text = ' '.join([
        (r.get('headline', '') + ' ' + r.get('content', ''))
        for r in reviews
    ])

    # 긍정/부정 키워드
    positive_words = ['좋아요', '만족', '추천', '편해요', '편하', '좋습니다', '최고', '훌륭', '괜찮', '깔끔',
                      '부드러', '푹신', '가성비', '빠른', '든든', '튼튼', '예쁘', '깨끗', '향기', '좋은']
    negative_words = ['별로', '아쉬', '불편', '냄새', '작아', '크기', '불량', '얇아', '약해', '비싸',
                      '배송', '파손', '교환', '반품', '후회', '실망', '하자', '찢어', '안맞', '불만']

    pos_count = sum(1 for w in positive_words if w in all_text)
    neg_count = sum(1 for w in negative_words if w in all_text)

    # 자주 나오는 2~4글자 한글 단어
    words = re.findall(r'[가-힣]{2,4}', all_text)
    # 불용어 제거
    stopwords = {'합니다', '있어요', '없어요', '그리고', '하지만', '인데요', '이에요', '해서요',
                 '같아요', '거예요', '했는데', '입니다', '습니다', '에서요', '니다요'}
    word_freq = Counter(w for w in words if w not in stopwords)
    top_keywords = word_freq.most_common(20)

    # 특성 키워드 추출 (제품 형태/기능 관련)
    feature_patterns = {
        '소재': ['실리콘', '메모리폼', '라텍스', '가죽', '메쉬', '쿠션', '젤', '에어', '폼', '면',
                 '스테인리스', '플라스틱', '원목', '세라믹', '유리'],
        '기능': ['통풍', '방수', '항균', '탈취', '보온', '냉감', '충격흡수', '아치', '교정',
                 '접이식', '휴대용', '무선', '충전', '자동'],
        '디자인': ['심플', '슬림', '미니', '대용량', '컴팩트', '투명', '블랙', '화이트',
                  '무광', '매트', '모던', '빈티지'],
    }

    detected_features = {}
    for category, patterns in feature_patterns.items():
        found = [(p, all_text.count(p)) for p in patterns if p in all_text]
        if found:
            detected_features[category] = sorted(found, key=lambda x: x[1], reverse=True)

    return {
        'total_reviews': len(reviews),
        'avg_rating': round(avg_rating, 1),
        'rating_distribution': dict(sorted(rating_dist.items())),
        'positive_ratio': round(pos_count / max(pos_count + neg_count, 1) * 100, 1),
        'top_keywords': top_keywords,
        'features': detected_features,
        'positive_mentions': pos_count,
        'negative_mentions': neg_count,
    }


def _analyze_with_claude(reviews: list, keyword: str, api_key: str) -> dict:
    """호환용 래퍼 — 내부적으로 Gemini 분석 사용"""
    return analyze_reviews_claude(reviews, keyword, api_key)


def analyze_reviews_claude(reviews: list, keyword: str, api_key: str = '') -> dict:
    """리뷰 분석 — Gemini 우선, 실패 시 기본 분석으로 폴백"""

    # 리뷰 텍스트 준비 (최대 300개) — 상품명 포함
    review_texts = []
    for r in reviews[:300]:
        pname = r.get('productName', '')
        stars = '★' * r.get('rating', 0)
        text = f"[{stars}] [{pname}] {r.get('headline', '')} {r.get('content', '')}"
        review_texts.append(text.strip())

    review_block = '\n---\n'.join(review_texts)

    prompt = f"""다음은 쿠팡에서 "{keyword}" 키워드로 판매되는 상위 상품들의 소비자 리뷰입니다.

{review_block}

위 리뷰를 분석하여 다음 항목을 JSON 형식으로 답해주세요:

1. "summary": 소비자가 이 제품군에 대해 전반적으로 느끼는 점 (3줄)
2. "pros": 소비자가 가장 많이 언급하는 장점 5가지 (배열)
3. "cons": 소비자가 가장 많이 언급하는 단점/불만 5가지 (배열)
4. "popular_types": 가장 인기 있는 제품 형태/타입 3가지와 이유 (배열, 각 항목은 {{"type": "", "reason": ""}})
5. "key_features": 소비자가 중요하게 생각하는 기능/특성 5가지 (배열)
6. "sourcing_tips": 이 제품을 소싱할 때 포커스해야 할 포인트 3가지 (배열)
7. "differentiation": 기존 제품 대비 차별화할 수 있는 아이디어 3가지 (배열)
8. "top_products": 리뷰에서 가장 많이 언급된 상품 3개와 소비자 평가 요약 (배열, 각 항목은 {{"name": "상품명", "summary": "한줄평"}})

JSON만 답해주세요."""

    try:
        content = _call_gemini(prompt, max_tokens=4000)
        if content:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                analysis = json.loads(json_match.group())
                analysis['_source'] = 'gemini'
                return analysis

    except Exception as e:
        logger.error(f'Gemini API 호출 실패: {e}')

    # 실패 시 기본 분석으로 폴백
    return analyze_reviews_basic(reviews, keyword)
