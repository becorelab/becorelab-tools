"""경쟁사 분석 파이프라인 진입점"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from competitor_analyzer.config import PRODUCTS, REPORT_DIR, OUR_BRAND, OUR_MALL_NAMES
from competitor_analyzer.collectors.helpstore import HelpstoreCollector
from competitor_analyzer.collectors.naver_shopping import NaverShoppingCollector
from competitor_analyzer.analyzer import CompetitorAnalyzer
from competitor_analyzer.report import ReportGenerator
from competitor_analyzer import storage as competitor_storage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


async def run_pipeline(
    product_key: str,
    save_json: bool = False,
    with_smartstore: bool = False,
    report_only: bool = False,
) -> dict:
    product_config = PRODUCTS[product_key]
    date_str = datetime.now().strftime('%Y-%m-%d')

    naver_results = []
    multi_keyword_data = None
    keyword_analysis = None
    ranking_data = None
    smartstore_data = None
    our_brand_data = None

    if not report_only:
        naver = NaverShoppingCollector()

        # 멀티 키워드 검색 → 중복 제거된 전체 시장 데이터
        all_keywords = product_config['keywords']
        logger.info('[%s] 멀티 키워드 검색 시작 (%d개 키워드)', product_key, len(all_keywords))
        multi_keyword_data = naver.search_multi(all_keywords, count_per_kw=40)
        logger.info('[%s] 멀티 키워드: %d개 수집 → 중복 제거 %d개',
                    product_key, multi_keyword_data['total_before_dedup'], multi_keyword_data['total_unique'])

        # 대표 키워드 결과는 첫 번째 키워드 검색 결과 사용 (순위/보고서용)
        naver_results = naver.search(all_keywords[0], count=40)
        logger.info('[%s] 대표 키워드 "%s": %d개', product_key, all_keywords[0], len(naver_results))

        # 우리 브랜드 상품 별도 검색 (순위 밖이어도 리뷰/구매 데이터 확보)
        our_brand_data = naver.search_our_brand(all_keywords[0])
        logger.info('[%s] 우리 브랜드 상품: %d개', product_key, len(our_brand_data))

        ranking_id = product_config.get('ranking_id')
        if ranking_id:
            helpstore = HelpstoreCollector()
            logger.info('[%s] 헬프스토어 키워드 분석 시작', product_key)
            keyword_analysis = helpstore.get_keyword_analysis(product_config['keywords'][0])
            ranking_data = helpstore.get_ranking_data(ranking_id)
            logger.info('[%s] 헬프스토어 수집 완료', product_key)

        if with_smartstore:
            from competitor_analyzer.collectors.smartstore import SmartstoreCollector
            logger.info('[%s] 스마트스토어 셀러센터 수집 시작', product_key)
            collector = SmartstoreCollector(headless=True)
            await collector.init()
            try:
                ok = await collector.login()
                if ok:
                    smartstore_data = await collector.get_keyword_traffic(days=14)
                    logger.info('[%s] 스마트스토어 %d건 수집 완료', product_key, len(smartstore_data or []))
                else:
                    logger.warning('[%s] 스마트스토어 로그인 실패 — 건너뜀', product_key)
            finally:
                await collector.close()

    analyzer = CompetitorAnalyzer()
    analysis = analyzer.analyze(product_key, naver_results, keyword_analysis, ranking_data, smartstore_data, multi_keyword_data, our_brand_data)

    reporter = ReportGenerator()
    report_path = reporter.save(analysis)
    logger.info('[%s] 보고서 저장: %s', product_key, report_path)

    # ── Firebase 저장 (실패해도 파이프라인 계속 진행) ──────────────────────
    try:
        doc_id = competitor_storage.save_analysis(analysis)
        if doc_id:
            logger.info('[%s] Firebase 저장 완료: %s', product_key, doc_id)
        else:
            logger.warning('[%s] Firebase 저장 건너뜀 (키 파일 없음 또는 연결 불가)', product_key)
    except Exception as e:
        logger.error('[%s] Firebase 저장 실패 (파이프라인 계속): %s', product_key, e)

    if save_json:
        json_path = Path(f'/tmp/competitor_{product_key}_{date_str}.json')
        json_path.write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2, default=str),
            encoding='utf-8',
        )
        logger.info('[%s] JSON 저장: %s', product_key, json_path)

    return analysis


def print_summary(product_key: str, analysis: dict):
    priority = analysis.get('priority_score', 0.0)
    diagnosis = analysis.get('diagnosis', [])
    critical = [d for d in diagnosis if d.get('severity') == 'critical']
    warnings = [d for d in diagnosis if d.get('severity') == 'warning']

    print(f'\n{"="*50}')
    print(f'  {product_key}')
    print(f'  우선순위 점수: {priority:.1f}/100')
    if critical:
        print(f'  🚨 Critical: {", ".join(d["issue"] for d in critical)}')
    if warnings:
        print(f'  ⚠️  Warning : {", ".join(d["issue"] for d in warnings)}')
    if not critical and not warnings:
        print('  ✅ 특이사항 없음')
    print(f'{"="*50}')


async def main():
    parser = argparse.ArgumentParser(description='비코어랩 경쟁사 분석 파이프라인')
    parser.add_argument('--product', type=str, help='특정 제품만 분석 (예: 식세기세제)')
    parser.add_argument('--report-only', action='store_true', help='이전 수집 데이터로 리포트만 생성')
    parser.add_argument('--save-json', action='store_true', help='JSON 결과 /tmp에 저장')
    parser.add_argument('--with-smartstore', action='store_true', help='스마트스토어 셀러센터 데이터 포함')
    args = parser.parse_args()

    if args.product:
        if args.product not in PRODUCTS:
            print(f'오류: 제품 키 "{args.product}"를 찾을 수 없습니다.')
            print(f'사용 가능: {", ".join(PRODUCTS.keys())}')
            return

        product_keys = [args.product]
    else:
        product_keys = list(PRODUCTS.keys())

    results = {}
    errors = []

    for i, product_key in enumerate(product_keys):
        if i > 0 and not args.report_only:
            time.sleep(1)

        try:
            analysis = await run_pipeline(
                product_key,
                save_json=args.save_json,
                with_smartstore=args.with_smartstore,
                report_only=args.report_only,
            )
            results[product_key] = analysis
            print_summary(product_key, analysis)
        except Exception as e:
            logger.error('[%s] 파이프라인 오류: %s', product_key, e)
            errors.append((product_key, str(e)))

    print(f'\n완료: {len(results)}개 성공', end='')
    if errors:
        print(f', {len(errors)}개 실패')
        for product_key, err in errors:
            print(f'  - {product_key}: {err}')
    else:
        print()


if __name__ == '__main__':
    asyncio.run(main())
