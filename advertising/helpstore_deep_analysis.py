"""
헬프스토어 Deep Analysis - ranking 테이블 HTML 구조 + keyword_analyze 페이지 API 파악
"""

import requests
import json
import re
from bs4 import BeautifulSoup

BASE = 'https://helpstore.shop'
LOGIN_DATA = {'loginId': 'becorelab', 'loginPw': 'qlzhdjfoq2023!!'}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'X-ajax-call': 'true',
}


def login():
    session = requests.Session()
    session.headers.update({
        'User-Agent': HEADERS['User-Agent'],
    })
    session.get(f'{BASE}/login')
    session.headers.update({'X-ajax-call': 'true'})
    r = session.post(f'{BASE}/login/', data=LOGIN_DATA, allow_redirects=True)
    data = r.json()
    assert data.get('success'), f'로그인 실패: {data}'
    print('[OK] 로그인 성공')
    return session


def parse_ranking_table(session):
    """ranking 페이지 테이블 구조 완전 파싱"""
    print('\n' + '='*60)
    print('[RANKING TABLE DEEP PARSE]')
    print('='*60)

    # HTML 페이지 받기 (non-ajax)
    s2 = requests.Session()
    s2.headers.update({'User-Agent': HEADERS['User-Agent']})
    # 로그인
    s2.get(f'{BASE}/login')
    s2.post(f'{BASE}/login/', data=LOGIN_DATA, allow_redirects=True)

    r = s2.get('https://helpstore.shop/fast/ranking/45522', timeout=30)
    html = r.text
    soup = BeautifulSoup(html, 'html.parser')

    # ── 테이블 헤더 (날짜 컬럼) ──
    table = soup.find('table')
    if not table:
        print('[ERROR] 테이블 없음')
        return

    thead = table.find('thead')
    if thead:
        ths = thead.find_all('th')
        print(f'\n컬럼 수: {len(ths)}')
        print('헤더:')
        for i, th in enumerate(ths):
            # data-id 같은 속성 있으면 출력
            attrs = dict(th.attrs)
            text = th.get_text(strip=True).replace('\n', ' ').replace('\t', ' ')
            # 중복 공백 제거
            text = re.sub(r'\s+', ' ', text)
            # [삭제] 등 제거
            text = text.replace('[삭제]', '').strip()
            delete_a = th.find('a', class_='btnDelete')
            scan_id = delete_a.get('data-id') if delete_a else None
            print(f'  [{i}] "{text}" | scan_id={scan_id} | attrs={attrs}')

    # ── 테이블 바디 (키워드별 순위 데이터) ──
    tbody = table.find('tbody', id='keywordTbody') or table.find('tbody')
    if not tbody:
        print('[ERROR] tbody 없음')
        return

    rows = tbody.find_all('tr')
    print(f'\n행 수: {len(rows)}')
    print('\n첫 3개 행 구조:')
    for i, row in enumerate(rows[:3]):
        print(f'\n  === 행 #{i+1} ===')
        # 행 전체 attrs
        print(f'  row attrs: {dict(row.attrs)}')
        cells = row.find_all('td')
        for j, cell in enumerate(cells):
            cell_text = cell.get_text(strip=True)
            cell_attrs = dict(cell.attrs)
            # 내부 a 태그
            a_tags = cell.find_all('a')
            a_info = [(a.get_text(strip=True), dict(a.attrs)) for a in a_tags]
            # 내부 span
            spans = cell.find_all('span')
            span_texts = [s.get_text(strip=True) for s in spans]
            print(f'  cell[{j}]: text="{cell_text[:80]}" attrs={cell_attrs}')
            if a_info:
                print(f'    a_tags: {a_info[:3]}')
            if span_texts:
                print(f'    spans: {span_texts[:5]}')

    # ── 전체 데이터 추출 ──
    print('\n\n=== 전체 순위 데이터 추출 ===')
    # 헤더에서 날짜 목록
    ths = thead.find_all('th') if thead else []
    dates = []
    scan_ids = []
    for th in ths[1:]:  # 첫 번째는 키워드
        delete_a = th.find('a', class_='btnDelete')
        text = th.get_text(strip=True)
        # 날짜 추출
        date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', text)
        date_str = date_match.group(1) if date_match else text[:16]
        dates.append(date_str)
        scan_ids.append(delete_a.get('data-id') if delete_a else None)

    print(f'날짜 컬럼 ({len(dates)}개): {dates[:5]}...')
    print(f'scan_ids ({len(scan_ids)}개): {scan_ids[:5]}...')

    rows = tbody.find_all('tr')
    all_data = []
    for row in rows:
        cells = row.find_all('td')
        if not cells:
            continue

        # 첫 번째 셀: 키워드 정보
        first_cell = cells[0]
        keyword_text = first_cell.get_text(strip=True)

        # data-keyword, data-keyword-id 찾기
        # row 또는 cell에 있을 수 있음
        keyword_elem = row.find(attrs={'data-keyword': True}) or first_cell.find(attrs={'data-keyword': True})
        keyword = keyword_elem.get('data-keyword') if keyword_elem else keyword_text
        keyword_id = keyword_elem.get('data-keyword-id') if keyword_elem else None

        row_data = {
            'keyword': keyword,
            'keyword_id': keyword_id,
            'rankings': {}
        }

        # 나머지 셀: 날짜별 순위
        for j, cell in enumerate(cells[1:]):
            if j < len(dates):
                date = dates[j]
                # 순위 텍스트 (숫자만)
                cell_text = cell.get_text(strip=True)
                rank_match = re.search(r'\d+', cell_text)
                rank_val = int(rank_match.group()) if rank_match else None
                # '-' or '없음' 처리
                if not rank_match:
                    rank_val = None
                row_data['rankings'][date] = rank_val

        all_data.append(row_data)
        print(f'  키워드: "{keyword}" (id={keyword_id}) | 최신순위={list(row_data["rankings"].values())[0] if row_data["rankings"] else None}')

    # JSON 저장
    result = {
        'product_id': '45522',
        'dates': dates,
        'scan_ids': scan_ids,
        'keywords': all_data
    }
    with open('/Users/macmini_ky/ClaudeAITeam/marketing/ranking_data_parsed.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'\n총 {len(all_data)}개 키워드 데이터 추출 완료')
    print('ranking_data_parsed.json 저장됨')

    return result


def analyze_keyword_page(session):
    """네이버 키워드 분석 페이지 - script 태그 + API 패턴 분석"""
    print('\n' + '='*60)
    print('[KEYWORD ANALYZE PAGE ANALYSIS]')
    print('='*60)

    # HTML 받기 (non-ajax, 브라우저처럼)
    s2 = requests.Session()
    s2.headers.update({'User-Agent': HEADERS['User-Agent']})
    s2.get(f'{BASE}/login')
    s2.post(f'{BASE}/login/', data=LOGIN_DATA, allow_redirects=True)

    # URL encode 적용
    kw_url = 'https://helpstore.shop/keyword/keyword_analyze/식기세척기 세제'
    r = s2.get(kw_url, timeout=30)
    html = r.text
    soup = BeautifulSoup(html, 'html.parser')

    # 스크립트 태그 전체 추출
    scripts = soup.find_all('script')
    print(f'\n총 script 태그: {len(scripts)}개')

    for i, script in enumerate(scripts):
        src = script.get('src', '')
        content = script.string or ''
        if src:
            print(f'\nScript #{i+1}: src="{src}"')
        elif content.strip():
            # 주요 내용만 출력
            content_preview = content.strip()[:300]
            if any(kw in content for kw in ['ajax', 'fetch', 'api/', 'API', 'data', 'keyword', 'url']):
                print(f'\nScript #{i+1} (inline, {len(content)}chars):')
                print(content.strip()[:500])

    # JS 파일에서 API 패턴 찾기
    print('\n\n[JS 파일 분석]')
    js_files = [s.get('src') for s in scripts if s.get('src') and 'helpstore' not in (s.get('src') or '')]
    local_js = [s.get('src') for s in scripts if s.get('src') and ('.js' in (s.get('src') or '')) and not s.get('src', '').startswith('http')]
    print(f'외부 JS: {js_files}')
    print(f'로컬 JS: {local_js}')

    for js_path in local_js[:5]:
        full_url = BASE + js_path if js_path.startswith('/') else js_path
        print(f'\n  Fetching: {full_url}')
        try:
            rj = s2.get(full_url, timeout=15)
            js_content = rj.text
            # API 패턴 찾기
            api_calls = re.findall(r"url\s*[=:]\s*['\"]([^'\"]+)['\"]", js_content)
            ajax_patterns = re.findall(r"ajax[^{]{0,20}\{[^}]{0,200}\}", js_content, re.DOTALL)
            fetch_patterns = re.findall(r"fetch\s*\(['\"][^'\"]+['\"]", js_content)

            if api_calls:
                print(f'  API URLs: {api_calls[:10]}')
            if fetch_patterns:
                print(f'  fetch calls: {fetch_patterns[:10]}')

            # 키워드 분석 관련 함수명
            funcs = re.findall(r'function\s+(\w+)\s*\(', js_content)
            kw_funcs = [f for f in funcs if any(k in f.lower() for k in ['keyword', 'analyze', 'rank', 'search', 'naver'])]
            if kw_funcs:
                print(f'  관련 함수: {kw_funcs}')
        except Exception as e:
            print(f'  ERROR: {e}')

    # 기존 API 테스트 (helpstore.py에서 발견된 것들)
    print('\n\n[알려진 API 테스트 - 식기세척기세제]')
    known_apis = [
        '/api/relKeyword/식기세척기세제',
        '/api/keywordCount/식기세척기세제',
        '/api/shoppingKeyword/식기세척기세제',
        '/api/keywordSection/식기세척기세제',
        '/api/etcKeyword/식기세척기세제',
        '/token/keyword',
        '/api/keywordTrend/50000830/식기세척기세제',
    ]

    results = {}
    for ep in known_apis:
        url = BASE + ep
        r = session.get(url, timeout=15)
        ct = r.headers.get('Content-Type', '')
        print(f'\n  {ep}')
        print(f'    status={r.status_code}, size={len(r.text)}')
        if 'json' in ct and r.status_code == 200:
            try:
                data = r.json()
                print(f'    keys: {list(data.keys())}')
                # data 내부 구조
                inner = data.get('data', {})
                if isinstance(inner, dict):
                    print(f'    data keys: {list(inner.keys())[:10]}')
                    # list 항목 첫 번째 미리보기
                    for k, v in inner.items():
                        if isinstance(v, list) and v:
                            print(f'    data.{k}[0]: {json.dumps(v[0], ensure_ascii=False)[:200]}')
                        elif not isinstance(v, list):
                            print(f'    data.{k}: {str(v)[:100]}')
                results[ep] = data
            except Exception as e:
                print(f'    JSON error: {e}')

    # 결과 저장
    with open('/Users/macmini_ky/ClaudeAITeam/marketing/keyword_api_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print('\n\nkeyword_api_results.json 저장됨')

    return results


def analyze_ranking_api(session):
    """ranking 관련 API 패턴 더 깊이 탐색"""
    print('\n' + '='*60)
    print('[RANKING API DISCOVERY]')
    print('='*60)

    # JS 파일 다운로드 (non-ajax 세션으로)
    s2 = requests.Session()
    s2.headers.update({'User-Agent': HEADERS['User-Agent']})
    s2.get(f'{BASE}/login')
    s2.post(f'{BASE}/login/', data=LOGIN_DATA, allow_redirects=True)

    r = s2.get('https://helpstore.shop/fast/ranking/45522', timeout=30)
    html = r.text
    soup = BeautifulSoup(html, 'html.parser')

    # JS 파일 목록
    scripts = soup.find_all('script', src=True)
    print(f'Script src 개수: {len(scripts)}')
    for s in scripts:
        print(f'  {s.get("src")}')

    # ranking.min.js 또는 fast.min.js 찾기
    for script_tag in scripts:
        src = script_tag.get('src', '')
        if any(k in src for k in ['rank', 'fast', 'common', 'hb', 'helpstore']):
            full_url = BASE + src if src.startswith('/') else src
            print(f'\n[Analyzing JS] {full_url}')
            try:
                rj = s2.get(full_url, timeout=15)
                js = rj.text

                # URL 패턴
                urls = re.findall(r"['\"/]((?:api|fast|rank|token)[^\s'\"&?#]+)", js)
                for u in list(dict.fromkeys(urls))[:30]:
                    print(f'  URL: {u}')

                # ajax/fetch
                ajax = re.findall(r"url\s*[=:]\s*['\"]([^'\"]{3,80})['\"]", js)
                for a in list(dict.fromkeys(ajax))[:20]:
                    print(f'  ajax url: {a}')

            except Exception as e:
                print(f'  ERROR: {e}')

    # 추가 API 후보 테스트
    print('\n[추가 API 후보 테스트]')
    candidates = [
        # ranking 데이터 관련
        '/api/fast/ranking',
        '/api/fastRanking/45522',
        '/fast/api/ranking/45522',
        '/api/rankHistory/45522',
        '/api/rankingData/45522',
        '/api/rank/data/45522',
        '/rank/data/45522',
        # keyword_id 기반
        '/api/ranking/keyword/383380',  # 식기세척기세제 keyword_id
        '/api/rank/keyword/383380',
        # scan_id 기반 (1901644)
        '/api/scan/1901644',
        '/api/ranking/scan/1901644',
        # 엑셀 다운로드 endpoint
        '/api/excel/ranking/45522',
        '/excel/ranking/45522',
        '/fast/excel/45522',
        # 알림 설정
        '/api/alim/ranking/45522',
    ]

    for ep in candidates:
        url = BASE + ep
        try:
            r = session.get(url, timeout=8)
            ct = r.headers.get('Content-Type', '')
            size = len(r.text)
            if r.status_code != 404 or 'json' in ct:
                print(f'  [HIT] {ep} → status={r.status_code}, type={ct[:40]}, size={size}')
                if 'json' in ct:
                    try:
                        d = r.json()
                        print(f'    data: {json.dumps(d, ensure_ascii=False)[:300]}')
                    except Exception:
                        pass
            else:
                print(f'  [404] {ep}')
        except Exception as e:
            print(f'  [ERR] {ep}: {e}')


def main():
    session = login()

    # 1. ranking 테이블 파싱
    ranking_data = parse_ranking_table(session)

    # 2. keyword 분석 페이지 API
    keyword_data = analyze_keyword_page(session)

    # 3. ranking API 탐색
    analyze_ranking_api(session)

    print('\n\n=== 완료 ===')


if __name__ == '__main__':
    main()
