"""경쟁 분석 엔진 — 3개 collector 데이터 통합 분석"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime
from typing import Optional

from competitor_analyzer.config import OUR_MALL_NAMES, PRODUCTS

logger = logging.getLogger(__name__)

_GRADE_RANK = {
    '플래티넘': 5,
    '프리미엄': 4,
    '빅파워': 3,
    '파워': 2,
    '씨앗': 1,
    '': 0,
}


def _grade_order(grade: str) -> int:
    for key in _GRADE_RANK:
        if key and key in grade:
            return _GRADE_RANK[key]
    return 0


def _percentile(values: list[float], target: float) -> float:
    """target이 values 내에서 하위 몇 %인지 반환 (낮을수록 저렴)"""
    if not values:
        return 0.0
    below = sum(1 for v in values if v < target)
    return round(below / len(values) * 100, 1)


class CompetitorAnalyzer:
    """경쟁 분석 엔진"""

    def analyze(
        self,
        product_key: str,
        naver_results: list[dict],
        keyword_analysis: dict = None,
        ranking_data: dict = None,
        smartstore_data: dict = None,
        multi_keyword_data: dict = None,
        our_brand_data: list[dict] = None,
    ) -> dict:
        """
        제품별 종합 분석 실행.

        Returns:
            {
                'product': str,
                'analyzed_at': str,
                'our_product': dict,
                'market_summary': dict,
                'price_analysis': dict,
                'review_analysis': dict,
                'mall_grade_analysis': dict,
                'keyword_analysis': dict,
                'ranking_trend': dict,
                'traffic_analysis': dict,
                'diagnosis': list[dict],
                'priority_score': float,
                'recommendations': list[str],
            }
        """
        logger.info('분석 시작: product_key=%s, naver_results=%d건', product_key, len(naver_results or []))

        product_config = PRODUCTS.get(product_key, {})
        our_product = self._find_our_product(naver_results or [])

        # 검색 순위에 없으면 브랜드 검색 데이터에서 우리 상품 보완
        if not our_product and our_brand_data:
            our_product = our_brand_data[0] if our_brand_data else None
            if our_product:
                our_product['_from_brand_search'] = True
                logger.info('우리 상품: 순위 밖 → 브랜드 검색에서 보완 (리뷰 %d, 구매 %d)',
                           our_product.get('review_count', 0), our_product.get('purchase_count', 0))
        elif our_product and our_brand_data:
            # 순위 내 있지만 리뷰 0이면 브랜드 검색 데이터로 보완
            brand_best = our_brand_data[0] if our_brand_data else None
            if brand_best and brand_best.get('review_count', 0) > our_product.get('review_count', 0):
                our_product['review_count'] = brand_best['review_count']
                our_product['purchase_count'] = brand_best.get('purchase_count', our_product.get('purchase_count', 0))
                our_product['zzim_count'] = brand_best.get('zzim_count', our_product.get('zzim_count', 0))
                logger.info('우리 상품: 리뷰 데이터 브랜드 검색에서 보강 (리뷰 %d)', brand_best['review_count'])

        organic = [p for p in (naver_results or []) if not p.get('is_ad')]
        all_results = naver_results or []

        market_summary = self._build_market_summary(all_results, organic)
        multi_keyword_summary = self._build_multi_keyword_summary(multi_keyword_data) if multi_keyword_data else {}
        price_analysis = self._build_price_analysis(our_product, all_results, product_config)
        review_analysis = self._build_review_analysis(our_product, all_results)
        mall_grade_analysis = self._build_mall_grade_analysis(our_product, all_results)
        kw_analysis = self._build_keyword_analysis(keyword_analysis)
        rank_trend = self._build_ranking_trend(ranking_data)
        traffic = self._build_traffic_analysis(smartstore_data)

        diagnosis = self._diagnose(
            product_key=product_key,
            product_config=product_config,
            our_product=our_product,
            price_analysis=price_analysis,
            review_analysis=review_analysis,
            mall_grade_analysis=mall_grade_analysis,
            kw_analysis=kw_analysis,
            rank_trend=rank_trend,
            traffic=traffic,
            market_summary=market_summary,
        )

        priority_score = self._calc_priority_score(
            price_analysis=price_analysis,
            review_analysis=review_analysis,
            rank_trend=rank_trend,
            traffic=traffic,
            our_product=our_product,
        )

        recommendations = self._build_recommendations(diagnosis)

        return {
            'product': product_key,
            'analyzed_at': datetime.now().isoformat(),
            'our_product': our_product or {},
            'market_summary': market_summary,
            'multi_keyword_summary': multi_keyword_summary,
            'price_analysis': price_analysis,
            'review_analysis': review_analysis,
            'mall_grade_analysis': mall_grade_analysis,
            'keyword_analysis': kw_analysis,
            'ranking_trend': rank_trend,
            'traffic_analysis': traffic,
            'competitors_table': all_results,
            'multi_keyword_products': (multi_keyword_data or {}).get('products', []),
            'our_brand_products': our_brand_data or [],
            'diagnosis': diagnosis,
            'priority_score': priority_score,
            'recommendations': recommendations,
        }

    # ------------------------------------------------------------------
    # 우리 상품 찾기
    # ------------------------------------------------------------------

    def _find_our_product(self, results: list[dict]) -> Optional[dict]:
        for item in results:
            mall = item.get('mall_name', '')
            if any(name.lower() in mall.lower() for name in OUR_MALL_NAMES):
                return item
        return None

    # ------------------------------------------------------------------
    # 시장 요약
    # ------------------------------------------------------------------

    def _build_market_summary(self, all_results: list[dict], organic: list[dict]) -> dict:
        if not all_results:
            return {}

        valid_prices = [p['price'] for p in all_results if p.get('price', 0) > 0]
        ad_count = sum(1 for p in all_results if p.get('is_ad'))
        ad_ratio = round(ad_count / len(all_results) * 100, 1) if all_results else 0.0

        review_counts = [p.get('review_count', 0) for p in all_results]

        grade_dist: dict[str, int] = {}
        for p in all_results:
            grade = p.get('mall_grade') or '기타'
            grade_dist[grade] = grade_dist.get(grade, 0) + 1

        purchase_counts = [p.get('purchase_count', 0) for p in all_results if p.get('purchase_count')]
        revenues = [p.get('estimated_revenue', 0) for p in all_results if p.get('estimated_revenue')]

        return {
            'total_count': len(all_results),
            'organic_count': len(organic),
            'ad_count': ad_count,
            'ad_ratio': ad_ratio,
            'avg_price': round(statistics.mean(valid_prices)) if valid_prices else 0,
            'median_price': round(statistics.median(valid_prices)) if valid_prices else 0,
            'min_price': min(valid_prices) if valid_prices else 0,
            'max_price': max(valid_prices) if valid_prices else 0,
            'avg_review_count': round(statistics.mean(review_counts)) if review_counts else 0,
            'max_review_count': max(review_counts) if review_counts else 0,
            'grade_distribution': grade_dist,
            'total_estimated_revenue': sum(revenues),
            'avg_purchase_count': round(statistics.mean(purchase_counts)) if purchase_counts else 0,
            'max_purchase_count': max(purchase_counts) if purchase_counts else 0,
            'products_with_sales': len(purchase_counts),
        }

    # ------------------------------------------------------------------
    # 멀티 키워드 통합 시장 분석
    # ------------------------------------------------------------------

    def _build_multi_keyword_summary(self, multi_data: dict) -> dict:
        if not multi_data:
            return {}

        products = multi_data.get('products', [])
        keyword_stats = multi_data.get('keyword_stats', [])

        valid_prices = [p['price'] for p in products if p.get('price', 0) > 0]
        revenues = [p.get('estimated_revenue', 0) for p in products if p.get('estimated_revenue')]
        purchases = [p.get('purchase_count', 0) for p in products if p.get('purchase_count')]

        # 키워드별 수집 결과
        kw_breakdown = []
        for ks in keyword_stats:
            kw_breakdown.append({
                'keyword': ks['keyword'],
                'products_found': ks['count'],
                'ads': ks['ad_count'],
            })

        # 매출 TOP10
        top_sellers = sorted(
            [p for p in products if p.get('estimated_revenue', 0) > 0],
            key=lambda x: x['estimated_revenue'],
            reverse=True,
        )[:10]

        return {
            'total_keywords_searched': len(keyword_stats),
            'total_before_dedup': multi_data.get('total_before_dedup', 0),
            'total_unique_products': multi_data.get('total_unique', 0),
            'total_estimated_revenue': sum(revenues),
            'avg_price': round(statistics.mean(valid_prices)) if valid_prices else 0,
            'avg_purchase_count': round(statistics.mean(purchases)) if purchases else 0,
            'products_with_sales': len(purchases),
            'keyword_breakdown': kw_breakdown,
            'top_sellers': top_sellers,
        }

    # ------------------------------------------------------------------
    # 가격 분석
    # ------------------------------------------------------------------

    def _build_price_analysis(
        self, our_product: Optional[dict], all_results: list[dict], product_config: dict
    ) -> dict:
        valid_prices = [p['price'] for p in all_results if p.get('price', 0) > 0]
        if not valid_prices:
            return {}

        avg_price = statistics.mean(valid_prices)
        median_price = statistics.median(valid_prices)

        our_price_actual = (our_product or {}).get('price', 0) or product_config.get('our_price', 0)

        if not our_price_actual:
            return {
                'avg_price': round(avg_price),
                'median_price': round(median_price),
                'our_price': None,
                'price_ratio': None,
                'percentile': None,
                'verdict': 'unknown',
            }

        ratio = our_price_actual / avg_price
        percentile = _percentile(valid_prices, our_price_actual)

        if ratio <= 0.9:
            verdict = '우위'
        elif ratio <= 1.1:
            verdict = '적정'
        elif ratio <= 1.5:
            verdict = '열세'
        else:
            verdict = '심각'

        return {
            'avg_price': round(avg_price),
            'median_price': round(median_price),
            'min_price': min(valid_prices),
            'max_price': max(valid_prices),
            'our_price': our_price_actual,
            'price_ratio': round(ratio, 2),
            'percentile': percentile,
            'verdict': verdict,
        }

    # ------------------------------------------------------------------
    # 리뷰 분석
    # ------------------------------------------------------------------

    def _build_review_analysis(self, our_product: Optional[dict], all_results: list[dict]) -> dict:
        if not all_results:
            return {}

        review_counts = [p.get('review_count', 0) for p in all_results]
        avg_reviews = statistics.mean(review_counts) if review_counts else 0
        max_reviews = max(review_counts) if review_counts else 0

        our_reviews = (our_product or {}).get('review_count', None)

        if our_reviews is None:
            return {
                'avg_review_count': round(avg_reviews),
                'max_review_count': max_reviews,
                'our_review_count': None,
                'percentile': None,
                'verdict': 'unknown',
            }

        percentile = _percentile(review_counts, our_reviews)

        if percentile >= 60:
            verdict = '우위'
        elif percentile >= 30:
            verdict = '적정'
        elif percentile >= 10:
            verdict = '열세'
        else:
            verdict = '심각'

        return {
            'avg_review_count': round(avg_reviews),
            'max_review_count': max_reviews,
            'our_review_count': our_reviews,
            'percentile': percentile,
            'verdict': verdict,
        }

    # ------------------------------------------------------------------
    # 몰등급 분석
    # ------------------------------------------------------------------

    def _build_mall_grade_analysis(self, our_product: Optional[dict], all_results: list[dict]) -> dict:
        if not all_results:
            return {}

        top5 = all_results[:5]
        top5_grades = [p.get('mall_grade', '') for p in top5]
        our_grade = (our_product or {}).get('mall_grade', '')

        top5_avg_rank = (
            round(statistics.mean([_grade_order(g) for g in top5_grades if g]), 1)
            if any(top5_grades) else 0
        )
        our_rank = _grade_order(our_grade)

        if not our_grade:
            impact = '등급 정보 없음'
        elif our_rank >= top5_avg_rank:
            impact = '등급 경쟁력 있음'
        elif our_rank == top5_avg_rank - 1:
            impact = '등급 소폭 열세 — 전환에 미미한 영향'
        else:
            impact = '등급 열세 — 구매자 신뢰도 낮출 수 있음'

        return {
            'our_grade': our_grade,
            'top5_grades': top5_grades,
            'top5_avg_grade_rank': top5_avg_rank,
            'our_grade_rank': our_rank,
            'conversion_impact': impact,
        }

    # ------------------------------------------------------------------
    # 키워드 분석 (헬프스토어)
    # ------------------------------------------------------------------

    def _build_keyword_analysis(self, keyword_analysis: Optional[dict]) -> dict:
        if not keyword_analysis:
            return {}

        return {
            'keyword': keyword_analysis.get('keyword', ''),
            'total_search': keyword_analysis.get('total_search', 0),
            'product_count': keyword_analysis.get('product_count', 0),
            'competition': keyword_analysis.get('competition', ''),
            'related_keywords_count': len(keyword_analysis.get('related_keywords', [])),
            'related_keywords_top5': keyword_analysis.get('related_keywords', [])[:5],
            'content_count': keyword_analysis.get('content_count', {}),
        }

    # ------------------------------------------------------------------
    # 순위 추이 (헬프스토어)
    # ------------------------------------------------------------------

    def _build_ranking_trend(self, ranking_data: Optional[dict]) -> dict:
        if not ranking_data:
            return {}

        keywords = ranking_data.get('keywords', [])
        dates = ranking_data.get('dates', [])

        if not keywords or not dates:
            return {
                'product_id': ranking_data.get('product_id'),
                'dates': dates,
                'keywords': [],
                'best_rank': None,
                'latest_rank': None,
                'trend_direction': 'unknown',
            }

        keyword_summaries = []
        all_latest_ranks = []
        all_best_ranks = []

        for kw in keywords:
            ranks_data = kw.get('ranks', [])
            valid_ranks = [r['rank'] for r in ranks_data if r.get('rank', 0) > 0]

            latest_rank = None
            trend = 'unknown'
            best_rank = min(valid_ranks) if valid_ranks else None

            if ranks_data:
                for r in reversed(ranks_data):
                    if r.get('rank', 0) > 0:
                        latest_rank = r['rank']
                        trend = r.get('direction', 'same')
                        break

            if latest_rank:
                all_latest_ranks.append(latest_rank)
            if best_rank:
                all_best_ranks.append(best_rank)

            keyword_summaries.append({
                'keyword': kw.get('keyword', ''),
                'latest_rank': latest_rank,
                'best_rank': best_rank,
                'trend': trend,
            })

        overall_latest = min(all_latest_ranks) if all_latest_ranks else None
        overall_best = min(all_best_ranks) if all_best_ranks else None

        if all_latest_ranks:
            directions = []
            for kw in keywords:
                for r in reversed(kw.get('ranks', [])):
                    if r.get('rank', 0) > 0:
                        directions.append(r.get('direction', 'same'))
                        break
            up_count = directions.count('up')
            down_count = directions.count('down')
            if up_count > down_count:
                overall_trend = 'improving'
            elif down_count > up_count:
                overall_trend = 'declining'
            else:
                overall_trend = 'stable'
        else:
            overall_trend = 'not_ranked'

        return {
            'product_id': ranking_data.get('product_id'),
            'dates': dates,
            'keywords': keyword_summaries,
            'best_rank': overall_best,
            'latest_rank': overall_latest,
            'trend_direction': overall_trend,
        }

    # ------------------------------------------------------------------
    # 유입/전환 분석 (셀러센터)
    # ------------------------------------------------------------------

    def _build_traffic_analysis(self, smartstore_data: Optional[dict]) -> dict:
        if not smartstore_data:
            return {}

        keyword_traffic = smartstore_data.get('keyword_traffic', [])
        channel_summary = smartstore_data.get('channel_summary', [])

        total_visits = sum(r.get('visits', 0) for r in keyword_traffic)
        total_orders = sum(r.get('orders', 0) for r in keyword_traffic)
        total_revenue = sum(r.get('revenue', 0) for r in keyword_traffic)
        overall_cvr = (total_orders / total_visits * 100) if total_visits > 0 else 0.0

        top_keywords = sorted(keyword_traffic, key=lambda x: x.get('visits', 0), reverse=True)[:5]

        organic_channel = next(
            (c for c in channel_summary if '오가닉' in c.get('channel', '') or '검색' in c.get('channel', '')),
            None,
        )

        return {
            'total_visits': total_visits,
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'overall_conversion_rate': round(overall_cvr, 2),
            'top_keywords': top_keywords,
            'channel_summary': channel_summary,
            'organic_channel': organic_channel,
        }

    # ------------------------------------------------------------------
    # 종합 진단
    # ------------------------------------------------------------------

    def _diagnose(
        self,
        product_key: str,
        product_config: dict,
        our_product: Optional[dict],
        price_analysis: dict,
        review_analysis: dict,
        mall_grade_analysis: dict,
        kw_analysis: dict,
        rank_trend: dict,
        traffic: dict,
        market_summary: dict,
    ) -> list[dict]:
        issues: list[dict] = []

        # 1) 순위 밖
        if not our_product:
            issues.append({
                'issue': '검색 결과 순위 밖',
                'severity': 'critical',
                'detail': f'{product_key} 제품이 네이버 쇼핑 상위 40개 내 미노출',
                'action': '트래픽 작업(CPC/SEO) 즉시 시작 — 최소 1페이지 진입이 선행 조건',
            })

        # 2) 가격 분석
        price_verdict = price_analysis.get('verdict', 'unknown')
        our_price = price_analysis.get('our_price')
        avg_price = price_analysis.get('avg_price', 0)
        price_ratio = price_analysis.get('price_ratio')

        if price_verdict == '심각' and our_price and avg_price:
            issues.append({
                'issue': '가격 경쟁력 심각',
                'severity': 'critical',
                'detail': f'우리 가격 {our_price:,}원 = 경쟁 평균의 {price_ratio:.1f}배 ({avg_price:,}원)',
                'action': '1개입 / 소용량 SKU 별도 등록 또는 묶음 구성 재설계',
            })
        elif price_verdict == '열세' and our_price and avg_price:
            issues.append({
                'issue': '가격 경쟁력 열세',
                'severity': 'warning',
                'detail': f'우리 가격 {our_price:,}원 = 경쟁 평균의 {price_ratio:.1f}배 ({avg_price:,}원)',
                'action': '가격 인하 여지 검토 또는 스펙 차별화로 프리미엄 포지셔닝 강화',
            })
        elif price_verdict == '우위':
            issues.append({
                'issue': '가격 경쟁력 우위',
                'severity': 'info',
                'detail': f'우리 가격 {our_price:,}원 — 경쟁 평균 {avg_price:,}원 대비 저렴',
                'action': '현재 가격 구조 유지, 리뷰·순위 개선에 집중',
            })

        # 3) 리뷰 분석
        review_verdict = review_analysis.get('verdict', 'unknown')
        our_reviews = review_analysis.get('our_review_count')
        max_reviews = review_analysis.get('max_review_count', 0)
        avg_reviews = review_analysis.get('avg_review_count', 0)

        if review_verdict == '심각' and our_reviews is not None:
            issues.append({
                'issue': '리뷰 경쟁력 심각',
                'severity': 'critical',
                'detail': f'우리 리뷰 {our_reviews:,}개 vs 최상위 {max_reviews:,}개 / 평균 {avg_reviews:,}개',
                'action': '리뷰 캠페인 즉시 집중 투입 — 체험단/리뷰 이벤트 우선',
            })
        elif review_verdict == '열세' and our_reviews is not None:
            issues.append({
                'issue': '리뷰 경쟁력 열세',
                'severity': 'warning',
                'detail': f'우리 리뷰 {our_reviews:,}개 vs 평균 {avg_reviews:,}개',
                'action': '자연 리뷰 유도 강화 (구매 후 문자/카톡 발송, 포토 리뷰 인센티브)',
            })
        elif review_verdict == '우위':
            issues.append({
                'issue': '리뷰 경쟁력 양호',
                'severity': 'info',
                'detail': f'우리 리뷰 {our_reviews:,}개 — 상위 {review_analysis.get("percentile")}% 구간',
                'action': '리뷰 퀄리티(포토/영상 비율) 관리 병행',
            })

        # 4) 몰등급
        impact = mall_grade_analysis.get('conversion_impact', '')
        if '열세' in impact:
            issues.append({
                'issue': '몰등급 열세',
                'severity': 'warning',
                'detail': f'우리 등급: {mall_grade_analysis.get("our_grade") or "없음"} / 상위5 등급: {mall_grade_analysis.get("top5_grades")}',
                'action': '등급 상향 조건(매출/리뷰/CS 지표) 확인 후 단계적 개선',
            })

        # 5) 순위 추이
        latest_rank = rank_trend.get('latest_rank')
        trend_dir = rank_trend.get('trend_direction', 'unknown')

        if latest_rank and latest_rank <= 3:
            issues.append({
                'issue': f'순위 TOP3 유지 (현재 {latest_rank}위)',
                'severity': 'info',
                'detail': f'네이버 순위 {latest_rank}위 — 트렌드: {trend_dir}',
                'action': '현재 트래픽 작업 유지, 순위 하락 모니터링',
            })
        elif latest_rank and latest_rank <= 10:
            issues.append({
                'issue': f'순위 TOP10 진입 (현재 {latest_rank}위)',
                'severity': 'info',
                'detail': f'네이버 순위 {latest_rank}위 — 트렌드: {trend_dir}',
                'action': '상위 3위 진입 목표로 CPC 집중',
            })
        elif latest_rank and latest_rank > 10:
            issues.append({
                'issue': f'순위 하위권 (현재 {latest_rank}위)',
                'severity': 'warning',
                'detail': f'네이버 순위 {latest_rank}위 — 트렌드: {trend_dir}',
                'action': '트래픽 캠페인 강화 — 10위 이내 진입 목표',
            })
        elif trend_dir == 'not_ranked' and rank_trend:
            issues.append({
                'issue': '헬프스토어 순위 추적 데이터 없음',
                'severity': 'warning',
                'detail': '헬프스토어 상품 등록 미완료 또는 ranking_id 미설정',
                'action': '헬프스토어에 상품 등록 후 ranking_id를 config.py에 추가',
            })

        # 6) 전환율
        cvr = traffic.get('overall_conversion_rate', 0)
        if traffic and cvr > 0:
            if cvr < 0.5:
                issues.append({
                    'issue': f'전환율 낮음 ({cvr:.1f}%)',
                    'severity': 'warning',
                    'detail': f'방문 {traffic.get("total_visits", 0):,}건 → 결제 {traffic.get("total_orders", 0):,}건 (전환율 {cvr:.1f}%)',
                    'action': '상세페이지 개선 / 대표 이미지 A/B 테스트 / 가격 재검토',
                })
            elif cvr >= 2.0:
                issues.append({
                    'issue': f'전환율 양호 ({cvr:.1f}%)',
                    'severity': 'info',
                    'detail': f'방문 {traffic.get("total_visits", 0):,}건 → 결제 {traffic.get("total_orders", 0):,}건',
                    'action': '전환율 유지하며 유입량 확대 집중',
                })

        # 7) 광고 비율
        ad_ratio = market_summary.get('ad_ratio', 0)
        if ad_ratio >= 50:
            issues.append({
                'issue': f'광고 상품 비율 높음 ({ad_ratio}%)',
                'severity': 'info',
                'detail': f'상위 결과 중 {ad_ratio}%가 광고 상품 — 오가닉 경쟁 완화 가능성',
                'action': 'CPC 광고 집행 시 오가닉 대비 ROAS 비교 후 믹스 결정',
            })

        return issues

    # ------------------------------------------------------------------
    # 우선순위 점수
    # ------------------------------------------------------------------

    def _calc_priority_score(
        self,
        price_analysis: dict,
        review_analysis: dict,
        rank_trend: dict,
        traffic: dict,
        our_product: Optional[dict],
    ) -> float:
        score = 50.0

        price_verdict = price_analysis.get('verdict', 'unknown')
        if price_verdict == '우위':
            score += 20
        elif price_verdict == '적정':
            score += 10
        elif price_verdict == '열세':
            score -= 15
        elif price_verdict == '심각':
            score -= 30

        review_verdict = review_analysis.get('verdict', 'unknown')
        if review_verdict == '우위':
            score += 10
        elif review_verdict == '열세':
            score -= 5
        elif review_verdict == '심각':
            score -= 15

        latest_rank = rank_trend.get('latest_rank')
        trend_dir = rank_trend.get('trend_direction', 'unknown')

        if latest_rank is None and rank_trend:
            score += 5
        elif latest_rank:
            if latest_rank <= 3:
                score += 15
            elif latest_rank <= 10:
                score += 10
            elif latest_rank <= 20:
                score += 0
            else:
                score -= 10

        if trend_dir == 'improving':
            score += 5
        elif trend_dir == 'declining':
            score -= 10

        if not our_product:
            score -= 20

        cvr = traffic.get('overall_conversion_rate', 0)
        if cvr >= 2.0:
            score += 10
        elif cvr >= 1.0:
            score += 5
        elif 0 < cvr < 0.5:
            score -= 10

        score = max(0.0, min(100.0, score))
        return round(score, 1)

    # ------------------------------------------------------------------
    # 추천 액션
    # ------------------------------------------------------------------

    def _build_recommendations(self, diagnosis: list[dict]) -> list[str]:
        critical = [d['action'] for d in diagnosis if d.get('severity') == 'critical']
        warning = [d['action'] for d in diagnosis if d.get('severity') == 'warning']
        info = [d['action'] for d in diagnosis if d.get('severity') == 'info']

        recommendations: list[str] = []
        for action in critical:
            recommendations.append(f'[긴급] {action}')
        for action in warning:
            recommendations.append(f'[권고] {action}')
        for action in info:
            recommendations.append(f'[참고] {action}')

        return recommendations
