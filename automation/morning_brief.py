"""
비코어랩 모닝 브리핑 전송 스크립트
- Windows 작업 스케줄러에서 매일 05:40에 실행
- morning_data.json(골드박스/API비용) + 실시간 API(매출/재고/발주) 조합
- 재고 데이터 빈 경우 최대 3회 재시도
- 오픈클로/보리 없이 직접 텔레그램 전송
"""
import json
import os
import sys
import time
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    OUTPUT_JSON, DATA_DIR,
)

BASE_LOGISTICS = "http://localhost:8082"
BRIEF_LOG = os.path.join(DATA_DIR, "morning_brief.log")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts} {msg}"
    print(line)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BRIEF_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=15,
        )
        if resp.status_code == 200:
            log("텔레그램 전송 완료")
        else:
            log(f"텔레그램 실패: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        log(f"텔레그램 전송 오류: {e}")


def fetch_text(path, retries=3, delay=30):
    """텍스트 API 호출 (빈 응답 시 재시도)"""
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(f"{BASE_LOGISTICS}{path}", timeout=20)
            text = r.text.strip() if r.status_code == 200 else ""
            # 헤더만 있는 빈 응답 감지
            lines = [l for l in text.splitlines() if l.strip()]
            if len(lines) >= 2:
                log(f"  {path}: OK (시도 {attempt}회)")
                return text
            else:
                log(f"  {path}: 데이터 없음 (시도 {attempt}/{retries}) — {delay}초 후 재시도")
        except Exception as e:
            log(f"  {path}: 오류 (시도 {attempt}/{retries}) — {e}")
        if attempt < retries:
            time.sleep(delay)
    log(f"  {path}: {retries}회 시도 후 실패, 빈 데이터로 진행")
    return ""


def load_morning_json():
    """morning_collect.py가 저장한 JSON (골드박스·API비용용)"""
    try:
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"morning_data.json 로드 실패: {e}")
        return {}


def format_goldbox(top3):
    if not top3:
        return "스캔 결과 없음"
    lines = []
    for i, item in enumerate(top3, 1):
        kw = item.get("keyword", "?")
        score = item.get("opportunity_score", 0)
        lines.append(f"{i}. {kw} ({score}점)")
    return "\n".join(lines)


def format_api_costs(costs):
    if not costs:
        return "데이터 없음"
    deepseek = costs.get("deepseek", {})
    if isinstance(deepseek, dict):
        balance_infos = deepseek.get("balance_infos", [])
        ds_balance = balance_infos[0].get("total_balance", "?") if balance_infos else "?"
        ds_str = f"DeepSeek: ${ds_balance}"
    else:
        ds_str = f"DeepSeek: {deepseek}"
    return "\n".join([
        "Z.AI: $10 정액",
        ds_str,
        "Anthropic: Max plan",
    ])


def build_message(daily_report, inventory, order_analysis, morning_data):
    now = datetime.now()
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekdays[now.weekday()]
    date_str = now.strftime(f"%m월 %d일 {weekday}요일")

    goldbox_str = format_goldbox(morning_data.get("goldbox_top3", []))
    api_costs_str = format_api_costs(morning_data.get("api_costs", {}))

    # 섹션별 조합
    sections = [
        f"🌾 비코어랩 데일리 브리핑 ({date_str})",
        "대표님 모닝~! 하치가 정리해드릴게요!\n",
    ]

    # 매출
    sections.append("💵 매출")
    if daily_report:
        sections.append(daily_report)
    else:
        sections.append("데이터 수집 실패 — 서버 확인 필요")

    # 재고
    sections.append("\n📦 주력 제품 재고")
    if inventory:
        sections.append(inventory)
    else:
        sections.append("⚠️ 재고 데이터 없음 — 서버 확인 필요")

    # 발주
    sections.append("\n🔁 발주 리마인드")
    if order_analysis:
        sections.append(order_analysis)
    else:
        sections.append("⚠️ 발주 데이터 없음")

    # 골드박스
    sections.append("\n🎁 골드박스 TOP 3")
    sections.append(goldbox_str)

    # API 비용
    sections.append("\n💰 API 비용 (이번달)")
    sections.append(api_costs_str)

    # 에러 알림
    errors = morning_data.get("errors", [])
    server_status = morning_data.get("server_status", {})
    failed_servers = [k for k, v in server_status.items() if v == "failed"]
    if failed_servers or errors:
        sections.append("\n⚠️ 새벽 자동화 이슈")
        for s in failed_servers:
            sections.append(f"- {s} 복구 실패")
        for e in errors[:3]:
            sections.append(f"- {e}")

    sections.append("\n이상! 오늘도 화이팅~! 🌾")
    return "\n".join(sections)


def main():
    log("=" * 40)
    log(f"모닝 브리핑 시작 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")

    # 1. morning_data.json 로드 (골드박스·API비용)
    morning_data = load_morning_json()
    log(f"morning_data 로드: {morning_data.get('timestamp', '없음')}")

    # 2. 실시간 API 호출 (재시도 포함)
    log("매출/재고/발주 API 호출 중...")
    daily_report  = fetch_text("/api/daily-report?format=text", retries=3, delay=30)
    inventory     = fetch_text("/api/inventory-report?format=text", retries=3, delay=30)
    order_analysis = fetch_text("/api/order-analysis?format=text", retries=3, delay=30)

    # 3. 메시지 조합
    message = build_message(daily_report, inventory, order_analysis, morning_data)

    # 4. 텔레그램 전송
    send_telegram(message)

    log("모닝 브리핑 완료")
    log("=" * 40)


if __name__ == "__main__":
    main()
