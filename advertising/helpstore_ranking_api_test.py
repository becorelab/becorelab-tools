"""
fastDetail.min.js에서 발견한 API 엔드포인트 테스트
- fast/keyword/reorder/
- fast/request/delete/
- tokens/rank
- fast/excel
"""

import requests
import json
import re

BASE = 'https://helpstore.shop'
LOGIN_DATA = {'loginId': 'becorelab', 'loginPw': 'qlzhdjfoq2023!!'}

def login():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'X-ajax-call': 'true',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://helpstore.shop/fast/ranking/45522',
    })
    session.get(f'{BASE}/login')
    r = session.post(f'{BASE}/login/', data=LOGIN_DATA, allow_redirects=True)
    data = r.json()
    assert data.get('success'), f'로그인 실패: {data}'
    print('[OK] 로그인 성공')
    return session


def test_fastdetail_apis(session):
    """fastDetail.min.js에서 발견한 API 테스트"""
    print('\n' + '='*60)
    print('[fastDetail.min.js API 테스트]')
    print('='*60)

    # 1. tokens/rank - ranking용 토큰 발급
    print('\n[1] GET /tokens/rank')
    r = session.get(f'{BASE}/tokens/rank', timeout=10)
    print(f'  status={r.status_code}, ct={r.headers.get("Content-Type","")[:50]}')
    if r.status_code == 200:
        try:
            d = r.json()
            print(f'  response: {json.dumps(d, ensure_ascii=False)}')
        except Exception:
            print(f'  text: {r.text[:200]}')

    # 2. fast/keyword/reorder/ - 키워드 순서 변경
    print('\n[2] GET /fast/keyword/reorder/')
    r = session.get(f'{BASE}/fast/keyword/reorder/', timeout=10)
    print(f'  status={r.status_code}')
    if r.status_code != 404:
        print(f'  text: {r.text[:200]}')

    # POST 시도
    print('\n[2] POST /fast/keyword/reorder/')
    r = session.post(f'{BASE}/fast/keyword/reorder/',
                     json={'rankingId': '45522', 'keywordIds': ['383380', '383381']},
                     timeout=10)
    print(f'  status={r.status_code}')
    if r.status_code != 404:
        print(f'  text: {r.text[:200]}')

    # 3. fast/request/delete/ - 스캔 삭제 (사용 주의)
    print('\n[3] fast/request/delete/ - 테스트 안 함 (삭제 위험)')

    # 4. fast/excel - 엑셀 다운로드
    print('\n[4] GET /fast/excel')
    r = session.get(f'{BASE}/fast/excel', timeout=10)
    print(f'  status={r.status_code}, ct={r.headers.get("Content-Type","")[:50]}')

    # 5. JS 파일 전체 내용 분석
    print('\n\n[fastDetail.min.js 전체 URL 패턴 분석]')
    r = requests.get('https://helpstore.shop/assets/js/pagejs/fastDetail.min.js?ver=1777162229242',
                     headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    js = r.text
    print(f'JS 파일 크기: {len(js)} bytes')

    # beautify first 3000 chars
    print('\n--- JS 내용 (앞 3000자) ---')
    print(js[:3000])

    # URL 패턴 전체 추출
    print('\n--- URL 패턴 전체 ---')
    url_patterns = re.findall(r"['\"]/([\w/.-]+)['\"]", js)
    for u in list(dict.fromkeys(url_patterns)):
        if len(u) > 3 and not any(skip in u for skip in ['assets', 'jquery', 'cdn']):
            print(f'  /{u}')

    # ajax 호출 패턴
    print('\n--- AJAX 호출 ---')
    ajax_calls = re.findall(r'(?:url|URL)\s*[=:]\s*["\']([^"\']+)["\']', js)
    for a in list(dict.fromkeys(ajax_calls)):
        print(f'  {a}')

    # 함수명 추출
    print('\n--- 주요 함수명 ---')
    funcs = re.findall(r'function\s+(\w+)\s*\(', js)
    print(f'  {funcs[:30]}')

    # 변수명 패턴 (API 관련)
    print('\n--- API 관련 변수 ---')
    vars_api = re.findall(r'var\s+(\w+)\s*=\s*["\']([^"\']{5,50})["\']', js)
    for name, val in vars_api[:20]:
        print(f'  {name} = "{val}"')

    return js


def test_ranking_data_endpoints(session):
    """ranking 데이터 조회 API 패턴 테스트"""
    print('\n' + '='*60)
    print('[ranking 데이터 조회 API 테스트]')
    print('='*60)

    # fastDetail.min.js 분석 결과 기반 추가 후보
    candidates = [
        # fast prefix 패턴
        ('GET', '/fast/ranking/data/45522', None),
        ('GET', '/fast/rankingData/45522', None),
        ('GET', '/fast/keyword/45522', None),
        ('GET', '/fast/keywords/45522', None),
        ('GET', '/fast/history/45522', None),
        ('GET', '/fast/result/45522', None),
        # rank prefix
        ('GET', '/rank/fast/45522', None),
        # tokens
        ('GET', '/tokens/rank', None),
        ('GET', '/token/rank', None),
        ('GET', '/tokens/ranking', None),
        # keyword_id 기반
        ('GET', '/fast/ranking/keyword/383380', None),
        ('GET', '/fast/keyword/ranking/383380', None),
        # scan 기반
        ('GET', '/fast/scan/1905567', None),
        ('GET', '/fast/scan/result/1905567', None),
        ('GET', '/fast/ranking/scan/1905567', None),
        # 다른 패턴들
        ('GET', '/api/fast/keyword/ranking', None),
        ('GET', '/api/rankings/45522', None),
    ]

    for method, ep, body in candidates:
        url = BASE + ep
        try:
            if method == 'GET':
                r = session.get(url, timeout=8)
            else:
                r = session.post(url, json=body, timeout=8)

            ct = r.headers.get('Content-Type', '')
            size = len(r.text)
            status = r.status_code

            if status != 404:
                print(f'  [HIT {status}] {ep} | ct={ct[:40]} | size={size}')
                if 'json' in ct:
                    try:
                        d = r.json()
                        print(f'    keys: {list(d.keys()) if isinstance(d, dict) else type(d).__name__}')
                        print(f'    data: {json.dumps(d, ensure_ascii=False)[:300]}')
                    except Exception:
                        pass
                elif size < 500:
                    print(f'    text: {r.text[:200]}')
            else:
                print(f'  [404] {ep}')
        except Exception as e:
            print(f'  [ERR] {ep}: {e}')


def analyze_table_cell_structure():
    """테이블 셀 데이터 구조 정밀 분석"""
    print('\n' + '='*60)
    print('[테이블 셀 구조 정밀 분석]')
    print('='*60)

    from bs4 import BeautifulSoup

    s2 = requests.Session()
    s2.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    s2.get(f'{BASE}/login')
    s2.post(f'{BASE}/login/', data=LOGIN_DATA, allow_redirects=True)

    r = s2.get('https://helpstore.shop/fast/ranking/45522', timeout=30)
    html = r.text
    soup = BeautifulSoup(html, 'html.parser')

    # 첫 번째 행의 첫 번째 데이터 셀 HTML 전체
    tbody = soup.find('tbody', id='keywordTbody')
    if not tbody:
        tbody = soup.find('tbody')

    rows = tbody.find_all('tr')
    if rows:
        first_row = rows[0]
        cells = first_row.find_all('td')

        print('\n첫 번째 행 첫 번째 셀 (키워드 셀) HTML:')
        print(str(cells[0])[:500])

        print('\n첫 번째 행 두 번째 셀 (날짜 셀) HTML:')
        print(str(cells[1])[:500])

        print('\n세 번째 셀 HTML:')
        print(str(cells[2])[:500])

    # 키워드 셀 구조 분석
    print('\n\n키워드 셀 전체 구조:')
    first_cells = [row.find('td', class_='left') for row in rows if row.find('td', class_='left')]
    for i, cell in enumerate(first_cells[:5]):
        print(f'\n키워드 #{i+1}: {str(cell)[:400]}')

    # data-keyword, data-keyword-id가 어디 있는지
    print('\n\ndata-keyword 속성 있는 요소들:')
    elems = soup.find_all(attrs={'data-keyword': True})
    for elem in elems[:10]:
        print(f'  tag={elem.name}, attrs={dict(elem.attrs)}, text={elem.get_text(strip=True)[:50]}')

    # setKeywords div 구조
    print('\n\nsetKeywords div:')
    set_kw = soup.find(id='setKeywords')
    if set_kw:
        print(str(set_kw)[:1000])

    # newKeywordForm
    print('\n\nnewKeywordForm:')
    form = soup.find(id='newKeywordForm')
    if form:
        print(str(form)[:500])

    # 전체 HTML 저장 (처음 10000자)
    with open('/Users/macmini_ky/ClaudeAITeam/marketing/ranking_page_html_sample.html', 'w', encoding='utf-8') as f:
        f.write(html[:30000])
    print('\n\nranking_page_html_sample.html 저장됨 (처음 30000자)')


def main():
    session = login()

    # 1. fastDetail JS API 테스트
    js_content = test_fastdetail_apis(session)

    # 2. ranking 데이터 엔드포인트 테스트
    test_ranking_data_endpoints(session)

    # 3. 테이블 셀 구조 정밀 분석
    analyze_table_cell_structure()

    print('\n\n=== 완료 ===')


if __name__ == '__main__':
    main()
