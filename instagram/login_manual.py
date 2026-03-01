"""
login_manual.py — 인스타그램 수동 로그인 (최초 1회)
브라우저 창이 뜨면 직접 로그인 → 세션 자동 저장
이후 봇은 저장된 세션으로 자동 로그인
"""

import asyncio
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_PATH = os.path.join(BASE_DIR, 'session.json')


async def manual_login():
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,  # 브라우저 창 띄우기
        args=[
            '--no-sandbox',
            '--disable-blink-features=AutomationControlled',
        ]
    )
    context = await browser.new_context(
        viewport={'width': 390, 'height': 844},
        user_agent=(
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) '
            'Version/16.6 Mobile/15E148 Safari/604.1'
        ),
        locale='ko-KR',
    )
    page = await context.new_page()

    print("━" * 50)
    print("  인스타그램 로그인 창이 열립니다!")
    print("  직접 로그인해주세요 (2FA 포함)")
    print("━" * 50)

    await page.goto('https://www.instagram.com/')
    await asyncio.sleep(3)

    # 로그인 완료 대기 (URL이 바뀔 때까지)
    print("\n⏳ 로그인 대기 중... (완료되면 자동 감지)")

    for _ in range(300):  # 최대 5분
        await asyncio.sleep(1)
        url = page.url
        if '/accounts/login/' not in url and 'instagram.com' in url:
            # 메인 페이지에 도달했는지 확인
            await asyncio.sleep(3)
            if '/accounts/login/' not in page.url:
                break
    else:
        print("❌ 5분 내에 로그인하지 않아 종료합니다.")
        await browser.close()
        await pw.stop()
        return

    # 세션 저장
    state = await context.storage_state()
    with open(SESSION_PATH, 'w') as f:
        json.dump(state, f)

    print("\n✅ 로그인 성공! 세션이 저장되었어요.")
    print(f"   파일: {SESSION_PATH}")
    print("   이제 봇이 이 세션으로 자동 동작합니다.")

    # DB에도 계정 저장
    try:
        from instagram_bot import get_db, init_db
        init_db()
        # 현재 로그인된 유저네임 확인
        await page.goto('https://www.instagram.com/accounts/edit/', wait_until='networkidle')
        await asyncio.sleep(2)

        conn = get_db()
        if len(sys.argv) > 1:
            conn.execute("UPDATE settings SET value=? WHERE key='ig_username'", (sys.argv[1],))
        conn.execute("UPDATE settings SET value='true' WHERE key='bot_active'")
        conn.commit()
        conn.close()
        print("   봇 자동화 ON 설정 완료!")
    except Exception as e:
        print(f"   (DB 저장 참고: {e})")

    await browser.close()
    await pw.stop()


if __name__ == '__main__':
    print("\n🔐 iLBiA 인스타그램 로그인\n")
    asyncio.run(manual_login())
