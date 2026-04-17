"""살림박스 훅 수동 교체 (오타 영상 제목 대신 다른 영상으로)."""
import sys
import gspread
from google.oauth2.service_account import Credentials
sys.stdout.reconfigure(encoding="utf-8")

KEY_PATH = r"C:\Users\info\claudeaiteam\sourcing\analyzer\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"

creds = Credentials.from_service_account_file(KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)
ws = sh.worksheet("후보 리스트")

NEW_HOOK = "특히 '스트레스 확 줄여준 꿀템 3가지' 영상 같은 실생활 꿀템 추천 스타일이 저희 제품과 잘 어울릴 것 같아요."

# 살림박스 Row11, N열
ws.update(values=[[NEW_HOOK]], range_name="N11")
print(f"Row11 (살림박스) N열 훅 교체 완료:")
print(f"  {NEW_HOOK}")
