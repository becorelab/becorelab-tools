"""인스타 최초 로그인 — 브라우저 창에서 수동 로그인 후 세션 저장.

사용법:
  python login_manual.py
  → 브라우저 창이 뜨면 인스타 로그인 → 로그인 완료 후 터미널에서 Enter
"""
import asyncio
import json
import os
from config import SESSION_PATH


async def manual_login():
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.4 Mobile/15E148 Safari/604.1"
        ),
        locale="ko-KR",
    )
    page = await context.new_page()
    await page.goto("https://www.instagram.com/accounts/login/")

    print("\n" + "=" * 50)
    print("브라우저에서 인스타그램에 로그인해주세요.")
    print("로그인 완료 후 여기서 Enter를 눌러주세요.")
    print("=" * 50)
    input()

    state = await context.storage_state()
    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)

    print(f"세션 저장 완료: {SESSION_PATH}")

    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(manual_login())
