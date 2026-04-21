"""기존 승인대기/승인 행들에 personal_hook 재생성.

실제 시트 L열(channel_id)을 보고 enrich_full()로 최근 영상 재수집 →
Haiku 재스크리닝 → personal_hook만 N열에 업데이트.

비용: 6명 × Haiku 호출 ~= $0.01 미만.
"""
import os, sys, json, time
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(os.path.join(_DIR, "..", "..", "sourcing", "analyzer", ".env"))

import gspread
from google.oauth2.service_account import Credentials
from youtube_crawler import enrich_full
from screener import screen_channel

KEY_PATH = r"C:\Users\User\claudeaiteam\sourcing\analyzer\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"

creds = Credentials.from_service_account_file(KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)
ws = sh.worksheet("후보 리스트")

# N열 헤더 설정
try:
    current_n1 = ws.acell("N1").value or ""
except Exception:
    current_n1 = ""
if current_n1 != "개인화 훅":
    ws.update(values=[["개인화 훅"]], range_name="N1")
    print("  N1 헤더 설정: 개인화 훅")

rows = ws.get_all_values()
print(f"총 {len(rows)-1}개 행 로드\n")

targets = []
for i, row in enumerate(rows[1:], 2):
    if len(row) < 12 or not row[0]:
        continue
    name = row[0]
    channel_id = row[11]
    current_hook = row[13] if len(row) > 13 else ""
    approval = row[9] if len(row) > 9 else ""
    status = row[8] if len(row) > 8 else ""
    # 아직 hook 없고 승인된 행만 (발송 대기 or 발송 완료도 일단 채움 — 향후 재컨택 시 활용)
    if channel_id and not current_hook and approval in ("승인", "approved"):
        targets.append((i, name, channel_id, status))

print(f"재스크리닝 대상: {len(targets)}명")
for i, name, cid, status in targets:
    print(f"  Row{i} [{status}] {name} ({cid})")

print()
for i, name, cid, status in targets:
    print(f"[{i}] {name} 처리 중...")
    try:
        ch = enrich_full(cid)
        screen = screen_channel(ch)
        hook = screen.get("personal_hook", "")
        print(f"    훅: {hook or '(비어있음)'}")
        ws.update(values=[[hook]], range_name=f"N{i}")
        time.sleep(0.5)  # API 레이트리밋 여유
    except Exception as e:
        print(f"    실패: {e}")

print(f"\n완료!")
