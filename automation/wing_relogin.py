#!/usr/bin/env python3
"""Wing(그로스) 세션 재로그인 — 대표님 headful 1회 로그인 → 상주 크롬에 세션 주입

supplyhub_relogin.py와 같은 패턴 (2026-06-11 검증):
- 상주 9222 크롬 중단 없음 (gross_relogin.sh의 bootout 방식 대체)
- 임시 프로필 headful 크롬에서 대표님이 채움컴퍼니 Wing 로그인
- 쿠키 DB 폴링(sxSessionId 생성)으로 감지 → mock_password 복호화 수확
- gross_session_cookies.json 백업 + 상주 크롬 주입 (Akamai 쿠키 제외)
※ 임시 프로필은 supplyhub와 분리(ChromeWingTmp) — xauth SSO 계정 충돌 방지

사용: python3 automation/wing_relogin.py
"""
import json
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/logistics")
from supplyhub_scraper import CDP_URL, _clean_cookies
from playwright.sync_api import sync_playwright

TMP_PROFILE = "/Users/macmini_ky/ChromeWingTmp"
COOKIE_DB = f"{TMP_PROFILE}/Default/Cookies"
COOKIE_DB_COPY = "/tmp/wing_relogin_cookies.db"
COOKIE_BACKUP = "/Users/macmini_ky/ClaudeAITeam/automation/gross_session_cookies.json"
SALES_URL = "https://wing.coupang.com/tenants/business-insight/sales-analysis"
LOGIN_WAIT_SEC = 3600
SESSION_COOKIE = "sxSessionId"  # 이게 생기면 Wing 로그인 완료


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
    if len(out) > 32 and not all(32 <= b < 127 for b in out[:8]):
        out = out[32:]
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _db_rows():
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
        b = p.chromium.launch_persistent_context(
            TMP_PROFILE, headless=False, channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1400, "height": 900},
            locale="ko-KR", timezone_id="Asia/Seoul")
        pg = b.pages[0] if b.pages else b.new_page()
        pg.goto(SALES_URL, wait_until="domcontentloaded", timeout=60000)
        start = time.time()
        print(f"👉 뜬 크롬에서 채움컴퍼니 Wing 로그인하세요. "
              f"(쿠키 DB 자동 감지, 최대 {LOGIN_WAIT_SEC//60}분)", flush=True)

        start_chrome_epoch = (start + 11644473600) * 1000000
        ok = False
        while time.time() - start < LOGIN_WAIT_SEC:
            time.sleep(5)
            if any(r[1] == SESSION_COOKIE and r[10] > start_chrome_epoch
                   for r in _db_rows()):
                ok = True
                break
        if not ok:
            print("❌ 로그인 감지 실패(시간초과). 다시 실행해 주세요.", flush=True)
            b.close()
            sys.exit(1)

        time.sleep(5)
        cookies = harvest_cookies()
        with open(COOKIE_BACKUP, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"✅ 로그인 감지. 쿠키 {len(cookies)}개 수확 → {COOKIE_BACKUP}", flush=True)
        b.close()

        # 상주 CDP 크롬에 주입 + 검증
        br = p.chromium.connect_over_cdp(CDP_URL, timeout=30000)
        ctx = br.contexts[0]
        ctx.add_cookies(_clean_cookies(cookies))
        vp = ctx.new_page()
        vp.goto(SALES_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(6)
        if "xauth" not in vp.url and "login" not in vp.url.lower() \
                and "Access Denied" not in vp.inner_text("body"):
            print("✅ 상주 크롬 Wing 세션 검증 OK — 9:30 그로스 크론 복구!", flush=True)
        else:
            print(f"⚠️ 상주 크롬 검증 실패 (URL={vp.url[:60]})", flush=True)
        vp.close()


if __name__ == "__main__":
    main()
