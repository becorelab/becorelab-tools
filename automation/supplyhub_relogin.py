#!/usr/bin/env python3
"""서플라이허브 세션 재로그인 — 대표님 headful 1회 로그인 → 상주 크롬에 세션 주입

흐름 (상주 9222 크롬 중단 없음, 2026-06-11 검증된 방식):
1. headful 크롬(임시 프로필) 띄움 → 대표님이 supplier.coupang.com 로그인 (becorelab)
2. 쿠키 DB 폴링으로 로그인 감지 (supplierHubSessionId 생성 감지 — 페이지/탭 상태 무관, 신뢰성↑)
   ※ 페이지 URL 폴링은 탭 추적 누락으로 실패한 전적 있음(2026-06-11). DB 폴링이 정답.
3. 쿠키 DB 직접 복호화 수확 (--use-mock-keychain → AES키 = PBKDF2('mock_password','saltysalt',1003))
   ※ 핵심 세션쿠키(supplierHubSessionId, sh_at 등)는 is_persistent=0 — 크롬 닫히면 증발.
     반드시 크롬 살아있을 때 DB에서 수확해야 함.
4. 백업 저장(supplyhub_session_cookies.json) → 상주 CDP 크롬에 주입
   ※ Akamai 쿠키(_abck/bm_*)는 주입 제외 — 상주 크롬(그로스)의 신뢰 쿠키 보존
5. 상주 크롬에서 입고상세 페이지 열어 세션 검증

사용: python3 automation/supplyhub_relogin.py
"""
import json
import os
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/logistics")
from supplyhub_scraper import (CDP_URL, COOKIE_BACKUP, DETAIL_URL,
                               _clean_cookies, _session_ok)
from playwright.sync_api import sync_playwright

TMP_PROFILE = "/Users/macmini_ky/ChromeSupplyhubTmp"
COOKIE_DB = f"{TMP_PROFILE}/Default/Cookies"
COOKIE_DB_COPY = "/tmp/supplyhub_relogin_cookies.db"
LOGIN_WAIT_SEC = 3600
SESSION_COOKIE = "sh_at"  # 서플라이허브 액세스토큰. 쿠팡이 supplierHubSessionId→sh_at/shSessionIdNew로
# 쿠키체계 변경(2026-06-18 확인). sh_at는 로그인마다 갱신돼 '값 변화' 감지에 적합. supplierHubSessionId는
# 잔재로 안 바뀌어 영영 감지 실패하던 버그 → sh_at로 교체.


def _aes_key():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(algorithm=hashes.SHA1(), length=16,
                     salt=b"saltysalt", iterations=1003)
    return kdf.derive(b"mock_password")


def _decrypt(key, blob):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    if not blob or blob[:3] != b"v10":
        return None
    d = Cipher(algorithms.AES(key), modes.CBC(b" " * 16)).decryptor()
    out = d.update(blob[3:]) + d.finalize()
    pad = out[-1]
    if pad < 1 or pad > 16:
        return None
    out = out[:-pad]
    # v24+ DB: 32바이트 host_key SHA256 프리픽스 제거
    if len(out) > 32 and not all(32 <= b < 127 for b in out[:8]):
        out = out[32:]
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _db_rows():
    """크롬 실행 중에도 안전하게 — 복사본으로 조회"""
    try:
        shutil.copy(COOKIE_DB, COOKIE_DB_COPY)
        con = sqlite3.connect(COOKIE_DB_COPY)
        rows = con.execute(
            """SELECT host_key, name, encrypted_value, value, path, is_secure,
                      is_httponly, expires_utc, is_persistent, samesite, creation_utc
               FROM cookies WHERE host_key LIKE '%coupang%'""").fetchall()
        con.close()
        return rows
    except Exception:
        return []


def harvest_cookies():
    key = _aes_key()
    ss_map = {-1: "Lax", 0: "None", 1: "Lax", 2: "Strict"}
    cookies = []
    for host, name, enc, val, path, sec, http, exp, persist, ss, _crt in _db_rows():
        v = val or _decrypt(key, enc)
        if v is None:
            continue
        c = {"name": name, "value": v, "domain": host, "path": path or "/",
             "secure": bool(sec), "httpOnly": bool(http),
             "sameSite": ss_map.get(ss, "Lax")}
        if persist and exp:
            c["expires"] = exp / 1000000 - 11644473600
        cookies.append(c)
    return cookies


def main():
    with sync_playwright() as p:
        # 1) headful 로그인 창
        b = p.chromium.launch_persistent_context(
            TMP_PROFILE, headless=False, channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1400, "height": 900},
            locale="ko-KR", timezone_id="Asia/Seoul")
        pg = b.pages[0] if b.pages else b.new_page()
        pg.goto(DETAIL_URL, wait_until="domcontentloaded", timeout=60000)
        start = time.time()
        print(f"👉 뜬 크롬에서 becorelab 계정으로 로그인하세요. "
              f"(쿠키 DB 자동 감지, 최대 {LOGIN_WAIT_SEC//60}분)", flush=True)

        # 2) 쿠키 DB 폴링 — supplierHubSessionId '값이 바뀌면'(=대표님이 새로 로그인) 감지.
        #    (이전: creation_utc 시각 비교 → 잔존쿠키/타이밍에 감지 실패하던 버그. 값 변화로 견고화)
        def _sess_val():
            for r in _db_rows():
                if r[1] == SESSION_COOKIE:
                    return r[3] or r[2]  # value 또는 encrypted_value (세션마다 다름)
            return None
        # 임시 프로필에 유효 세션이 이미 살아있으면(잔존 로그인) 폴링 생략하고 즉시 수확.
        # ('값 변화' 폴링은 이미 로그인된 상태에선 값이 안 바뀌어 감지 못 하던 함정 — 2026-06-18 케이스)
        time.sleep(3)
        if _session_ok(pg):
            print("✅ 이미 로그인된 유효 세션 감지 — 폴링 생략, 즉시 수확", flush=True)
            ok = True
        else:
            before = _sess_val()
            ok = False
            while time.time() - start < LOGIN_WAIT_SEC:
                time.sleep(5)
                cur = _sess_val()
                if cur and cur != before:
                    ok = True
                    break
        if not ok:
            print("❌ 로그인 감지 실패(시간초과). 다시 실행해 주세요.", flush=True)
            b.close()
            sys.exit(1)

        time.sleep(5)  # 로그인 직후 부가 쿠키(sh_at 등) 안착 대기
        cookies = harvest_cookies()
        with open(COOKIE_BACKUP, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"✅ 로그인 감지. 쿠키 {len(cookies)}개 수확 → {COOKIE_BACKUP}", flush=True)
        b.close()

        # 3) 상주 CDP 크롬에 세션 주입 + 검증
        br = p.chromium.connect_over_cdp(CDP_URL, timeout=30000)
        ctx = br.contexts[0]
        ctx.add_cookies(_clean_cookies(cookies))
        vp = ctx.new_page()
        vp.goto(DETAIL_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(6)
        sess_ok = _session_ok(vp)
        if sess_ok:
            print("✅ 전용 크롬(9223) 세션 검증 OK", flush=True)
        else:
            print("⚠️ 검증 실패 — 수확 쿠키 불완전 가능성. 재로그인 필요.", flush=True)
        vp.close()  # 탭만 닫기 — 전용 크롬 유지

    # 4) 로그인+주입 성공 시 곧바로 로켓 매출 수집 (1클릭 자동화 — 세션 살아있을 때 즉시)
    if sess_ok:
        import subprocess
        print("⏳ 로켓 매출 수집 시작 (로그인 직후 즉시)...", flush=True)
        subprocess.run([sys.executable,
                        os.path.join(os.path.dirname(__file__), "rocket_daily.py")])
    else:
        print("로켓 수집 건너뜀 (세션 검증 실패) — 잠시 후 다시 로그인해 주세요.", flush=True)


if __name__ == "__main__":
    main()
