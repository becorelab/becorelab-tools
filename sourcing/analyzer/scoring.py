"""
기회점수 산출 엔진
대표님 핵심 기준:
1. 매출 쏠림 없이 상위 판매자가 골고루 잘 파는가
2. 판매자 실력이 아니라 수요>공급이라서 잘 팔리는가
3. 키워드 단위 분석 (같은 제품도 키워드마다 경쟁도 다름)
"""

import math
import logging
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OpportunityScore:
    """기회점수 결과"""
    keyword: str = ''
    total_score: float = 0          # 종합 기회점수 (0~100)

    # 시장 매력도 지표
    market_size: float = 0          # 시장 규모 점수
    top10_avg_revenue: int = 0      # 상위10 평균매출
    top10_avg_sales: int = 0        # 상위10 평균판매량
    top10_avg_price: int = 0        # 상위10 평균판매가

    # 매출 집중도 지표 (낮을수록 좋음)
    top1_share: float = 0           # 1위 점유율
    top3_concentration: float = 0   # 상위3 집중도
    revenue_equality: float = 0     # 매출균등도 (10위/1위, 높을수록 분산)
    concentration_score: float = 0  # 매출 분산 점수

    # 진입 용이도 지표
    new_product_rate: float = 0     # 신상품 진입률 (리뷰 100개 미만 비율)
    new_product_performance: float = 0  # 신상품 성과율
    ad_dependency: float = 0        # 광고 의존도
    entry_score: float = 0          # 진입 용이도 점수

    # 수익성 지표
    avg_price: int = 0
    estimated_margin_rate: float = 0
    profitability_score: float = 0

    # 키워드 경쟁 지표
    search_volume: int = 0          # 검색량
    product_count: int = 0          # 상품수
    search_product_ratio: float = 0 # 검색량/상품수 비율
    competition_level: str = ''

    # 추천
    recommended_keyword: str = ''
    recommendation_reason: str = ''
    grade: str = ''                 # A/B/C/D


def calculate_opportunity(products: list, inflow_keywords: list = None,
                          related_keywords: list = None, keyword: str = '') -> OpportunityScore:
    """
    기회점수 산출

    Args:
        products: CoupangProduct 리스트 (상위 40개)
        inflow_keywords: InflowKeyword 리스트
        related_keywords: RelatedKeyword 리스트
        keyword: 검색 키워드
    """
    score = OpportunityScore(keyword=keyword)

    if not products:
        return score

    # 비광고 상품만 필터 (실제 오가닉 순위)
    organic = [p for p in products if not p.is_ad]
    if not organic:
        organic = products

    # ─── 1. 시장 규모 분석 ───
    top10 = organic[:10]
    if top10:
        revenues = [p.revenue_monthly for p in top10 if p.revenue_monthly > 0]
        sales = [p.sales_monthly for p in top10 if p.sales_monthly > 0]
        prices = [p.price for p in top10 if p.price > 0]

        score.top10_avg_revenue = int(sum(revenues) / len(revenues)) if revenues else 0
        score.top10_avg_sales = int(sum(sales) / len(sales)) if sales else 0
        score.top10_avg_price = int(sum(prices) / len(prices)) if prices else 0

        # 시장 규모 점수 (상위10 평균매출 기준, 500만~5000만 범위)
        if score.top10_avg_revenue > 0:
            score.market_size = min(100, max(0,
                (math.log10(score.top10_avg_revenue) - math.log10(500_000)) /
                (math.log10(50_000_000) - math.log10(500_000)) * 100
            ))

    # ─── 2. 매출 집중도 분석 ───
    if len(top10) >= 3:
        revenues_sorted = sorted(
            [p.revenue_monthly for p in top10 if p.revenue_monthly > 0],
            reverse=True
        )

        if revenues_sorted:
            total_rev = sum(revenues_sorted)

            # 1위 점유율
            score.top1_share = revenues_sorted[0] / total_rev if total_rev > 0 else 0

            # 상위3 집중도
            top3_rev = sum(revenues_sorted[:3])
            score.top3_concentration = top3_rev / total_rev if total_rev > 0 else 0

            # 매출균등도 (10위/1위)
            if len(revenues_sorted) >= 2:
                score.revenue_equality = revenues_sorted[-1] / revenues_sorted[0]

            # 집중도 점수 (분산될수록 높음)
            # 1위 점유율 20% 이하 = 100점, 50% 이상 = 0점
            share_score = max(0, min(100, (0.5 - score.top1_share) / 0.3 * 100))
            # 균등도 0.3 이상 = 100점, 0.05 이하 = 0점
            equality_score = max(0, min(100, (score.revenue_equality - 0.05) / 0.25 * 100))

            score.concentration_score = share_score * 0.5 + equality_score * 0.5

    # ─── 3. 진입 용이도 분석 ───
    if organic:
        # 신상품 진입률 (리뷰 100개 미만이 상위 40에 몇 개?)
        new_products = [p for p in organic if p.review_count < 100]
        score.new_product_rate = len(new_products) / len(organic)

        # 신상품 성과율 (리뷰 100개 미만 중 상위 20에 든 비율)
        top20_new = [p for p in organic[:20] if p.review_count < 100]
        score.new_product_performance = len(top20_new) / max(1, len(new_products)) if new_products else 0

        # 광고 의존도
        if inflow_keywords:
            ad_weights = [kw.ad_weight for kw in inflow_keywords if kw.ad_weight > 0]
            if ad_weights:
                # 검색량 가중 평균 광고비중
                total_vol = sum(kw.search_volume for kw in inflow_keywords if kw.search_volume > 0)
                if total_vol > 0:
                    weighted_ad = sum(
                        kw.ad_weight * kw.search_volume
                        for kw in inflow_keywords
                        if kw.search_volume > 0
                    ) / total_vol
                    score.ad_dependency = weighted_ad
                else:
                    score.ad_dependency = sum(ad_weights) / len(ad_weights)

        # 진입 용이도 점수
        # 신상품 진입률 높을수록 좋음 (0.3이상 = 100)
        new_rate_score = min(100, score.new_product_rate / 0.3 * 100)
        # 광고 의존도 낮을수록 좋음 (10% 이하 = 100, 50% 이상 = 0)
        ad_score = max(0, min(100, (50 - score.ad_dependency) / 40 * 100))

        score.entry_score = new_rate_score * 0.6 + ad_score * 0.4

    # ─── 4. 수익성 분석 ───
    if score.top10_avg_price > 0:
        # 단순 추정: 판매가 대비 원가 비율 (카테고리별 차이 있지만 평균 30~40%)
        estimated_cost_rate = 0.35
        score.estimated_margin_rate = (1 - estimated_cost_rate) * 100
        score.avg_price = score.top10_avg_price

        # 가격대 점수 (1만원~10만원 사이가 적정)
        if 10000 <= score.top10_avg_price <= 100000:
            score.profitability_score = 80
        elif 5000 <= score.top10_avg_price < 10000:
            score.profitability_score = 50
        else:
            score.profitability_score = 30

    # ─── 5. 키워드 경쟁 분석 ───
    if related_keywords:
        for kw in related_keywords:
            if kw.keyword == keyword:
                score.search_volume = kw.total_search
                score.product_count = kw.product_count
                score.competition_level = kw.competition
                if kw.product_count > 0:
                    score.search_product_ratio = kw.total_search / kw.product_count
                break

    # ─── 6. 추천 진입 키워드 ───
    if inflow_keywords:
        # 광고비중 낮고 검색량 높은 키워드 추천
        candidates = [
            kw for kw in inflow_keywords
            if kw.search_volume >= 1000 and kw.ad_weight < 30
        ]
        if candidates:
            # 검색량 / (광고비중 + 1) 비율로 정렬
            best = max(candidates, key=lambda k: k.search_volume / (k.ad_weight + 1))
            score.recommended_keyword = best.keyword
            score.recommendation_reason = (
                f'검색량 {best.search_volume:,} | 광고비중 {best.ad_weight:.1f}%'
            )

    # ─── 7. 종합 기회점수 ───
    # 기회점수 = 시장매력도(30%) × 진입용이도(35%) × 매출분산(25%) × 수익성(10%)
    score.total_score = (
        score.market_size * 0.30 +
        score.entry_score * 0.35 +
        score.concentration_score * 0.25 +
        score.profitability_score * 0.10
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
        f'기회점수 산출: {keyword} = {score.total_score:.1f} ({score.grade}) '
        f'| 시장 {score.market_size:.0f} | 진입 {score.entry_score:.0f} '
        f'| 분산 {score.concentration_score:.0f}'
    )

    return score


def generate_keyword_variants(keyword: str) -> list:
    """
    쿠팡 띄어쓰기 변형 키워드 생성
    쿠팡은 띄어쓰기도 별도 검색어로 인식
    """
    variants = set()
    variants.add(keyword)

    # 1. 모든 공백 제거 (붙여쓰기)
    no_space = keyword.replace(' ', '')
    if no_space != keyword:
        variants.add(no_space)

    # 2. 단어 사이 공백 추가/제거 변형
    words = keyword.split()
    if len(words) >= 2:
        # 각 위치에서 공백 제거
        for i in range(len(words) - 1):
            merged = words[:i] + [words[i] + words[i+1]] + words[i+2:]
            variants.add(' '.join(merged))

    # 3. 붙여쓰기에서 자연스러운 위치에 공백 삽입
    if len(no_space) >= 4:
        for i in range(2, len(no_space) - 1):
            variant = no_space[:i] + ' ' + no_space[i:]
            variants.add(variant)

    variants.discard(keyword)  # 원본 제외
    return list(variants)


# ─────────────────────────────────────────────
# 테스트
# ─────────────────────────────────────────────
if __name__ == '__main__':
    # 변형 키워드 테스트
    test_keywords = ['발바닥 마사지기', '고체 탈취제', '일회용 팬티']
    for kw in test_keywords:
        variants = generate_keyword_variants(kw)
        print(f'\n"{kw}" 변형:')
        for v in variants:
            print(f'  → "{v}"')
