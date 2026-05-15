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
print("HEADER:", rows[0][:14])
print()
for i, row in enumerate(rows[1:], 2):
    if len(row) > 0 and row[0]:
        name = row[0][:15]
        I = row[8] if len(row) > 8 else ""   # 상태
        J = row[9] if len(row) > 9 else ""   # 승인
        K = row[10] if len(row) > 10 else ""  # 메모
        L = row[11] if len(row) > 11 else ""  # channel_id
        print(f"Row{i}: A={name:<15} I(상태)={I:<15} J(승인)={J:<10} K(메모)={K[:20]:<20} L(ch_id)={L[:30]}")
