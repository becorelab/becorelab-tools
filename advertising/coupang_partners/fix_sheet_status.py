"""7개 이미 발송한 행의 I열(상태)을 approved→contacted로 수정."""
import gspread, sys
from google.oauth2.service_account import Credentials
sys.stdout.reconfigure(encoding="utf-8")
KEY_PATH = "/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json"
SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"
creds = Credentials.from_service_account_file(KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)
ws = sh.worksheet("후보 리스트")
rows = ws.get_all_values()
updated = 0
for i, row in enumerate(rows[1:], 2):
    if len(row) > 8 and row[8] == "approved":
        ws.update(values=[["contacted"]], range_name=f"I{i}")
        print(f"  Row{i} {row[0]}: approved → contacted")
        updated += 1
print(f"\n완료: {updated}개 행 수정")
