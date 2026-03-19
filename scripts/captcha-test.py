"""보안코드 자동 인식 테스트 — Playwright + Claude Vision"""
import sys, os, time, base64, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'logistics'))
from playwright.sync_api import sync_playwright
import anthropic

# 이지어드민 설정
EZADMIN = {
    "url": "https://www.ezadmin.co.kr/index.html",
    "domain": "ka04",
    "id": "icanglobal",
    "pw": "Dkftm!234",
}

def read_captcha_with_claude(screenshot_path):
    """스크린샷에서 보안코드 숫자를 Claude Vision으로 읽기"""
    client = anthropic.Anthropic()

    with open(screenshot_path, "rb") as f:
        img_data = base64.standard_b64encode(f.read()).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_data,
                    },
                },
                {
                    "type": "text",
                    "text": "이 이미지에 보안코드 숫자 4자리가 보입니다. 숫자만 정확히 알려주세요. 숫자 4자리만 출력하세요. 예: 1234"
                }
            ],
        }],
    )

    code = response.content[0].text.strip()
    # 숫자만 추출
    digits = ''.join(c for c in code if c.isdigit())
    return digits[:4] if len(digits) >= 4 else digits


def main():
    print("🚀 보안코드 자동 인식 테스트 시작")

    with sync_playwright() as p:
        # Edge(msedge) 브라우저 사용
        browser = p.chromium.launch(
            channel="msedge",
            headless=False,  # 화면 보이게
        )
        page = browser.new_page()

        # 1. 이지어드민 로그인 페이지 이동
        print("1️⃣ 이지어드민 접속 중...")
        page.goto(EZADMIN["url"], timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # 2. 로그인 팝업 표시 + 정보 입력
        print("2️⃣ 로그인 정보 입력 중...")
        page.evaluate("document.getElementById('login-popup').style.display = 'block'")
        page.wait_for_timeout(1000)

        page.fill("#login-domain", EZADMIN["domain"])
        page.fill("#login-id", EZADMIN["id"])
        page.fill("#login-pwd", EZADMIN["pw"])

        # 3. 로그인 실행
        print("3️⃣ 로그인 실행...")
        page.evaluate("login_check(null)")
        page.wait_for_timeout(8000)
        print(f"   현재 URL: {page.url}")

        # 4. 보안코드 팝업 감지
        print("4️⃣ 보안코드 확인 중...")
        has_captcha = False
        for i in range(10):
            has_captcha = page.evaluate("""
                (() => {
                    const blocks = document.querySelectorAll('.blockUI.blockMsg');
                    for (const b of blocks) {
                        if (b.offsetWidth > 0 && b.offsetHeight > 0
                            && !b.querySelector('#wrap')) return true;
                    }
                    return false;
                })()
            """)
            if has_captcha:
                break
            time.sleep(1)

        if not has_captcha:
            print("   ✅ 보안코드 없음 — 이미 인증됨!")
            browser.close()
            return

        print("   🔒 보안코드 발견! 스크린샷 촬영...")

        # 5. 스크린샷 촬영
        screenshot_path = os.path.join(os.path.dirname(__file__), "captcha_screenshot.png")
        page.screenshot(path=screenshot_path)
        print(f"   📸 스크린샷 저장: {screenshot_path}")

        # 6. Claude Vision으로 보안코드 읽기
        print("5️⃣ Claude Sonnet으로 보안코드 읽는 중...")
        captcha_code = read_captcha_with_claude(screenshot_path)
        print(f"   🔑 인식된 보안코드: {captcha_code}")

        if len(captcha_code) == 4:
            # 7. 보안코드 입력
            print("6️⃣ 보안코드 입력 중...")
            # 보안코드 입력 필드 찾기
            captcha_input = page.evaluate("""
                (() => {
                    const blocks = document.querySelectorAll('.blockUI.blockMsg');
                    for (const b of blocks) {
                        const input = b.querySelector('input[type="text"], input[type="number"], input:not([type])');
                        if (input) {
                            input.value = '""" + captcha_code + """';
                            input.dispatchEvent(new Event('input', {bubbles: true}));
                            input.dispatchEvent(new Event('change', {bubbles: true}));
                            return 'input found and filled';
                        }
                    }
                    // input이 없으면 키보드로 직접 입력 시도
                    return 'no input found';
                })()
            """)
            print(f"   입력 결과: {captcha_input}")

            # 확인/전송 버튼 클릭
            page.evaluate("""
                (() => {
                    const blocks = document.querySelectorAll('.blockUI.blockMsg');
                    for (const b of blocks) {
                        const btn = b.querySelector('button, input[type="submit"], input[type="button"], a.btn');
                        if (btn) { btn.click(); return 'clicked'; }
                    }
                    return 'no button';
                })()
            """)

            page.wait_for_timeout(5000)

            # 보안코드 통과 확인
            still_captcha = page.evaluate("""
                (() => {
                    const blocks = document.querySelectorAll('.blockUI.blockMsg');
                    for (const b of blocks) {
                        if (b.offsetWidth > 0 && b.offsetHeight > 0
                            && !b.querySelector('#wrap')) return true;
                    }
                    return false;
                })()
            """)

            if still_captcha:
                print("   ❌ 보안코드 통과 실패 — 재시도 필요")
            else:
                print("   ✅ 보안코드 통과 성공!!!")
                print(f"   현재 URL: {page.url}")
        else:
            print(f"   ❌ 보안코드 인식 실패: '{captcha_code}'")

        print("\n⏳ 30초 대기 (화면 확인용)...")
        page.wait_for_timeout(30000)
        browser.close()


if __name__ == "__main__":
    main()
