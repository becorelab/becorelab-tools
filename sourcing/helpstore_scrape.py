import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 1. 로그인
        await page.goto('https://helpstore.shop/login')
        await page.wait_for_load_state('networkidle')
        await page.fill('#loginId', 'becorelab')
        await page.fill('#loginPw', 'qlzhdjfoq2023!!')
        await page.click('#btnLogin')
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)
        print('Logged in')

        # 상세 API 응답 수집
        results = {}

        # 1. /api/relKeyword/ - 연관 키워드 (전체 응답)
        resp = await page.evaluate('''async () => {
            const res = await fetch('/api/relKeyword/' + encodeURIComponent('건조기시트'), {
                headers: {'X-ajax-call': 'true'}
            });
            return await res.json();
        }''')
        results['relKeyword'] = resp
        print('relKeyword: list count =', len(resp.get('data', {}).get('list', [])))

        # 2. /api/keywordCount/ - 키워드 카운트
        resp = await page.evaluate('''async () => {
            const res = await fetch('/api/keywordCount/' + encodeURIComponent('건조기시트'), {
                headers: {'X-ajax-call': 'true'}
            });
            return await res.json();
        }''')
        results['keywordCount'] = resp
        print('keywordCount:', json.dumps(resp, ensure_ascii=False)[:200])

        # 3. /api/shoppingKeyword/ - 쇼핑 키워드 자동완성
        resp = await page.evaluate('''async () => {
            const res = await fetch('/api/shoppingKeyword/' + encodeURIComponent('건조기시트'), {
                headers: {'X-ajax-call': 'true'}
            });
            return await res.json();
        }''')
        results['shoppingKeyword'] = resp
        print('shoppingKeyword:', json.dumps(resp, ensure_ascii=False)[:300])

        # 4. /api/keywordSection/ - 키워드 섹션
        resp = await page.evaluate('''async () => {
            const res = await fetch('/api/keywordSection/' + encodeURIComponent('건조기시트'), {
                headers: {'X-ajax-call': 'true'}
            });
            return await res.json();
        }''')
        results['keywordSection'] = resp
        print('keywordSection:', json.dumps(resp, ensure_ascii=False)[:300])

        # 5. /api/etcKeyword/ - 기타 키워드
        resp = await page.evaluate('''async () => {
            const res = await fetch('/api/etcKeyword/' + encodeURIComponent('건조기시트'), {
                headers: {'X-ajax-call': 'true'}
            });
            return await res.json();
        }''')
        results['etcKeyword'] = resp
        print('etcKeyword:', json.dumps(resp, ensure_ascii=False)[:200])

        # 6. /token/keyword - 키워드 토큰
        resp = await page.evaluate('''async () => {
            const res = await fetch('/token/keyword', {
                headers: {'X-ajax-call': 'true'}
            });
            return await res.json();
        }''')
        results['tokenKeyword'] = resp
        token = resp.get('data', {}).get('token', '')
        print(f'Token: {token}')

        # 7. /api/complete/keyword - 키워드 완료 보고 (토큰 포함)
        resp = await page.evaluate('''async ([token]) => {
            const res = await fetch('/api/complete/keyword', {
                method: 'POST',
                headers: {
                    'X-ajax-call': 'true',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    keyword: '건조기시트',
                    token: token,
                    type: 'keyword_analyze_coupang'
                })
            });
            return await res.json();
        }''', [token])
        results['completeKeyword'] = resp
        print('completeKeyword:', json.dumps(resp, ensure_ascii=False))

        # 8. /api/translate - 번역 (올바른 토큰 사용)
        translate_token_resp = await page.evaluate('''async () => {
            const res = await fetch('/token/translate', {
                headers: {'X-ajax-call': 'true'}
            });
            return await res.json();
        }''')
        translate_token = translate_token_resp.get('data', {}).get('token', '')

        resp = await page.evaluate('''async ([token]) => {
            const res = await fetch('/api/translate', {
                method: 'POST',
                headers: {
                    'X-ajax-call': 'true',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    keyword: '건조기시트',
                    token: token
                })
            });
            return await res.json();
        }''', [translate_token])
        results['translate'] = resp
        print('translate:', json.dumps(resp, ensure_ascii=False)[:300])

        # 9. /api/keywordTrend - 키워드 트렌드
        resp = await page.evaluate('''async () => {
            const res = await fetch('/api/keywordTrend/50000830/' + encodeURIComponent('건조기시트'), {
                headers: {'X-ajax-call': 'true'}
            });
            return await res.json();
        }''')
        results['keywordTrend'] = resp
        print('keywordTrend: success =', resp.get('success'), ', keys =', list(resp.get('data', {}).keys()))

        # 전체 결과 저장
        with open('helpstore_api_responses.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print('\n=== ALL RESPONSES SAVED ===')

        # relKeyword 응답에서 개별 아이템 구조 확인
        rel_list = results.get('relKeyword', {}).get('data', {}).get('list', [])
        if rel_list:
            print('\n=== relKeyword ITEM STRUCTURE ===')
            print(json.dumps(rel_list[0], ensure_ascii=False, indent=2))

        await browser.close()

asyncio.run(main())
