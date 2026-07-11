"""
그로스 세션 쿠키 브릿지 — 대표님 평소 크롬 쿠키를 빌려 CDP 크롬에 주입.

배경: 쿠팡 Wing은 헤드리스/자동화 브라우저의 xauth 로그인을 Akamai로 차단함
(navigator.webdriver·CDP포트·Chrome for Testing 지문 감지). 무인 재로그인이 계속 실패.
→ 대표님이 평소 쓰는 일반 크롬은 "사람 지문"이라 로그인이 살아있음.
   그 쿠키를 browser_cookie3로 읽어와 CDP 크롬 컨텍스트에 주입하면 로그인 대체.
(네이버 GFA에서 검증된 방식 — naver_ad_to_sheet.py 참조. 2026-07-12 쿠팡 Wing 적용)

사용:
  단독 실행(쿠키 갱신+백업): python3 gross_cookie_bridge.py
  코드에서:               from gross_cookie_bridge import refresh_from_user_chrome
"""
import json, sys
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"
COOKIE_BACKUP = "/Users/macmini_ky/ClaudeAITeam/automation/gross_session_cookies.json"


def _read_user_chrome_cookies():
    """대표님 평소 크롬에서 쿠팡 쿠키를 읽어 playwright add_cookies 형식으로 변환."""
    import browser_cookie3
    out, seen = [], set()
    for dom in ("coupang.com",):  # .coupang.com 하위 전부 포함됨
        cj = browser_cookie3.chrome(domain_name=dom)
        for c in cj:
            key = (c.name, c.domain, c.path)
            if key in seen:
                continue
            seen.add(key)
            ck = {
                "name": c.name,
                "value": c.value,
                "domain": c.domain if c.domain.startswith(".") else c.domain,
                "path": c.path or "/",
                "httpOnly": bool(getattr(c, "_rest", {}).get("HttpOnly", False)),
                "secure": bool(c.secure),
                "sameSite": "Lax",  # playwright는 Strict/Lax/None만 허용 — 안전값
            }
            # 세션 쿠키(expires None)는 expires 생략, 있으면 정수로
            if c.expires:
                ck["expires"] = float(c.expires)
            out.append(ck)
    return out


def refresh_from_user_chrome(verbose=True):
    """대표님 크롬 쿠키 → CDP 크롬 주입 + 백업파일 갱신. 성공 시 True."""
    cookies = _read_user_chrome_cookies()
    wing = [c for c in cookies if "coupang" in c["domain"]]
    if verbose:
        print(f"  [브릿지] 대표님 크롬에서 쿠팡 쿠키 {len(cookies)}개 읽음")
    # 로그인 핵심 쿠키 확인
    names = {c["name"] for c in cookies}
    if not (names & {"JSESSIONID", "CGSID_PARTNERADMINWEB", "sxSessionId"}):
        print("  [브릿지] ⚠️ Wing 로그인 세션 쿠키 없음 — 대표님 크롬에 Wing 로그인 필요")
        return False

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=30000)
        ctx = b.contexts[0]
        # add_cookies는 sameSite/expires 형식 엄격 → 개별 시도로 나쁜 항목만 스킵
        ok = 0
        for c in cookies:
            try:
                ctx.add_cookies([c]); ok += 1
            except Exception:
                pass
        if verbose:
            print(f"  [브릿지] CDP 크롬에 {ok}/{len(cookies)}개 주입")
        # 주입 후 컨텍스트 쿠키를 백업파일에 저장(다음 무인 실행용)
        json.dump(ctx.cookies(), open(COOKIE_BACKUP, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    if verbose:
        print("  [브릿지] ✅ 백업파일 갱신 완료")
    return True


if __name__ == "__main__":
    try:
        ok = refresh_from_user_chrome()
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"  [브릿지] ❌ 실패: {type(e).__name__}: {e}")
        sys.exit(1)
