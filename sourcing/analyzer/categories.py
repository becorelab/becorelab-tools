"""
쿠팡 카테고리 데이터 (435개 실제 카테고리)
- 쿠팡 공식 카테고리 구조 기반
- 소규모 브랜드 진입 가능한 카테고리 필터링 옵션
"""

import json
import os

_CATEGORIES_FILE = os.path.join(os.path.dirname(__file__), 'coupang_categories.json')

def _load():
    with open(_CATEGORIES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# 제외 카테고리 없음 (전부 오픈)
SKIP_CATEGORIES = set()

CATEGORY_SEEDS = _load()


def get_all_categories() -> dict:
    """전체 카테고리 반환"""
    return CATEGORY_SEEDS


def get_explorable_categories() -> dict:
    """소규모 브랜드 진입 가능한 카테고리만"""
    return {k: v for k, v in CATEGORY_SEEDS.items() if k not in SKIP_CATEGORIES}


def get_category_names() -> list:
    return list(CATEGORY_SEEDS.keys())


def get_seeds_by_category(category: str) -> list:
    return CATEGORY_SEEDS.get(category, [])


def get_all_seeds() -> list:
    """전체 시드 (카테고리 정보 포함)"""
    result = []
    for cat, keywords in CATEGORY_SEEDS.items():
        for kw in keywords:
            result.append({'keyword': kw, 'category': cat})
    return result
