"""
기회점수 산출 엔진 v2

대표님 핵심 기준:
1. 매출 분포가 고른 시장 (상위3 독식 X)
2. 300만원+ 판매자가 40~50% 이상
3. 4~10등 평균매출 = 내가 진입 시 기대매출
4. 신상품 가중치 (매출/리뷰/1000) — 리뷰 적은데 잘 팔리면 시장 수요 신호
"""

import math
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OpportunityScore:
    """기회점수 결과"""
    keyword: str = ''
    total_score: float = 0          # 종합 기회점수 (0~100)
    grade: str = ''                 # A/B/C/D

    # 1. 매출 분산도
    top3_revenue_sum: int = 0       # 상위3 매출 합
    rest_revenue_sum: int = 0       # 나머지 37개 매출 합
    top3_share: float = 0           # 상위3 점유율
    concentration_score: float = 0

    # 2. 시장 활성도
    sellers_over_3m: int = 0        # 300만원+ 판매자 수
    sellers_over_3m_rate: float = 0 # 300만원+ 비율
    activity_score: float = 0

    # 3. 진입 기대 매출
    top4_10_avg_revenue: int = 0    # 4~10등 평균매출
    top4_10_avg_sales: int = 0      # 4~10등 평균판매량
    top4_10_avg_price: int = 0      # 4~10등 평균가격
    entry_revenue_score: float = 0

    # 4. 시장 수요 신호 (신상품 가중치)
    new_product_rate: float = 0     # 신상품 비율 (리뷰 100 미만)
    avg_new_product_weight: float = 0  # 신상품 가중치 평균
    demand_signal_score: float = 0

    # 보조 지표
    top10_avg_revenue: int = 0
    top10_avg_sales: int = 0
    top10_avg_price: int = 0
    top1_share: float = 0
    revenue_equality: float = 0
    total_products: int = 0

    # 추천
    recommended_keyword: str = ''


def calculate_opportunity(products: list, inflow_keywords: list = None,
                          related_keywords: list = None, keyword: str = '') -> OpportunityScore:
    """
    기회점수 산출 v2

    기회점수 = 매출분산도(40%) + 시장활성도(25%) + 진입기대매출(20%) + 시장수요신호(15%)
    """
    score = OpportunityScore(keyword=keyword)

    if not products:
        return score

    # 매출순 정렬
    sorted_products = sorted(products, key=lambda p: p.revenue_monthly, reverse=True)
    score.total_products = len(sorted_products)

    # ─── 1. 매출 분산도 (40%) ───
    # 상위3 vs 나머지: 나머지가 더 크면 좋은 시장
    top3 = sorted_products[:3]
    rest = sorted_products[3:]

    score.top3_revenue_sum = sum(p.revenue_monthly for p in top3)
    score.rest_revenue_sum = sum(p.revenue_monthly for p in rest)
    total_revenue = score.top3_revenue_sum + score.rest_revenue_sum

    if total_revenue > 0:
        score.top3_share = score.top3_revenue_sum / total_revenue

    # 점수: 상위3 점유율 30% 미만 = 100점, 80% 이상 = 0점
    score.concentration_score = max(0, min(100,
        (0.80 - score.top3_share) / 0.50 * 100
    ))

    # ─── 2. 시장 활성도 (25%) ───
    # 월매출 300만원 이상 판매자 비율
    score.sellers_over_3m = sum(1 for p in sorted_products if p.revenue_monthly >= 3_000_000)
    score.sellers_over_3m_rate = score.sellers_over_3m / len(sorted_products) if sorted_products else 0

    # 점수: 65% 이상 = 100점, 15% 이하 = 0점
    score.activity_score = max(0, min(100,
        (score.sellers_over_3m_rate - 0.15) / 0.50 * 100
    ))

    # ─── 3. 진입 기대 매출 (20%) ───
    # 4~10등 평균매출 = 내가 10등 안에 들면 기대할 수 있는 매출
    top4_10 = sorted_products[3:10]
    if top4_10:
        revenues = [p.revenue_monthly for p in top4_10]
        sales = [p.sales_monthly for p in top4_10]
        prices = [p.price for p in top4_10 if p.price > 0]

        score.top4_10_avg_revenue = int(sum(revenues) / len(revenues))
        score.top4_10_avg_sales = int(sum(sales) / len(sales))
        score.top4_10_avg_price = int(sum(prices) / len(prices)) if prices else 0

    # 점수: 5,000만원 이상 = 100점, 100만원 이하 = 0점 (로그 스케일)
    if score.top4_10_avg_revenue > 0:
        score.entry_revenue_score = max(0, min(100,
            (math.log10(max(score.top4_10_avg_revenue, 1)) - math.log10(1_000_000)) /
            (math.log10(50_000_000) - math.log10(1_000_000)) * 100
        ))

    # ─── 4. 시장 수요 신호 (15%) ───
    # 신상품 가중치 = 매출 / 리뷰 / 1000 (리뷰 적은데 매출 높으면 시장 수요)
    new_products = [p for p in sorted_products if p.review_count < 100]
    score.new_product_rate = len(new_products) / len(sorted_products) if sorted_products else 0

    # 신상품 가중치 평균 (리뷰 100 미만 상품들)
    weights = []
    for p in new_products:
        reviews = max(p.review_count, 1)  # 0 방지
        w = p.revenue_monthly / reviews / 1000
        weights.append(w)

    score.avg_new_product_weight = sum(weights) / len(weights) if weights else 0

    # 점수: 신상품 진입률 + 신상품 가중치 조합
    # 진입률 40%+ = 50점, 가중치 100+ = 50점
    rate_score = min(50, score.new_product_rate / 0.40 * 50)
    weight_score = min(50, score.avg_new_product_weight / 100 * 50)
    score.demand_signal_score = rate_score + weight_score

    # ─── 보조 지표 (표시용) ───
    top10 = sorted_products[:10]
    if top10:
        rev10 = [p.revenue_monthly for p in top10]
        sal10 = [p.sales_monthly for p in top10]
        pri10 = [p.price for p in top10 if p.price > 0]
        score.top10_avg_revenue = int(sum(rev10) / len(rev10))
        score.top10_avg_sales = int(sum(sal10) / len(sal10))
        score.top10_avg_price = int(sum(pri10) / len(pri10)) if pri10 else 0

        if total_revenue > 0:
            score.top1_share = sorted_products[0].revenue_monthly / total_revenue

        if len(rev10) >= 2 and rev10[0] > 0:
            score.revenue_equality = rev10[-1] / rev10[0]

    # ─── 추천 키워드 (연관 키워드에서) ───
    if related_keywords:
        best_ratio = 0
        for kw in related_keywords[:50]:
            if kw.product_count > 0 and kw.total_search >= 1000 and not kw.is_brand:
                ratio = kw.total_search / kw.product_count
                if ratio > best_ratio:
                    best_ratio = ratio
                    score.recommended_keyword = kw.keyword

    # ─── 종합 기회점수 ───
    score.total_score = (
        score.concentration_score * 0.40 +
        score.activity_score * 0.25 +
        score.entry_revenue_score * 0.20 +
        score.demand_signal_score * 0.15
    )

    # 등급
    if score.total_score >= 75:
        score.grade = 'A'
    elif score.total_score >= 55:
        score.grade = 'B'
    elif score.total_score >= 35:
        score.grade = 'C'
    else:
        score.grade = 'D'

    logger.info(
        f'기회점수: {keyword} = {score.total_score:.1f} ({score.grade}) '
        f'| 분산 {score.concentration_score:.0f} | 활성 {score.activity_score:.0f} '
        f'| 기대매출 {score.entry_revenue_score:.0f} | 수요신호 {score.demand_signal_score:.0f}'
    )

    return score


def generate_keyword_variants(keyword: str) -> list:
    """쿠팡 띄어쓰기 변형 키워드 생성"""
    variants = set()
    variants.add(keyword)

    no_space = keyword.replace(' ', '')
    if no_space != keyword:
        variants.add(no_space)

    words = keyword.split()
    if len(words) >= 2:
        for i in range(len(words) - 1):
            merged = words[:i] + [words[i] + words[i+1]] + words[i+2:]
            variants.add(' '.join(merged))

    if len(no_space) >= 4:
        for i in range(2, len(no_space) - 1):
            variants.add(no_space[:i] + ' ' + no_space[i:])

    variants.discard(keyword)
    return list(variants)
