"""메일 템플릿 시트 업데이트 — pipeline.py의 TEMPLATES를 그대로 반영."""
import gspread, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.oauth2.service_account import Credentials
sys.stdout.reconfigure(encoding="utf-8")

# pipeline.py의 템플릿을 그대로 가져와서 싱글 소스로 유지
from pipeline import TEMPLATES

KEY_PATH = r"C:\Users\User\claudeaiteam\sourcing\analyzer\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"

creds = Credentials.from_service_account_file(KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)

TARGETS = {
    "A": "살림/생활/청소 채널",
    "B": "육아/아기/반려 채널",
    "C": "기타 (쿠팡 추천/리뷰 채널)",
}

try:
    ws = sh.worksheet("메일 템플릿")
    sh.del_worksheet(ws)
except Exception:
    pass
ws = sh.add_worksheet(title="메일 템플릿", rows=60, cols=4)

rows = [["타입", "타겟 채널", "제목", "본문"]]
for ttype in ["A", "B", "C"]:
    tpl = TEMPLATES[ttype]
    rows.append([ttype, TARGETS[ttype], tpl["subject"], tpl["body"]])

ws.update(values=rows, range_name="A1:D4", value_input_option="RAW")

ws.format("A1:D1", {
    "backgroundColor": {"red": 0.22, "green": 0.33, "blue": 0.53},
    "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
    "horizontalAlignment": "CENTER",
})
ws.format("D2:D4", {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"})
ws.format("A2:C4", {"verticalAlignment": "TOP"})

requests_body = {"requests": [
    {"updateDimensionProperties": {
        "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 60}, "fields": "pixelSize"
    }},
    {"updateDimensionProperties": {
        "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 180}, "fields": "pixelSize"
    }},
    {"updateDimensionProperties": {
        "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3},
        "properties": {"pixelSize": 340}, "fields": "pixelSize"
    }},
    {"updateDimensionProperties": {
        "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 4},
        "properties": {"pixelSize": 560}, "fields": "pixelSize"
    }},
    {"updateDimensionProperties": {
        "range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": 1, "endIndex": 4},
        "properties": {"pixelSize": 360}, "fields": "pixelSize"
    }},
]}
sh.batch_update(requests_body)

print("메일 템플릿 시트 업데이트 완료!")
for ttype in ["A", "B", "C"]:
    print(f"  타입 {ttype} ({TARGETS[ttype]}): {TEMPLATES[ttype]['subject']}")
