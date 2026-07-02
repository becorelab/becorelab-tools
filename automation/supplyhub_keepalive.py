#!/usr/bin/env python3
"""서플라이허브 세션 keepalive — KEYCLOAK idle 만료 전 주기적 활동으로 세션 연장 실험/유지

배경 (2026-07-02, 세션노트 2026-06-16 옵션 B 실행):
- Akamai는 '로그인 POST'만 차단. 로그인된 세션의 페이지 로드는 자유 (그로스/스크레이퍼가 매일 증명).
- KEYCLOAK SSO ~12h 만료가 idle(활동 없음) 기반이면 → 3시간 주기 페이지 로드로 무한 연장 가능(완전 무인화).
- 절대만료(max)라면 연장 불가 → 이 로그가 정확한 수명 데이터를 남김 (가설 검증용).

동작: 9223 전용크롬에서 입고상세 페이지 1회 로드 → 세션 검증 →
  OK      : 쿠키 재백업(sh_at 갱신분 저장) + 로그 + 만료마커 제거
  만료     : 백업쿠키 주입 1회 재시도 → 복구되면 RESTORED
  최종만료 : 마커 없으면 텔레그램 알림 1회(에피소드당 1회, 도배 방지) + 마커 생성

launchd: com.becorelab.supplyhub-keepalive (1,4,7,10,13,16,19,22시 15분 — 8시 수집크론 직전 7:15 보장)
로그: automation/logs/supplyhub_keepalive.log — "OK 스트릭 > 12h"가 나오면 idle 가설 입증.
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/logistics")
sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
from supplyhub_scraper import (CDP_URL, COOKIE_BACKUP, DETAIL_URL,
                               _clean_cookies, _session_ok)

try:
    from alert import alert
except Exception:
    def alert(*a, **k):
        pass

EXPIRED_MARKER = "/Users/macmini_ky/ClaudeAITeam/automation/.supplyhub_expired"
LOG = "/Users/macmini_ky/ClaudeAITeam/automation/logs/supplyhub_keepalive.log"


def _log(msg):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _sh_at_fp(cookies):
    """sh_at 값 지문 — 값이 바뀌면 무클릭 토큰 갱신이 일어났다는 증거 (idle 가설 데이터)"""
    for c in cookies:
        if c.get("name") == "sh_at":
            return hashlib.sha1(c.get("value", "").encode()).hexdigest()[:10]
    return "-"


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.connect_over_cdp(CDP_URL, timeout=30000)
        ctx = br.contexts[0]
        pg = ctx.new_page()
        pg.set_default_timeout(60000)
        try:
            pg.goto(DETAIL_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
            status = "OK" if _session_ok(pg) else None

            if not status:
                # 백업쿠키 주입 1회 재시도 (스크레이퍼와 동일 패턴)
                pg.close()
                if os.path.exists(COOKIE_BACKUP):
                    try:
                        with open(COOKIE_BACKUP, encoding="utf-8") as f:
                            ctx.add_cookies(_clean_cookies(json.load(f)))
                    except Exception as e:
                        _log(f"백업쿠키 주입 실패: {e}")
                pg = ctx.new_page()
                pg.set_default_timeout(60000)
                pg.goto(DETAIL_URL, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)
                status = "RESTORED" if _session_ok(pg) else "EXPIRED"

            if status in ("OK", "RESTORED"):
                cookies = ctx.cookies()
                with open(COOKIE_BACKUP, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                _log(f"{status} sh_at={_sh_at_fp(cookies)} (쿠키 {len(cookies)}개 재백업)")
                if os.path.exists(EXPIRED_MARKER):
                    os.remove(EXPIRED_MARKER)
            else:
                _log("EXPIRED — 세션·백업쿠키 모두 만료")
                if not os.path.exists(EXPIRED_MARKER):
                    alert("서플라이허브 keepalive",
                          "서플라이허브 세션이 풀렸어요. 편하실 때 "
                          "python3 ClaudeAITeam/automation/supplyhub_relogin.py 로 "
                          "한 번만 로그인해 주시면 로켓 매출까지 바로 채워둘게요!",
                          "warn")
                    open(EXPIRED_MARKER, "w").write(datetime.now().isoformat())
        finally:
            try:
                pg.close()  # 탭만 닫기 — 상주 크롬 유지
            except Exception:
                pass


if __name__ == "__main__":
    main()
