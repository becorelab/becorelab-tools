"""
헬프스토어 두 페이지 구조 분석 스크립트
1. 네이버 키워드 분석: /keyword/keyword_analyze/식기세척기 세제
2. 키워드 순위 추적: /fast/ranking/45522
"""

import requests
import json
import re
from urllib.parse import urljoin

BASE = 'https://helpstore.shop'
LOGIN_DATA = {'loginId': 'becorelab', 'loginPw': 'qlzhdjfoq2023!!'}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
}


def login():
    session = requests.Session()
    session.headers.update(HEADERS)

    # GET 로그인 페이지 (세션 쿠키)
    r = session.get(f'{BASE}/login')
    print(f'[LOGIN GET] status={r.status_code}')

    # POST 로그인
    session.headers.update({'X-ajax-call': 'true', 'Content-Type': 'application/x-www-form-urlencoded'})
    r = session.post(f'{BASE}/login/', data=LOGIN_DATA, allow_redirects=True)
    print(f'[LOGIN POST] status={r.status_code}')
    try:
        data = r.json()
        print(f'[LOGIN] response: {json.dumps(data, ensure_ascii=False)[:200]}')
        if data.get('success'):
            print('[LOGIN] 로그인 성공!')
        else:
            print(f'[LOGIN] 실패: {data}')
    except Exception:
        print(f'[LOGIN] JSON 아님, text 앞부분: {r.text[:200]}')

    # 일반 헤더로 복원
    session.headers.update({'X-ajax-call': 'true', 'Accept': 'application/json, text/plain, */*'})
    return session


def analyze_page(session, url, page_name):
    """페이지 HTML 가져와서 구조 분석"""
    print(f'\n{"="*60}')
    print(f'[{page_name}] URL: {url}')
    print('='*60)

    r = session.get(url, timeout=30)
    print(f'Status: {r.status_code}')
    print(f'Content-Type: {r.headers.get("Content-Type", "")}')
    print(f'Content-Length: {len(r.text)} bytes')

    html = r.text

    # ── 1. inline JSON 데이터 찾기 ──
    print('\n[JSON in HTML]')
    json_patterns = [
        (r'var\s+(\w+)\s*=\s*(\{[^;]{20,}?\});', 'var obj = {...}'),
        (r'var\s+(\w+)\s*=\s*(\[[^\]]{20,}\]);', 'var arr = [...]'),
        (r'window\[[\'"]([\w]+)[\'"]\]\s*=\s*(\{[^;]{20,}?\});', 'window["key"] = {...}'),
    ]
    for pat, desc in json_patterns:
        matches = re.findall(pat, html, re.DOTALL)
        for name, raw in matches[:5]:
            try:
                obj = json.loads(raw)
                print(f'  {desc}: var {name} = {json.dumps(obj, ensure_ascii=False)[:150]}...')
            except Exception:
                pass

    # ── 2. data-* attribute 패턴 ──
    print('\n[data-attributes]')
    data_attrs = re.findall(r'data-[\w-]+=[\'""][^"\']*[\'""]', html)
    seen = set()
    for attr in data_attrs:
        key = re.match(r'data-[\w-]+', attr)
        if key and key.group() not in seen:
            seen.add(key.group())
            print(f'  {attr[:100]}')

    # ── 3. <script> 태그 내 API 호출 패턴 ──
    print('\n[API calls in scripts]')
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    api_patterns = [
        r"['\"/]api/[^\s'\"]+",
        r"fetch\s*\(['\"][^'\"]+['\"]",
        r"axios\.[a-z]+\s*\(['\"][^'\"]+['\"]",
        r"\$\.ajax\s*\(\s*\{[^}]*url\s*:\s*['\"][^'\"]+['\"]",
        r"XMLHttpRequest",
    ]
    found_apis = set()
    for script in scripts:
        for pat in api_patterns:
            for m in re.findall(pat, script):
                if m not in found_apis:
                    found_apis.add(m)
                    print(f'  {m[:120]}')

    # ── 4. 테이블 구조 ──
    print('\n[Tables]')
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
    for i, tbl in enumerate(tables[:5]):
        headers = re.findall(r'<th[^>]*>(.*?)</th>', tbl, re.DOTALL)
        headers_clean = [re.sub(r'<[^>]+>', '', h).strip() for h in headers if h.strip()]
        if headers_clean:
            print(f'  Table #{i+1}: headers = {headers_clean}')
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.DOTALL)
        print(f'  Table #{i+1}: {len(rows)} rows')

    # ── 5. 주요 div/container ID ──
    print('\n[Key IDs / Classes]')
    ids = re.findall(r'id=["\']([a-zA-Z][\w-]{3,})["\']', html)
    classes = re.findall(r'class=["\']([a-zA-Z][\w\s-]{5,})["\']', html)
    print(f'  IDs ({len(ids)} total): {list(dict.fromkeys(ids))[:30]}')
    # 주요 클래스만 (공백 없는 단일 클래스)
    single_classes = [c for c in classes if ' ' not in c][:20]
    print(f'  Notable classes: {list(dict.fromkeys(single_classes))}')

    # ── 6. HTML 앞부분 저장 ──
    return html


def analyze_ranking_data(html, product_id):
    """ranking 페이지 특화 분석"""
    print(f'\n{"="*60}')
    print(f'[RANKING PAGE DEEP ANALYSIS] product_id={product_id}')
    print('='*60)

    # ── 숫자 ID 패턴 (1901644 같은 것들) ──
    print('\n[Large number IDs in data-attributes]')
    big_numbers = re.findall(r'data-[\w-]+=[\'""](\d{6,})[\'""]', html)
    for n in list(dict.fromkeys(big_numbers))[:20]:
        # 해당 data-attr 전체 컨텍스트 찾기
        ctx = re.findall(rf'[^<]{{0,80}}data-[^=]+=[\'"]{n}[\'""][^>]{{0,80}}', html)
        for c in ctx[:2]:
            print(f'  {c.strip()[:150]}')

    # ── 상품 ID / 키워드 data attr ──
    print(f'\n[Items with data containing {product_id}]')
    ctx = re.findall(rf'.{{0,120}}{product_id}.{{0,120}}', html)
    for c in ctx[:10]:
        print(f'  ...{c.strip()[:200]}...')

    # ── 날짜 패턴 ──
    print('\n[Date patterns]')
    dates = re.findall(r'\d{4}-\d{2}-\d{2}', html)
    print(f'  Dates found: {list(dict.fromkeys(dates))[:20]}')

    # ── 순위 관련 숫자 ──
    print('\n[Ranking-related patterns]')
    rank_patterns = [
        r'rank["\']?\s*:\s*(\d+)',
        r'ranking["\']?\s*:\s*(\d+)',
        r'"rank"\s*:\s*(\d+)',
        r'data-rank=[\'""](\d+)[\'""]',
        r'data-ranking=[\'""](\d+)[\'""]',
    ]
    for pat in rank_patterns:
        matches = re.findall(pat, html, re.IGNORECASE)
        if matches:
            print(f'  Pattern "{pat[:40]}": {matches[:10]}')

    # ── script 태그 전체 내용 중 ranking 관련 ──
    print('\n[Script contents with ranking data]')
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for i, script in enumerate(scripts):
        if any(kw in script.lower() for kw in ['rank', 'keyword', 'date', 'chart', 'labels', 'datasets']):
            print(f'\n  --- Script #{i+1} (length={len(script)}) ---')
            # 처음 1000자만
            print(f'  {script[:1000]}')
            if len(script) > 1000:
                print(f'  ...[truncated, total {len(script)} chars]')

    # ── 리스트/배열 패턴 ──
    print('\n[Array / list data]')
    arr_patterns = re.findall(r'(?:labels|datasets|data|rankData|rankList)\s*[:=]\s*(\[[^\]]{0,500}\])', html, re.DOTALL)
    for arr_str in arr_patterns[:5]:
        print(f'  {arr_str[:200]}')

    # ── 키워드 문자열 ──
    print('\n[Korean keyword strings]')
    korean_strings = re.findall(r'[\'""]([가-힣\s]{4,30})[\'""]\s*[,\]}]', html)
    for s in list(dict.fromkeys(korean_strings))[:30]:
        print(f'  "{s}"')


def test_api_endpoints(session, product_id='45522'):
    """가능한 API 엔드포인트 직접 테스트"""
    print(f'\n{"="*60}')
    print(f'[API ENDPOINT TESTS] product_id={product_id}')
    print('='*60)

    endpoints = [
        # ranking 관련
        f'/api/ranking/{product_id}',
        f'/api/fast/ranking/{product_id}',
        f'/api/rank/{product_id}',
        f'/api/rankingHistory/{product_id}',
        f'/api/ranking/history/{product_id}',
        f'/api/product/ranking/{product_id}',
        # keyword analyze 관련
        '/api/keywordAnalyze/식기세척기 세제',
        '/api/naverKeyword/식기세척기 세제',
        '/api/keyword/analyze/식기세척기 세제',
        '/api/keywordData/식기세척기 세제',
        # 기존에 알려진 패턴
        '/api/relKeyword/식기세척기 세제',
        '/api/keywordCount/식기세척기 세제',
        '/api/keywordSection/식기세척기 세제',
    ]

    results = {}
    for ep in endpoints:
        try:
            url = BASE + ep
            r = session.get(url, timeout=10)
            ctype = r.headers.get('Content-Type', '')
            print(f'  {ep}')
            print(f'    → status={r.status_code}, type={ctype[:50]}, size={len(r.text)}')
            if r.status_code == 200 and 'json' in ctype:
                try:
                    data = r.json()
                    print(f'    → JSON keys: {list(data.keys())[:10]}')
                    print(f'    → data preview: {json.dumps(data, ensure_ascii=False)[:200]}')
                    results[ep] = data
                except Exception:
                    print(f'    → JSON parse fail: {r.text[:100]}')
            elif r.status_code == 200:
                print(f'    → text preview: {r.text[:100]}')
        except Exception as e:
            print(f'  {ep} → ERROR: {e}')

    return results


def main():
    # 1. 로그인
    session = login()

    # 2. 네이버 키워드 분석 페이지
    kw_url = 'https://helpstore.shop/keyword/keyword_analyze/식기세척기 세제'
    kw_html = analyze_page(session, kw_url, '네이버 키워드 분석')

    # 3. ranking 페이지
    rank_url = 'https://helpstore.shop/fast/ranking/45522'
    rank_html = analyze_page(session, rank_url, '키워드 순위 추적')

    # 4. ranking 페이지 심층 분석
    analyze_ranking_data(rank_html, '45522')

    # 5. API 엔드포인트 테스트
    api_results = test_api_endpoints(session)

    # 6. 결과 저장
    output = {
        'keyword_page_sample': kw_html[:5000],
        'ranking_page_sample': rank_html[:5000],
        'api_results': api_results,
    }
    with open('/Users/macmini_ky/ClaudeAITeam/marketing/helpstore_analysis_result.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print('\n\n[DONE] 분석 완료! helpstore_analysis_result.json 저장됨')


if __name__ == '__main__':
    main()
