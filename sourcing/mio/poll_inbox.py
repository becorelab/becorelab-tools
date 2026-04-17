"""
알리바바 인박스 온디맨드 폴링
대표님 지시 시 실행 → 스냅샷 비교 → 변경 감지 → 보고 → 자동 종료
"""

import sys
import os
import io
import json
import time
import hashlib
import argparse
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)
sys.path.insert(0, os.path.dirname(__file__))

from playwright.sync_api import sync_playwright

CDP_URL = "http://localhost:9222"
SNAPSHOT_FILE = os.path.join(os.path.dirname(__file__), "inbox_snapshot.json")


def _take_snapshot() -> dict:
    """인박스 페이지 열어서 raw text 스냅샷 반환. 별도 탭 열고 닫음."""
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        try:
            page.goto('https://message.alibaba.com/',
                      wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)
            text = page.inner_text('body')
            url = page.url
        finally:
            page.close()

    if len(text.strip()) < 50:
        return {"error": "페이지 로딩 실패 또는 로그인 필요", "text": text[:500]}

    return {
        "success": True,
        "url": url,
        "text": text[:8000],
        "hash": hashlib.md5(text[:8000].encode()).hexdigest(),
        "timestamp": datetime.now().isoformat(),
    }


def _extract_conversations(text: str) -> list[str]:
    """raw text에서 대화 항목 추출 (줄 단위, 빈 줄 구분)"""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return lines


def _diff_snapshots(baseline: dict, current: dict) -> dict:
    """두 스냅샷 비교 → 변경 내용 반환"""
    if baseline.get("hash") == current.get("hash"):
        return {"changed": False}

    old_lines = set(_extract_conversations(baseline.get("text", "")))
    new_lines = set(_extract_conversations(current.get("text", "")))

    added = new_lines - old_lines
    removed = old_lines - new_lines

    return {
        "changed": True,
        "added_lines": len(added),
        "removed_lines": len(removed),
        "sample_new": list(added)[:20],
    }


def _save_snapshot(snapshot: dict):
    with open(SNAPSHOT_FILE, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def _load_snapshot() -> dict | None:
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def poll(duration_min: int = 90, interval_min: int = 10):
    """온디맨드 폴링 메인 루프"""
    end_time = datetime.now() + timedelta(minutes=duration_min)
    print(f"📬 인박스 폴링 시작 — {duration_min}분간, {interval_min}분 간격")
    print(f"   종료 예정: {end_time.strftime('%H:%M')}")

    # 베이스라인 스냅샷
    print("\n📸 베이스라인 스냅샷 촬영 중...")
    baseline = _take_snapshot()
    if "error" in baseline:
        print(f"❌ {baseline['error']}")
        return
    _save_snapshot(baseline)
    print(f"✅ 베이스라인 저장 (hash: {baseline['hash'][:8]})")

    check_count = 0
    while datetime.now() < end_time:
        wait_sec = interval_min * 60
        remaining = (end_time - datetime.now()).total_seconds()
        if wait_sec > remaining:
            wait_sec = max(int(remaining), 0)
            if wait_sec <= 0:
                break

        print(f"\n⏳ {interval_min}분 대기 중... (남은 시간: {int(remaining/60)}분)")
        time.sleep(wait_sec)

        check_count += 1
        print(f"\n🔍 체크 #{check_count} ({datetime.now().strftime('%H:%M:%S')})")

        current = _take_snapshot()
        if "error" in current:
            print(f"⚠️ 스냅샷 실패: {current['error']}")
            continue

        diff = _diff_snapshots(baseline, current)
        if diff["changed"]:
            print(f"🔔 변경 감지! 새 라인 {diff['added_lines']}개")
            for line in diff["sample_new"][:10]:
                if len(line) > 10:
                    print(f"   → {line[:120]}")
            _save_snapshot(current)
            baseline = current
        else:
            print("   변경 없음")

    print(f"\n⏰ 폴링 종료 (총 {check_count}회 체크)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="알리바바 인박스 온디맨드 폴링")
    parser.add_argument("--duration", type=int, default=90, help="폴링 지속 시간(분)")
    parser.add_argument("--interval", type=int, default=10, help="체크 간격(분)")
    args = parser.parse_args()
    poll(duration_min=args.duration, interval_min=args.interval)
