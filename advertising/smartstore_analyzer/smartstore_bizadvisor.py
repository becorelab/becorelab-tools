#!/usr/bin/env python3
"""
네이버 스마트스토어 셀러센터 비즈어드바이저 데이터 수집기
마케팅분석 + 매출분석(판매분석) 페이지 자동 수집

사용법:
    python3 smartstore_bizadvisor.py
    python3 smartstore_bizadvisor.py --start 2026-04-01 --end 2026-04-25

구조:
    - accounts.commerce.naver.com 로그인 (이메일/판매자 아이디 방식)
    - biz_iframe API (NSI 쿠키 + NEONB 쿠키 기반 인증)
    - 사이트ID: s_321cd73103c6f (ILBIA 통합 매니저)
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# ── 설정 ──────────────────────────────────────────────────────────────────────
SMARTSTORE_ID = "info@becorelab.kr"
SMARTSTORE_PW = "becolab@2024"
SITE_ID = "s_321cd73103c6f"  # ILBIA 통합 매니저

# API 베이스
BIZ_API_BASE = f"https://sell.smartstore.naver.com/biz_iframe/api/v3/sites/{SITE_ID}/report"
BIZ_API_V2 = f"https://sell.smartstore.naver.com/biz_iframe/api/v2/sites/{SITE_ID}/pivot"

# ── 탭 구조 ───────────────────────────────────────────────────────────────────
MARKETING_TABS = [
    "전체채널",
    "검색채널",
    "웹사이트채널",
    "사용자정의채널",
    "인구통계",
    "시간대별",
    "상품노출성과",
]

SALES_TABS = [
    "판매성과",
    "상품성과",
    "상품/마케팅채널",
    "상품/검색채널",
    "상품/인구통계",
    "상품/고객프로파일",
    "상품/지역",
    "배송통계",
]

# ── API 정의 ──────────────────────────────────────────────────────────────────
# use_index: 페이지 탭별 API 인덱스 매핑
# dimensions: 분류 기준 (채널, 날짜, 키워드 등)
# metrics: 측정 지표 (방문, 구매, 매출 등)

MARKETING_APIS = {
    # 마케팅분석 > 전체채널
    "revenue-all-channel-detail": {
        "tab": "전체채널",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "revenue-all-channel-detail",
            "dimensions": "mapped_channel_name",   # 또는 device_category, ref_channel
            "metrics": [
                "num_interaction",     # 방문수
                "pv",                  # 페이지뷰
                "num_purchase",        # 구매수
                "pay_amount",          # 결제금액
                "attribution_num_purchase",   # 기여 구매수
                "attribution_pay_amount",     # 기여 결제금액
                "pv_by_num_interaction",      # 방문당 PV
                "purchase_rate_by_interaction",        # 구매전환율
                "pay_amount_by_interaction",           # 방문당 결제금액
                "attribution_pay_amount",              # 기여 ROAS용
                "cost",                               # 광고비용
                "attribution_roas",                   # ROAS
            ],
            "service": "biz_advisor",
        },
        "description": "채널별(마케팅채널, 검색, SNS 등) 유입/전환/매출 성과",
    },
    # 마케팅분석 > 검색채널
    "revenue-search-channel-detail": {
        "tab": "검색채널",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "revenue-search-channel-detail",
            "dimensions": "ref_keyword",   # 검색 키워드별
            "metrics": [
                "num_interaction",
                "pv",
                "num_purchase",
                "pay_amount",
                "attribution_num_purchase",
                "attribution_pay_amount",
                "pv_by_num_interaction",
                "purchase_rate_by_interaction",
                "pay_amount_by_interaction",
                "attribution_purchase_rate_by_interaction",
                "attribution_pay_amount_by_interaction",
                "simple_num_users",
                "detail_num_users",
            ],
            "service": "biz_advisor",
            "size": "1000",  # 최대 1000개 키워드
            "sort": "num_interaction",
            "order": "desc",
        },
        "description": "검색 키워드별 유입/전환/매출 성과 (가장 중요한 탭)",
    },
    # 마케팅분석 > 웹사이트채널
    "revenue-website-channel-detail": {
        "tab": "웹사이트채널",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "revenue-website-channel-detail",
            "metrics": [
                "num_interaction", "pv", "num_purchase", "pay_amount",
                "attribution_num_purchase", "attribution_pay_amount",
                "pv_by_num_interaction", "purchase_rate_by_interaction",
                "pay_amount_by_interaction", "attribution_purchase_rate_by_interaction",
                "attribution_pay_amount_by_interaction", "simple_num_users", "detail_num_users",
            ],
            "service": "biz_advisor",
        },
        "description": "외부 웹사이트(블로그, 카페 등) 유입 성과",
    },
    # 마케팅분석 > 인구통계
    "revenue-user-detail": {
        "tab": "인구통계",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "revenue-user-detail",
            "dimensions": ["gender", "age_bucket_all"],  # 성별+연령대
            "metrics": [
                "num_interaction", "num_purchase", "pay_amount",
                "attribution_num_purchase", "attribution_pay_amount",
                "pv_by_num_interaction", "purchase_rate_by_interaction",
                "pay_amount_by_interaction", "attribution_purchase_rate_by_interaction",
                "attribution_pay_amount_by_interaction", "simple_num_users",
            ],
            "service": "biz_advisor",
        },
        "description": "방문자 성별/연령대별 구매 성과",
    },
    # 마케팅분석 > 시간대별
    "revenue-hour-detail": {
        "tab": "시간대별",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "revenue-hour-detail",
            "dimensions": "hour",    # 0~23시
            "metrics": [
                "num_interaction", "pv", "num_purchase", "pay_amount",
                "attribution_num_purchase", "attribution_pay_amount",
                "pv_by_num_interaction", "purchase_rate_by_interaction",
                "pay_amount_by_interaction", "attribution_purchase_rate_by_interaction",
                "attribution_pay_amount_by_interaction", "simple_num_users",
            ],
            "size": "1000",
            "sort": "simple_num_users",
            "order": "asc",
            "service": "biz_advisor",
        },
        "description": "시간대별(0~23시) 방문/구매 성과",
    },
    # 마케팅분석 > 상품노출성과
    "product-impression": {
        "tab": "상품노출성과",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "product-impression",
            "dimensions": ["product_name", "product_id", "mapped_channel_name", "ref_channel", "ref_keyword"],
            "metrics": ["num_interaction", "avg_impression_rank"],  # 노출수, 평균 노출 순위
            "size": "1000",
            "sort": "num_interaction",
            "order": "desc",
            "service": "biz_advisor",
        },
        "description": "상품별+채널별 노출수 및 평균 노출 순위",
    },
}

SALES_APIS = {
    # 판매분석 > 판매성과
    "sales-product-unit": {
        "tab": "판매성과",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "sales-product-unit",
            "dimensions": "date_time",   # 날짜별
            "metrics": [
                "num_purchase",              # 주문수
                "pay_amount",               # 결제금액
                "pay_amount_on_mobile",     # 모바일 결제금액
                "pay_amount_on_pc",         # PC 결제금액
                "product_quantity",         # 주문 상품수
                "product_quantity_on_mobile",
                "product_quantity_on_pc",
                "refund_pay_amount",        # 환불금액
                "refund_product_quantity",  # 환불 상품수
                "refund_num_purchase",      # 환불 주문수
                "product_coupon_discount_amount",  # 상품쿠폰 할인
                "order_coupon_discount_amount",    # 주문쿠폰 할인
                "product_quantity_refund_rate",    # 상품 환불률
                "pay_amount_refund_rate",          # 금액 환불률
                "sum_of_coupon",                   # 총 쿠폰 할인
                "pay_amount_by_product_quantity",  # 상품당 결제금액
                "pay_amount_mobile_rate",          # 모바일 결제 비율
            ],
            "service": "biz_advisor",
        },
        "description": "날짜별 전체 판매 성과 (매출, 주문수, 환불, 쿠폰 등)",
    },
    # 판매분석 > 상품성과 (상품별 매출)
    "sales-product-unit-by-product": {
        "tab": "상품성과",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "sales-product-unit",
            "dimensions": ["product_name", "product_id"],  # 상품별
            "metrics": [
                "num_purchase", "pay_amount",
                "pay_amount_on_mobile", "pay_amount_on_pc",
                "product_quantity", "refund_pay_amount",
                "refund_product_quantity", "refund_num_purchase",
                "product_coupon_discount_amount", "order_coupon_discount_amount",
                "pay_amount_mobile_rate",
            ],
            "size": "1000",
            "sort": "pay_amount",
            "order": "desc",
            "service": "biz_advisor",
        },
        "description": "상품별 매출/주문수/환불 성과",
    },
    # 판매분석 > 상품/마케팅채널 (귀속 기준)
    "attribution-product-detail": {
        "tab": "상품/마케팅채널",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "attribution-product-detail",
            "dimensions": ["small_category", "mapped_channel_name"],
            "metrics": [
                "attribution_num_purchase_by_payment_date",  # 귀속 구매수
                "attribution_pay_amount_by_payment_date",    # 귀속 결제금액
            ],
            "service": "biz_advisor",
        },
        "description": "상품 카테고리+마케팅채널별 귀속 구매/매출 성과",
    },
    # 판매분석 > 상품/검색채널
    "attribution-product-search-channel-detail": {
        "tab": "상품/검색채널",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "attribution-product-search-channel-detail",
            "dimensions": ["product_name", "ref_keyword"],
            "metrics": [
                "attribution_num_purchase_by_payment_date",
                "attribution_pay_amount_by_payment_date",
            ],
            "size": "1000",
            "sort": "attribution_pay_amount_by_payment_date",
            "order": "desc",
            "service": "biz_advisor",
        },
        "description": "상품별+검색키워드별 귀속 구매/매출 성과",
    },
    # 판매분석 > 배송통계
    "delivery-report": {
        "tab": "배송통계",
        "url_pattern": BIZ_API_BASE,
        "key_params": {
            "useIndex": "delivery-report",
            "dimensions": "date_time",
            "metrics": [
                "dispatched_due_success_ratio",  # 발송기한 준수율
                "avg_delivery_time",             # 평균 배송 시간
                "product_quantity",              # 발송 상품수
            ],
            "service": "biz_advisor",
        },
        "description": "날짜별 배송 성과 (발송기한 준수율, 평균배송시간 등)",
    },
}

# ── 핵심 메트릭 설명 ──────────────────────────────────────────────────────────
METRICS_DESCRIPTION = {
    "num_interaction": "방문수 (세션)",
    "pv": "페이지뷰",
    "simple_num_users": "방문자수 (UV)",
    "detail_num_users": "상세 방문자수",
    "num_purchase": "구매(주문)수",
    "pay_amount": "결제금액",
    "pay_amount_on_mobile": "모바일 결제금액",
    "pay_amount_on_pc": "PC 결제금액",
    "attribution_num_purchase": "기여 구매수 (마케팅 기여 방식)",
    "attribution_pay_amount": "기여 결제금액",
    "attribution_num_purchase_by_payment_date": "귀속 구매수 (결제일 기준)",
    "attribution_pay_amount_by_payment_date": "귀속 결제금액 (결제일 기준)",
    "pv_by_num_interaction": "방문당 PV",
    "purchase_rate_by_interaction": "구매전환율 (방문 기준)",
    "pay_amount_by_interaction": "방문당 결제금액",
    "attribution_purchase_rate_by_interaction": "기여 구매전환율",
    "attribution_pay_amount_by_interaction": "기여 방문당 결제금액",
    "attribution_roas": "ROAS (광고수익률)",
    "cost": "광고 비용",
    "product_quantity": "주문 상품수",
    "refund_pay_amount": "환불금액",
    "refund_product_quantity": "환불 상품수",
    "refund_num_purchase": "환불 주문수",
    "product_coupon_discount_amount": "상품쿠폰 할인금액",
    "order_coupon_discount_amount": "주문쿠폰 할인금액",
    "sum_of_coupon": "총 쿠폰 할인금액",
    "pay_amount_refund_rate": "금액 환불률",
    "product_quantity_refund_rate": "상품 환불률",
    "pay_amount_by_product_quantity": "상품당 평균 결제금액",
    "pay_amount_mobile_rate": "모바일 결제 비율",
    "num_interaction_rate": "채널별 방문 비율",
    "num_interaction_trend_rate": "방문수 증감률",
    "num_purchase_trend_rate": "구매수 증감률",
    "avg_impression_rank": "평균 노출 순위 (낮을수록 상위 노출)",
    "dispatched_due_success_ratio": "발송기한 준수율",
    "avg_delivery_time": "평균 배송 시간 (시간 단위)",
}

# ── 날짜 필터 ─────────────────────────────────────────────────────────────────
# 기간 preset: 화면에서 클릭 가능한 기간 버튼
# 실제로는 startDate/endDate 파라미터로 직접 지정 가능
DATE_PRESETS = {
    "7일": (-7, 0),
    "14일": (-14, 0),
    "30일": (-30, 0),
    "90일": (-90, 0),
    "어제": (-1, -1),
    "오늘": (0, 0),
}


def get_default_date_range():
    """기본 날짜 범위: 최근 14일"""
    today = datetime.now()
    end = today - timedelta(days=1)
    start = end - timedelta(days=13)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def login(page, email, password):
    """셀러센터 로그인"""
    page.goto("https://accounts.commerce.naver.com/login")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    time.sleep(2)

    # 이메일/아이디 입력
    page.locator('input[placeholder*="아이디"]').fill(email)
    time.sleep(0.3)
    page.locator('input[type="password"]').fill(password)
    time.sleep(0.3)

    # 로그인 버튼 클릭 (정확히 "로그인" 텍스트 버튼)
    page.get_by_role("button", name="로그인", exact=True).click()
    time.sleep(10)  # 로그인 처리 대기

    # 로그인 확인
    body_text = page.evaluate("() => document.body.innerText").replace("\n", " ")
    if "로그아웃" in body_text or email in body_text:
        return True
    else:
        return False


def collect_all_data(start_date: str, end_date: str, output_dir: str = "/tmp"):
    """전체 데이터 수집 메인 함수"""
    all_data = {
        "site_id": SITE_ID,
        "start_date": start_date,
        "end_date": end_date,
        "collected_at": datetime.now().isoformat(),
        "marketing": {},
        "sales": {},
    }

    api_responses = {}

    def handle_response(response):
        url = response.url
        if "biz_iframe/api/v3" in url and "report" in url:
            try:
                body = response.json()
                import re
                use_index = re.search(r"useIndex=([^&]+)", url)
                idx = use_index.group(1) if use_index else "unknown"
                if idx not in api_responses:
                    api_responses[idx] = []
                api_responses[idx].append({"url": url, "data": body})
            except Exception:
                pass

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1600, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
        )
        page = context.new_page()
        page.on("response", handle_response)

        # 로그인
        print(f"로그인 중... ({SMARTSTORE_ID})")
        ok = login(page, SMARTSTORE_ID, SMARTSTORE_PW)
        if not ok:
            print("로그인 실패!")
            browser.close()
            return None
        print("로그인 성공!")

        # 마케팅분석 페이지 - 모든 탭 순회
        print("\n[마케팅분석] 데이터 수집 중...")
        page.goto("https://sell.smartstore.naver.com/#/bizadvisor/marketing")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(6)

        tabs = page.query_selector_all('[role="tab"]')
        for tab in tabs:
            tab_text = tab.inner_text().strip()
            print(f"  탭: {tab_text}")
            tab.click()
            time.sleep(4)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            time.sleep(3)

        # 매출분석(판매분석) 페이지 - 모든 탭 순회
        print("\n[판매분석] 데이터 수집 중...")
        page.goto("https://sell.smartstore.naver.com/#/bizadvisor/sales")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(6)

        tabs = page.query_selector_all('[role="tab"]')
        for tab in tabs:
            tab_text = tab.inner_text().strip()
            print(f"  탭: {tab_text}")
            tab.click()
            time.sleep(4)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            time.sleep(3)

        browser.close()

    # 데이터 정리
    for idx, calls in api_responses.items():
        if idx in MARKETING_APIS:
            api_info = MARKETING_APIS[idx]
            all_data["marketing"][idx] = {
                "tab": api_info["tab"],
                "description": api_info["description"],
                "records": calls[-1]["data"] if calls else [],
            }
        elif idx in SALES_APIS or idx + "-by-product" in SALES_APIS:
            api_info = SALES_APIS.get(idx, SALES_APIS.get(idx + "-by-product", {}))
            all_data["sales"][idx] = {
                "tab": api_info.get("tab", idx),
                "description": api_info.get("description", ""),
                "records": calls[-1]["data"] if calls else [],
            }
        else:
            all_data["sales"][idx] = {
                "tab": idx,
                "description": "",
                "records": calls[-1]["data"] if calls else [],
            }

    # 저장
    output_path = os.path.join(output_dir, f"bizadvisor_{start_date}_{end_date}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n데이터 저장: {output_path}")

    return all_data


def print_summary(data: dict):
    """수집 데이터 요약 출력"""
    print("\n" + "=" * 60)
    print(f"수집 완료: {data['start_date']} ~ {data['end_date']}")
    print(f"사이트: {data['site_id']}")

    print("\n[마케팅분석]")
    for idx, info in data.get("marketing", {}).items():
        records = info.get("records", [])
        print(f"  {info['tab']} ({idx}): {len(records)}개 레코드")
        if records and isinstance(records, list) and len(records) > 0:
            first = records[0]
            print(f"    샘플: {json.dumps(first, ensure_ascii=False)[:120]}")

    print("\n[판매분석]")
    for idx, info in data.get("sales", {}).items():
        records = info.get("records", [])
        print(f"  {info['tab']} ({idx}): {len(records)}개 레코드")
        if records and isinstance(records, list) and len(records) > 0:
            first = records[0]
            print(f"    샘플: {json.dumps(first, ensure_ascii=False)[:120]}")


def main():
    parser = argparse.ArgumentParser(description="네이버 스마트스토어 비즈어드바이저 데이터 수집")
    parser.add_argument("--start", help="시작일 (YYYY-MM-DD)", default=None)
    parser.add_argument("--end", help="종료일 (YYYY-MM-DD)", default=None)
    parser.add_argument("--output", help="저장 디렉토리", default="/tmp")
    args = parser.parse_args()

    start_date, end_date = get_default_date_range()
    if args.start:
        start_date = args.start
    if args.end:
        end_date = args.end

    print(f"수집 기간: {start_date} ~ {end_date}")

    data = collect_all_data(start_date, end_date, args.output)
    if data:
        print_summary(data)


if __name__ == "__main__":
    main()
