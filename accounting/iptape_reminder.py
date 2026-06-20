# -*- coding: utf-8 -*-
"""6/23 입테이프 입고일 리마인더 — 두리 봇으로 대표님께 텔레그램 발송 후 자기 cron 제거 (1회성)."""
import os, json, urllib.request, urllib.parse, subprocess

BASE = os.path.expanduser("~/.claude/channels/telegram-doori")
token = None
for line in open(f"{BASE}/.env"):
    if line.startswith("TELEGRAM_BOT_TOKEN="):
        token = line.split("=", 1)[1].strip()
chat = json.load(open(f"{BASE}/access.json"))["allowFrom"][0]

msg = (
    "대표님~ 🐰 입테이프 입고일이에요! 📦\n\n"
    "오늘 입고되면 **입테이프 옵션가를 '1개입이 돋보이는 구조'로 다시 짜셔야 해요.**\n\n"
    "📌 왜냐면 (6월 정산 분석 결론):\n"
    "• 입테이프는 실판매가 1개입 중심이에요 (수량·매출 1위, 마진율 24.2%)\n"
    "• 큰 번들(5·6개입)은 광고 유입 '미끼'일 뿐, 실구매는 1개입으로 교차전환돼요\n"
    "• 그래서 번들 가격을 올리는 건 역효과 (미끼 약화 → 유입↓)\n\n"
    "✅ 방향: 가격은 동결하고, **1개입을 전면 노출·광고로 밀어서** 판매 믹스를 1개입으로 옮기기\n"
    "   → 1개입 마진율이 높아 믹스가 쏠리면 전체 마진이 자동 개선돼요 💕\n\n"
    "입고 확인하시고 옵션가 재설계 진행해 주세요~!"
)

url = f"https://api.telegram.org/bot{token}/sendMessage"
data = urllib.parse.urlencode({"chat_id": chat, "text": msg, "parse_mode": "Markdown"}).encode()
try:
    r = urllib.request.urlopen(url, data=data, timeout=20)
    print("sent:", r.status)
except Exception as e:
    print("send error:", e)
    raise

# 발송 성공 시 launchd 잡 자기제거 (1회성)
subprocess.run(
    "launchctl unload ~/Library/LaunchAgents/com.becorelab.iptape-reminder.plist 2>/dev/null; "
    "rm -f ~/Library/LaunchAgents/com.becorelab.iptape-reminder.plist",
    shell=True,
)
print("launchd job removed")
