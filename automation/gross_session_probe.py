#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""그로스 Wing 세션 수명 측정 프로브 (2026-07-20, GPT 하치 제안).
목적: "로그인 후 세션이 정확히 몇 시간 사는지"를 데이터로 측정 → idle만료 vs 절대만료 판별.

- CDP 상주 크롬(9222)에서 Wing 판매분석 페이지를 읽기 전용으로 1회 로드.
- xauth/login 리다이렉트 없으면 ALIVE, 있으면 DEAD.
- 로그인 시각 마커(gross_login_stamp.txt)로부터 경과시간 기록.
- ⚠️ 자동 로그인 POST 절대 안 함 (Akamai 달굼 방지). 읽기만.

판별:
- 활동(프로브)을 계속 하는데도 일정 세션나이에 죽으면 → absolute max-age
- 활동 간격 벌어질 때만(밤 공백) 죽으면 → idle timeout (keepalive로 무한연장 가능)

크론: 1시간 간격 권장. 로그: logs/gross_session_probe.log
마커 갱신: 대표님 로그인 성공 시 gross_cookie_bridge/relogin이 stamp 갱신하면 정확도↑ (현재는 수동 --stamp).
"""
import sys, os, time
from datetime import datetime
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"
SALES_URL = "https://wing.coupang.com/tenants/business-insight/sales-analysis"
BASE = os.path.dirname(os.path.abspath(__file__))
STAMP = os.path.join(BASE, "gross_login_stamp.txt")
LOG = os.path.join(BASE, "logs", "gross_session_probe.log")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _login_age_hours():
    try:
        t0 = float(open(STAMP).read().strip())
        return (time.time() - t0) / 3600
    except Exception:
        return None


def set_stamp():
    open(STAMP, "w").write(str(time.time()))
    print(f"로그인 시각 마커 갱신: {_now()}")


def probe():
    age = _login_age_hours()
    age_str = f"{age:.1f}h" if age is not None else "?(마커없음)"
    status, url = "DEAD", ""
    # ⭐ 세션 갱신 = 실제 매출 조회 (2026-07-21, 대표님 관찰: goto 아니라 진짜 업무 동작이 세션 연장).
    #    coupang_gross_daily.fetch_options_for가 vi-detail-search(인증 매출 API)를 실제 호출 → 세션 활동.
    #    ①먼저 goto로 살았나 확인 → ②살았으면 실제 조회로 세션 갱신(ALIVE+).
    try:
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(CDP_URL, timeout=20000)
            ctx = b.contexts[0]
            pg = ctx.new_page()
            pg.goto(SALES_URL, wait_until="domcontentloaded", timeout=45000)
            url = pg.url
            alive = not ("xauth" in url or "login" in url.lower())
            pg.close()
    except Exception as e:
        alive = False; url = f"err:{str(e)[:40]}"
    if alive:
        status = "ALIVE"
        try:
            from datetime import date, timedelta
            import coupang_gross_daily as _cg
            yday = (date.today() - timedelta(days=1)).isoformat()
            rows = _cg.fetch_options_for(yday)   # 실제 vi-detail-search 조회 = 세션 활동
            if rows is not None:
                status = "ALIVE+"; url = f"조회옵션={len(rows)}"
        except Exception as e:
            url = f"조회err:{str(e)[:35]}"  # 페이지는 살았는데 조회 실패
    line = f"{_now()} {status} 로그인후={age_str} {url[:60]}\n"
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    open(LOG, "a").write(line)
    print(line.strip())
    return status


if __name__ == "__main__":
    if "--stamp" in sys.argv:
        set_stamp()
    else:
        probe()
