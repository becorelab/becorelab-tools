#!/usr/bin/env python3
"""
알리바바 자동 채팅봇 — 상대 답장 감지 → headless Claude 판단 → 자동 재답장
(2026-07-06 페이블 하치 구축. 레나 승인모드의 후속 — 무인 신뢰모드)

동작 (launchd 5분 주기, 1회 실행-종료):
1. CDP(9222)로 message.alibaba.com 인박스 스캔
2. 대화별 최신 메시지 해시를 state.json과 비교 → 새 '상대' 메시지만 처리
3. brain.py(claude -p)가 답장/스킵/에스컬레이션 결정
4. 답장이면 번역모드 입력창(readOnly 아닌 textarea)에 타이핑→검증→전송→전송확인
5. 모든 액션 텔레그램 통지, 에스컬레이션은 즉시 대표님 호출

안전장치:
- 첫 실행 = 베이스라인만 기록 (과거 밀린 메시지에 답장 폭탄 방지)
- 마지막 발화가 우리(item-right)면 스킵 (자문자답/루프 방지)
- 대화당 하루 3회, 전체 하루 12회 전송 상한
- 23:00~07:30 콰이어트아워 스킵
- DRY_RUN=1 이면 전송 없이 초안만 텔레그램
- 락파일로 중복 실행 방지
"""
import json
import os
import re
import sys
import time
import hashlib
import fcntl
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
from brain import decide  # noqa: E402
from notify import tg_send  # noqa: E402

CDP_URL = "http://localhost:9222"
STATE_FILE = DIR / "state.json"
LOCK_FILE = DIR / ".bot.lock"
LOG_DIR = DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
QUIET_START, QUIET_END = 23, 7.5   # 23:00~07:30 스킵
MAX_PER_CONV_PER_DAY = 3
MAX_TOTAL_PER_DAY = 12
TOP_N_CONVERSATIONS = 15
BUBBLE_CONTEXT = 14                # brain에 넘길 최근 버블 수


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"conversations": {}, "daily": {}}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def today_key():
    return datetime.now().strftime("%Y-%m-%d")


def conv_key(name, company):
    return hashlib.md5(f"{name}|{company}".encode()).hexdigest()[:12]


def in_quiet_hours():
    h = datetime.now().hour + datetime.now().minute / 60
    return h >= QUIET_START or h < QUIET_END


def scan_inbox(page):
    """대화 목록 파싱 → [{name, company, preview, unread, el_index}]"""
    items = page.query_selector_all(".contact-item-container")
    out = []
    for i, it in enumerate(items[:TOP_N_CONVERSATIONS]):
        try:
            raw = (it.inner_text() or "").strip()
            lines = [l.strip() for l in raw.split("\n") if l.strip()]
            unread_el = it.query_selector(".unread-num")
            unread = int(unread_el.inner_text().strip()) if unread_el and unread_el.inner_text().strip().isdigit() else 0
            # 형식: [아바타글자] [배지] 이름 / 시각 / 회사 / 미리보기...
            # 이름 = 시각(HH:MM 또는 날짜) 바로 앞 줄
            name, company, preview = "", "", ""
            for j, l in enumerate(lines):
                if re.match(r"^\d{1,2}:\d{2}$|^\d{4}-\d{1,2}-\d{1,2}$", l):
                    name = lines[j - 1] if j >= 1 else ""
                    company = lines[j + 1] if j + 1 < len(lines) else ""
                    preview = " ".join(lines[j + 2:])[:200]
                    break
            if not name:
                continue
            out.append({"name": name, "company": company, "preview": preview,
                        "unread": unread, "index": i})
        except Exception as e:
            log(f"  ⚠️ 목록 파싱 실패({i}): {e}")
    return out


def open_conversation(page, index):
    items = page.query_selector_all(".contact-item-container")
    if index >= len(items):
        return False
    items[index].click()
    time.sleep(4)
    return True


def read_bubbles(page):
    """열린 대화의 메시지 버블 → [{side: 'us'|'them', text}] (시간순)
    ⚠️ DOM 순서는 버추얼 스크롤 때문에 시간순이 아님 — 화면 y좌표로 정렬해야 함 (2026-07-06 실측)"""
    rows = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('.message-item-wrapper').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.height > 0) {
          const cls = el.className || '';
          out.push({y: r.y,
                    side: cls.includes('item-right') ? 'us' : (cls.includes('item-left') ? 'them' : '?'),
                    text: (el.innerText || '').trim().slice(0, 600)});
        }
      });
      out.sort((a, b) => a.y - b.y);
      return out;
    }""")
    return [{"side": r["side"], "text": r["text"]} for r in rows if r["text"]]


def find_input_box(page):
    """쓰기 가능한 입력창 (번역모드: readOnly 위칸 건너뛰고 아래칸)"""
    for sel in ["textarea", '[contenteditable="true"]', '[role="textbox"]']:
        for el in page.query_selector_all(sel):
            try:
                if not el.is_visible():
                    continue
                if el.evaluate("el => el.readOnly || el.disabled || false"):
                    continue
                return el
            except Exception:
                continue
    return None


def send_reply(page, message):
    """타이핑→반영검증→전송→전송확인. 성공 True"""
    box = find_input_box(page)
    if not box:
        return False, "입력창 못 찾음"
    box.click()
    time.sleep(0.8)
    box.type(message, delay=20)
    time.sleep(1.5)
    typed = box.evaluate("el => el.tagName === 'TEXTAREA' ? el.value : el.innerText")
    if message[:20] not in (typed or ""):
        return False, f"타이핑 미반영 (현재값: {str(typed)[:60]!r})"
    time.sleep(2)  # 번역 반영 대기
    send_btn = None
    for sel in ['button:has-text("Send")', 'button[class*="send"]', '[class*="btn-send"]']:
        el = page.query_selector(sel)
        if el and el.is_visible():
            send_btn = el
            break
    if send_btn:
        send_btn.click()
    else:
        page.keyboard.press("Enter")
    time.sleep(3)
    # 전송 확인: 마지막 버블이 우리 것 + 내용 일부 일치
    bubbles = read_bubbles(page)
    if bubbles and bubbles[-1]["side"] == "us" and message[:15] in bubbles[-1]["text"]:
        return True, "전송 확인됨"
    return True, "전송 클릭됨 (버블 확인은 불확실 — 번역 발송일 수 있음)"


def main():
    # 중복 실행 방지
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("이미 실행 중 — 종료")
        return

    if in_quiet_hours():
        log("콰이어트아워 — 스킵")
        return

    state = load_state()
    day = today_key()
    daily = state["daily"].setdefault(day, {"total_sent": 0})
    first_run = not state["conversations"]

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        page = None
        for pg in ctx.pages:
            if "alibaba" in (pg.url or ""):
                page = pg
                break
        if not page:
            page = ctx.new_page()
        page.goto("https://message.alibaba.com/message/messenger.htm#/",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(6)

        if "login.alibaba.com" in page.url:
            log("❌ 로그인 세션 만료")
            tg_send("🔴 [알리바바봇] 로그인 세션이 만료됐어요. 하치에게 'QR 다시 띄워줘'라고 해주세요!")
            return

        convs = scan_inbox(page)
        log(f"인박스 스캔: {len(convs)}개 대화")

        actions = []
        for c in convs:
            key = conv_key(c["name"], c["company"])
            prev = state["conversations"].get(key, {})
            preview_hash = hashlib.md5(c["preview"].encode()).hexdigest()

            if first_run:
                state["conversations"][key] = {
                    "name": c["name"], "company": c["company"],
                    "last_hash": preview_hash, "sent": {}}
                continue

            if prev.get("last_hash") == preview_hash and c["unread"] == 0:
                continue  # 변화 없음

            # 새 내용 → 대화 열어서 확인
            log(f"변화 감지: {c['name']} ({c['company'][:30]}) unread={c['unread']}")
            if not open_conversation(page, c["index"]):
                continue
            bubbles = read_bubbles(page)
            state["conversations"][key] = {
                "name": c["name"], "company": c["company"],
                "last_hash": preview_hash, "sent": prev.get("sent", {})}

            if not bubbles or bubbles[-1]["side"] != "them":
                log("  마지막 발화가 상대가 아님 → 스킵")
                continue

            sent_today = state["conversations"][key]["sent"].get(day, 0)
            if sent_today >= MAX_PER_CONV_PER_DAY:
                log("  대화별 일일 상한 도달 → 스킵")
                tg_send(f"⚠️ [알리바바봇] {c['name']} 대화 하루 {MAX_PER_CONV_PER_DAY}회 상한 도달 — 직접 확인 필요할 수 있어요")
                continue
            if daily["total_sent"] >= MAX_TOTAL_PER_DAY:
                log("  전체 일일 상한 도달 → 중단")
                break

            transcript = "\n".join(
                f"[{'우리' if b['side'] == 'us' else '상대'}] {b['text']}"
                for b in bubbles[-BUBBLE_CONTEXT:])
            decision = decide(c["name"], c["company"], transcript)
            log(f"  brain 결정: {decision.get('action')} — {decision.get('reason', '')[:80]}")

            if decision.get("action") == "reply" and decision.get("message"):
                msg = decision["message"]
                if DRY_RUN:
                    tg_send(f"📝 [알리바바봇 DRY-RUN] {c['name']} 답장 초안:\n\n{msg}\n\n(전송 안 함)")
                    actions.append(f"초안: {c['name']}")
                else:
                    ok, note = send_reply(page, msg)
                    if ok:
                        state["conversations"][key]["sent"][day] = sent_today + 1
                        daily["total_sent"] += 1
                        tg_send(f"📨 [알리바바봇] {c['name']}({c['company'][:25]})에게 자동 답장:\n\n{msg[:400]}\n\n({note})")
                        actions.append(f"전송: {c['name']}")
                    else:
                        tg_send(f"🔴 [알리바바봇] {c['name']} 답장 전송 실패: {note}")
                        actions.append(f"실패: {c['name']}")
                    log(f"  전송결과: {ok} {note}")
            elif decision.get("action") == "escalate":
                tg_send(f"🙋 [알리바바봇] 대표님 판단 필요 — {c['name']}({c['company'][:25]})\n"
                        f"사유: {decision.get('reason', '')}\n"
                        f"상대 메시지: {bubbles[-1]['text'][:300]}\n"
                        f"제안 초안: {decision.get('message', '(없음)')[:300]}")
                actions.append(f"에스컬레이션: {c['name']}")
            else:
                actions.append(f"스킵: {c['name']}")

            time.sleep(2)

        save_state(state)
        if first_run:
            log(f"✅ 베이스라인 기록 완료 ({len(state['conversations'])}개 대화) — 다음 실행부터 새 메시지에 반응")
        elif actions:
            log("액션: " + ", ".join(actions))
        else:
            log("새 메시지 없음")


if __name__ == "__main__":
    main()
