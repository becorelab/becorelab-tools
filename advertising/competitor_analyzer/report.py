"""분석 결과를 마크다운 보고서로 변환하여 옵시디언 볼트에 저장"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from competitor_analyzer.config import REPORT_DIR

logger = logging.getLogger(__name__)

_VERDICT_EMOJI = {
    '우위': '✅',
    '적정': '⚡',
    '열세': '⚠️',
    '심각': '🚨',
}

_SEVERITY_EMOJI = {
    'critical': '🚨',
    'warning': '⚠️',
    'info': 'ℹ️',
}


class ReportGenerator:
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or REPORT_DIR

    def generate(self, analysis: dict) -> str:
        product = analysis.get('product', '')
        analyzed_at = analysis.get('analyzed_at', datetime.now().isoformat())
        priority_score = analysis.get('priority_score', 0.0)

        date_str = analyzed_at[:10] if len(analyzed_at) >= 10 else analyzed_at

        sections = [
            self._frontmatter(product, date_str, priority_score),
            f'# {product} 경쟁 분석 리포트\n',
            f'> 분석일: {date_str} | 우선순위 점수: {priority_score:.1f}/100\n',
            self._market_summary(analysis.get('market_summary', {})),
            self._price_analysis(analysis.get('price_analysis', {})),
            self._review_analysis(analysis.get('review_analysis', {})),
            self._mall_grade_analysis(analysis.get('mall_grade_analysis', {})),
        ]

        our_brand = analysis.get('our_brand_products', [])
        if our_brand:
            sections.append(self._our_brand_section(our_brand, analysis.get('our_product', {})))

        multi_kw = analysis.get('multi_keyword_summary')
        if multi_kw:
            sections.append(self._multi_keyword_summary(multi_kw))

        keyword_analysis = analysis.get('keyword_analysis')
        if keyword_analysis:
            sections.append(self._keyword_analysis(keyword_analysis))

        ranking_trend = analysis.get('ranking_trend')
        if ranking_trend:
            sections.append(self._ranking_trend(ranking_trend))

        traffic_analysis = analysis.get('traffic_analysis')
        if traffic_analysis:
            sections.append(self._traffic_analysis(traffic_analysis))

        competitors = analysis.get('competitors_table', [])
        if competitors:
            sections.append(self._competitors_table(competitors, analysis.get('product', '')))

        sections.append(self._diagnosis(analysis.get('diagnosis', [])))
        sections.append(self._recommendations(analysis.get('recommendations', [])))

        return '\n'.join(sections)

    def save(self, analysis: dict) -> Path:
        product = analysis.get('product', 'unknown')
        analyzed_at = analysis.get('analyzed_at', datetime.now().isoformat())
        date_str = analyzed_at[:10] if len(analyzed_at) >= 10 else analyzed_at

        product_dir = self.output_dir / product
        product_dir.mkdir(parents=True, exist_ok=True)

        filename = f'{date_str} {product} 경쟁분석.md'
        filepath = product_dir / filename

        content = self.generate(analysis)
        filepath.write_text(content, encoding='utf-8')

        logger.info('보고서 저장 완료: %s', filepath)
        return filepath

    def _frontmatter(self, product: str, date_str: str, priority_score: float) -> str:
        return (
            f'---\n'
            f'tags: [경쟁분석, {product}]\n'
            f'date: {date_str}\n'
            f'priority_score: {priority_score:.1f}\n'
            f'---\n'
        )

    def _market_summary(self, summary: dict) -> str:
        if not summary:
            return '## 📊 시장 현황\n\n데이터 없음\n'

        total = summary.get('total_count', 0)
        ad = summary.get('ad_count', 0)
        avg_price = summary.get('avg_price', 0)
        min_price = summary.get('min_price', 0)
        max_price = summary.get('max_price', 0)
        avg_reviews = summary.get('avg_review_count', 0)
        grade_dist = summary.get('grade_distribution', {})

        grade_str = ', '.join(f'{k} {v}개' for k, v in grade_dist.items()) if grade_dist else '-'

        avg_purchases = summary.get('avg_purchase_count', 0)
        total_revenue = summary.get('total_estimated_revenue', 0)
        products_with_sales = summary.get('products_with_sales', 0)

        lines = [
            '## 📊 시장 현황\n',
            '| 항목 | 값 |',
            '|------|-----|',
            f'| 경쟁 상품수 | {total}개 (광고 {ad}개 포함) |',
            f'| 평균 가격 | ₩{avg_price:,} |',
            f'| 가격 범위 | ₩{min_price:,} ~ ₩{max_price:,} |',
            f'| 평균 리뷰 | {avg_reviews:,}개 |',
            f'| 평균 구매건수 | {avg_purchases:,}건 ({products_with_sales}개 상품 기준) |',
            f'| 시장 추정 매출합 | ₩{total_revenue:,} |',
            f'| 몰등급 분포 | {grade_str} |',
            '',
        ]
        return '\n'.join(lines)

    def _price_analysis(self, price: dict) -> str:
        if not price:
            return '## 🏷️ 가격 포지션\n\n데이터 없음\n'

        verdict = price.get('verdict', '')
        emoji = _VERDICT_EMOJI.get(verdict, '')
        our_price = price.get('our_price') or 0
        comp_avg = price.get('avg_price', 0)
        comp_median = price.get('median_price', 0)
        percentile = price.get('percentile') or 0.0

        lines = [
            f'## 🏷️ 가격 포지션\n',
            f'{emoji} **{verdict}** (상위 {percentile:.0f}%)\n',
            '| 항목 | 가격 |',
            '|------|------|',
            f'| 우리 가격 | ₩{our_price:,} |',
            f'| 경쟁사 평균 | ₩{comp_avg:,} |',
            f'| 경쟁사 중앙값 | ₩{comp_median:,} |',
            '',
        ]
        return '\n'.join(lines)

    def _review_analysis(self, review: dict) -> str:
        if not review:
            return '## 📝 리뷰 경쟁력\n\n데이터 없음\n'

        verdict = review.get('verdict', '')
        emoji = _VERDICT_EMOJI.get(verdict, '')
        our_reviews = review.get('our_review_count') or 0
        comp_avg = review.get('avg_review_count', 0)
        comp_max = review.get('max_review_count', 0)
        percentile = review.get('percentile') or 0.0

        lines = [
            f'## 📝 리뷰 경쟁력\n',
            f'{emoji} **{verdict}** (상위 {percentile:.0f}%)\n',
            '| 항목 | 리뷰수 |',
            '|------|--------|',
            f'| 우리 리뷰 | {our_reviews:,}개 |',
            f'| 경쟁사 평균 | {comp_avg:,}개 |',
            f'| 경쟁사 최대 | {comp_max:,}개 |',
            '',
        ]
        return '\n'.join(lines)

    def _mall_grade_analysis(self, grade: dict) -> str:
        if not grade:
            return '## 🏪 몰등급\n\n데이터 없음\n'

        our_grade = grade.get('our_grade', '-') or '-'
        top5 = grade.get('top5_grades', [])
        top5_str = ', '.join(g or '없음' for g in top5) if top5 else '-'
        impact = grade.get('conversion_impact', '')

        lines = [
            '## 🏪 몰등급\n',
            f'- 우리 등급: **{our_grade}**',
            f'- 상위 5개 몰 등급: {top5_str}',
            f'- 전환 영향: {impact}' if impact else '',
            '',
        ]
        return '\n'.join(lines)

    def _our_brand_section(self, our_brand: list, our_product: dict) -> str:
        if not our_brand:
            return ''

        from_search = not our_product.get('_from_brand_search', False) if our_product else False
        status = '검색 순위 내 노출' if from_search and our_product else '검색 순위 밖 (브랜드 검색으로 확인)'

        lines = [
            '## 🏠 우리 상품 현황\n',
            f'> {status}\n',
            '| 상품명 | 가격 | 리뷰 | 구매건수 | 찜 | 추정매출 |',
            '|--------|------|------|---------|-----|---------|',
        ]

        total_reviews = 0
        total_purchases = 0
        total_revenue = 0

        for p in our_brand:
            name = p.get('product_name', '')
            if len(name) > 35:
                name = name[:33] + '..'
            price = p.get('price', 0)
            reviews = p.get('review_count', 0)
            purchases = p.get('purchase_count', 0)
            zzim = p.get('zzim_count', 0)
            revenue = p.get('estimated_revenue', 0)

            total_reviews += reviews
            total_purchases += purchases
            total_revenue += revenue

            lines.append(
                f'| {name} | ₩{price:,} | {reviews:,} | {purchases:,} | {zzim:,} | ₩{revenue:,} |'
            )

        lines.append(f'| **합계** | - | **{total_reviews:,}** | **{total_purchases:,}** | - | **₩{total_revenue:,}** |')
        lines.append('')
        return '\n'.join(lines)

    def _multi_keyword_summary(self, multi: dict) -> str:
        if not multi:
            return ''

        total_kw = multi.get('total_keywords_searched', 0)
        before_dedup = multi.get('total_before_dedup', 0)
        unique = multi.get('total_unique_products', 0)
        total_rev = multi.get('total_estimated_revenue', 0)
        avg_price = multi.get('avg_price', 0)
        avg_purchases = multi.get('avg_purchase_count', 0)
        with_sales = multi.get('products_with_sales', 0)

        lines = [
            '## 🌐 멀티 키워드 시장 규모\n',
            f'> {total_kw}개 키워드 검색 → 중복 제거 전 {before_dedup}개 → **고유 상품 {unique}개**\n',
            '| 항목 | 값 |',
            '|------|-----|',
            f'| 고유 상품수 | {unique}개 |',
            f'| 평균 가격 | ₩{avg_price:,} |',
            f'| 평균 구매건수 | {avg_purchases:,}건 ({with_sales}개 상품 기준) |',
            f'| **통합 추정 매출** | **₩{total_rev:,}** |',
            '',
        ]

        kw_breakdown = multi.get('keyword_breakdown', [])
        if kw_breakdown:
            lines.append('### 키워드별 수집 현황\n')
            lines.append('| 키워드 | 상품수 | 광고수 |')
            lines.append('|--------|--------|--------|')
            for kb in kw_breakdown:
                lines.append(f'| {kb["keyword"]} | {kb["products_found"]} | {kb["ads"]} |')
            lines.append('')

        top_sellers = multi.get('top_sellers', [])
        if top_sellers:
            lines.append('### 💰 통합 매출 TOP10\n')
            lines.append('| # | 상품명 | 판매자 | 가격 | 구매건수 | 추정매출 | 발견 키워드 |')
            lines.append('|---|--------|--------|------|---------|---------|------------|')
            for i, p in enumerate(top_sellers, 1):
                name = p.get('product_name', '')[:25]
                mall = p.get('mall_name', '')
                price = p.get('price', 0)
                pc = p.get('purchase_count', 0)
                rev = p.get('estimated_revenue', 0)
                kws = ', '.join(p.get('found_keywords', [])[:3])
                lines.append(f'| {i} | {name} | {mall} | ₩{price:,} | {pc:,} | ₩{rev:,} | {kws} |')
            lines.append('')

        return '\n'.join(lines)

    def _keyword_analysis(self, keyword: dict) -> str:
        if not keyword:
            return ''

        kw = keyword.get('keyword', '')
        total_search = keyword.get('total_search', 0)
        product_count = keyword.get('product_count', 0)
        competition = keyword.get('competition', '-')
        related_top5 = keyword.get('related_keywords_top5', [])

        related_str = '-'
        if related_top5 and isinstance(related_top5, list):
            kw_names = []
            for item in related_top5:
                if isinstance(item, dict):
                    kw_names.append(item.get('keyword', item.get('relKeyword', str(item))))
                else:
                    kw_names.append(str(item))
            related_str = ', '.join(kw_names) if kw_names else '-'

        lines = [
            '## 🔍 키워드 분석\n',
            '| 항목 | 값 |',
            '|------|-----|',
            f'| 대표 키워드 | {kw} |',
            f'| 월 검색량 | {total_search:,} |',
            f'| 상품수 | {product_count:,} |',
            f'| 경쟁도 | {competition} |',
            f'| 연관 키워드 | {related_str} |',
            '',
        ]
        return '\n'.join(lines)

    def _ranking_trend(self, ranking: dict) -> str:
        if not ranking:
            return ''

        keywords = ranking.get('keywords', [])
        if not keywords:
            return '## 📈 순위 추이\n\n데이터 없음\n'

        best_rank = ranking.get('best_rank')
        latest_rank = ranking.get('latest_rank')
        trend = ranking.get('trend_direction', 'unknown')

        trend_emoji = {'improving': '📈', 'declining': '📉', 'stable': '➡️'}.get(trend, '❓')

        lines = [
            '## 📈 순위 추이\n',
            f'전체 추세: {trend_emoji} **{trend}** | 최고 순위: {best_rank or "-"}위 | 최신 순위: {latest_rank or "-"}위\n',
            '| 키워드 | 최신 순위 | 최고 순위 | 추세 |',
            '|--------|----------|----------|------|',
        ]

        for kw_data in keywords[:10]:
            kw_name = kw_data.get('keyword', '')
            lr = kw_data.get('latest_rank')
            br = kw_data.get('best_rank')
            t = kw_data.get('trend', 'same')
            t_icon = {'up': '▲', 'down': '▼', 'same': '-'}.get(t, '-')
            lines.append(f'| {kw_name} | {lr or "-"}위 | {br or "-"}위 | {t_icon} |')

        lines.append('')
        return '\n'.join(lines)

    def _traffic_analysis(self, traffic: dict) -> str:
        if not traffic:
            return ''

        total_visits = traffic.get('total_visits', 0)
        total_orders = traffic.get('total_orders', 0)
        total_revenue = traffic.get('total_revenue', 0)
        cvr = traffic.get('overall_conversion_rate', 0.0)
        top_keywords = traffic.get('top_keywords', [])

        lines = [
            '## 🔄 유입/전환\n',
            '| 항목 | 값 |',
            '|------|-----|',
            f'| 총 방문수 | {total_visits:,} |',
            f'| 총 결제건수 | {total_orders:,} |',
            f'| 총 결제금액 | ₩{total_revenue:,} |',
            f'| 전환율 | {cvr:.1f}% |',
            '',
        ]

        if top_keywords:
            lines.append('### 상위 유입 키워드\n')
            lines.append('| 키워드 | 방문수 | 결제건수 | 전환율 |')
            lines.append('|--------|--------|----------|--------|')
            for item in top_keywords:
                kw = item.get('keyword', '-')
                visits = item.get('visits', 0)
                orders = item.get('orders', 0)
                conv = item.get('conversion_rate', 0.0)
                lines.append(f'| {kw} | {visits:,} | {orders:,} | {conv:.1f}% |')
            lines.append('')

        return '\n'.join(lines)

    def _competitors_table(self, competitors: list, product: str) -> str:
        if not competitors:
            return ''

        lines = [
            f'## 🛒 판매 상품 목록 ({len(competitors)}개)\n',
            '| 순위 | 상품명 | 판매자 | 등급 | 가격 | 구매건수 | 추정매출 | 리뷰 | 찜 | 광고 | 링크 |',
            '|------|--------|--------|------|------|---------|---------|------|-----|------|------|',
        ]

        for p in competitors:
            rank = p.get('rank', '-')
            name = p.get('product_name', '')
            if len(name) > 30:
                name = name[:28] + '..'
            mall = p.get('mall_name', '')
            grade = p.get('mall_grade', '') or '-'
            price = p.get('price', 0)
            purchase = p.get('purchase_count', 0)
            revenue = p.get('estimated_revenue', 0)
            reviews = p.get('review_count', 0)
            zzim = p.get('zzim_count', 0)
            is_ad = '광고' if p.get('is_ad') else '-'
            url = p.get('url', '')
            link = f'[보기]({url})' if url else '-'

            purchase_str = f'{purchase:,}' if purchase else '-'
            revenue_str = f'₩{revenue:,}' if revenue else '-'

            is_ours = any(n.lower() in mall.lower() for n in ['일비아', 'ILBIA', 'ilbia', '비코어랩'])
            prefix = '**' if is_ours else ''
            suffix = '**' if is_ours else ''

            lines.append(
                f'| {prefix}{rank}{suffix} '
                f'| {prefix}{name}{suffix} '
                f'| {prefix}{mall}{suffix} '
                f'| {grade} '
                f'| {prefix}₩{price:,}{suffix} '
                f'| {purchase_str} '
                f'| {revenue_str} '
                f'| {reviews:,} '
                f'| {zzim:,} '
                f'| {is_ad} '
                f'| {link} |'
            )

        # 매출 TOP5 요약
        with_revenue = [p for p in competitors if p.get('estimated_revenue', 0) > 0]
        if with_revenue:
            top5 = sorted(with_revenue, key=lambda x: x.get('estimated_revenue', 0), reverse=True)[:5]
            lines.append('')
            lines.append('### 💰 추정 매출 TOP5\n')
            lines.append('| 순위 | 상품명 | 판매자 | 구매건수 | 추정매출 |')
            lines.append('|------|--------|--------|---------|---------|')
            for i, p in enumerate(top5, 1):
                name = p.get('product_name', '')[:25]
                mall = p.get('mall_name', '')
                pc = p.get('purchase_count', 0)
                rev = p.get('estimated_revenue', 0)
                lines.append(f'| {i} | {name} | {mall} | {pc:,} | ₩{rev:,} |')

        lines.append('')
        return '\n'.join(lines)

    def _diagnosis(self, diagnosis: list) -> str:
        if not diagnosis:
            return '## 🩺 진단 결과\n\n진단 항목 없음\n'

        lines = ['## 🩺 진단 결과\n']

        for item in diagnosis:
            severity = item.get('severity', 'info')
            emoji = _SEVERITY_EMOJI.get(severity, 'ℹ️')
            issue = item.get('issue', '')
            detail = item.get('detail', '')
            action = item.get('action', '')

            lines.append(f'### {emoji} {issue}\n')
            if detail:
                lines.append(f'{detail}\n')
            if action:
                lines.append(f'**액션**: {action}\n')

        return '\n'.join(lines)

    def _recommendations(self, recommendations: list) -> str:
        if not recommendations:
            return '## 💡 액션 아이템\n\n추천 항목 없음\n'

        lines = ['## 💡 액션 아이템\n']
        for i, rec in enumerate(recommendations, 1):
            lines.append(f'{i}. {rec}')
        lines.append('')
        return '\n'.join(lines)
