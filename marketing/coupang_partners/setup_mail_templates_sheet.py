"""구글 시트에 메일 템플릿 시트 추가"""
import sys
import gspread
from google.oauth2.service_account import Credentials

sys.stdout.reconfigure(encoding="utf-8")

KEY_PATH = r"C:\Users\User\claudeaiteam\sourcing\analyzer\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"

creds = Credentials.from_service_account_file(KEY_PATH, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
])
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)

for ws in sh.worksheets():
    if ws.title == "메일 템플릿":
        sh.del_worksheet(ws)
        break

tpl = sh.add_worksheet(title="메일 템플릿", rows=85, cols=4, index=2)
tid = tpl.id

content = [
    [""],
    ["", "📧 협업 제안 메일 템플릿"],
    [""],
    ["", "아래 3가지 타입 중 유튜버 채널 성격에 맞게 AI가 자동 선택합니다."],
    ["", "{채널명}, {추천제품}, {최근영상제목} 등은 AI가 자동으로 치환합니다."],
    [""],
    # ── 타입 A ──
    ["", "TYPE A — 살림/생활 채널 (신제품 체험 제안형)"],
    [""],
    ["", "제목:", "{채널명}님, 구독자분들이 댓글로 물어볼 제품이에요"],
    [""],
    ["", "본문:"],
    ["", "", "{채널명}님 안녕하세요!"],
    ["", "", "쿠팡 건조기 시트 리뷰 7,000개, 패밀리케어 브랜드 iLBiA(일비아)입니다."],
    ["", "", ""],
    ["", "", "{채널명}님 채널 영상 잘 봤어요."],
    ["", "", "댓글에 세탁 꿀팁 물어보시는 분들이 많으시던데,"],
    ["", "", "저희가 이번에 새로 출시한 '캡슐 표백제'가"],
    ["", "", "딱 그 주제로 영상 하나 나올 수 있는 제품이에요."],
    ["", "", ""],
    ["", "", "세탁조에 캡슐 하나 넣기만 하면 끝이라 사용법도 간단하고,"],
    ["", "", "산소계 표백 성분이라 색상 옷도 안전해요."],
    ["", "", "비포/애프터가 확실해서 시청자 반응 좋을 것 같아요."],
    ["", "", ""],
    ["", "", "이 외에도 건조기 시트, 식기세척기 세제, 얼룩 제거제 등"],
    ["", "", "iLBiA 제품 풀세트(5~7만원 상당)를 보내드릴게요."],
    ["", "", ""],
    ["", "", "한번 써보시겠어요?"],
    ["", "", "제품 제공 또는 원고료 등 조건은 편하게 맞춰드릴게요."],
    ["", "", ""],
    ["", "", "비코어랩 마케팅팀"],
    [""],
    # ── 타입 B ──
    ["", "TYPE B — 육아/반려동물 채널 (콘텐츠 아이디어형)"],
    [""],
    ["", "제목:", "{채널명}님 안녕하세요, 영상 소재 하나 제안드려도 될까요?"],
    [""],
    ["", "본문:"],
    ["", "", "{채널명}님 안녕하세요!"],
    ["", "", "쿠팡 건조기 시트 리뷰 7,000개, 패밀리케어 브랜드 iLBiA입니다."],
    ["", "", ""],
    ["", "", "{채널명}님 영상 보면서 \"이 분한테 저희 신제품 보내드리면"],
    ["", "", "진짜 리얼한 후기가 나오겠다\" 싶었어요."],
    ["", "", ""],
    ["", "", "아이(반려동물) 있는 집은 세탁이 전쟁이잖아요."],
    ["", "", "이번에 새로 나온 '캡슐 표백제'가 세탁조에 하나 넣기만 하면 되는 거라"],
    ["", "", "아기 옷 얼룩, 침구류 세탁에 딱이에요."],
    ["", "", "산소계 성분이라 아기 옷에도 안심이고, 비포/애프터 찍으시면 조회수 터질 소재예요."],
    ["", "", ""],
    ["", "", "캡슐 표백제 외에도 건조기 시트, 얼룩 제거제 등"],
    ["", "", "iLBiA 제품 풀세트(5~7만원 상당)를 보내드릴게요."],
    ["", "", ""],
    ["", "", "마음에 안 드시면 영상 안 만드셔도 되고요."],
    ["", "", "제품 제공 또는 원고료 등 조건은 편하게 맞춰드릴게요."],
    ["", "", ""],
    ["", "", "비코어랩 마케팅팀"],
    [""],
    # ── 타입 C ──
    ["", "TYPE C — 추천/리뷰 채널 (도전 제안형)"],
    [""],
    ["", "제목:", "{채널명}님, 신제품 캡슐 표백제 첫 리뷰어 되실래요?"],
    [""],
    ["", "본문:"],
    ["", "", "{채널명}님 안녕하세요!"],
    ["", "", "쿠팡 건조기 시트 리뷰 7,000개, 패밀리케어 브랜드 iLBiA입니다."],
    ["", "", ""],
    ["", "", "{채널명}님이 추천하시는 것들 보면 진짜 써보고 고르신 게 느껴져서"],
    ["", "", "저희 신제품 첫 리뷰를 {채널명}님한테 맡기고 싶었어요."],
    ["", "", ""],
    ["", "", "이번에 새로 출시한 '캡슐 표백제'인데,"],
    ["", "", "세탁조에 캡슐 하나 넣으면 표백 + 세정이 한번에 되는 제품이에요."],
    ["", "", "산소계 성분이라 색상 옷도 OK, 아직 리뷰 영상이 거의 없어서 선점 효과도 있을 거예요."],
    ["", "", ""],
    ["", "", "캡슐 표백제 외에도 건조기 시트, 식기세척기 세제, 얼룩 제거제 등"],
    ["", "", "iLBiA 제품 풀세트(5~7만원 상당)를 함께 보내드릴게요."],
    ["", "", ""],
    ["", "", "제품 제공 또는 원고료 등 조건은 따로 상의해요."],
    ["", "", ""],
    ["", "", "비코어랩 마케팅팀"],
]

tpl.update(values=content, range_name=f"A1:C{len(content)}")

WHITE = {"red": 1, "green": 1, "blue": 1}
DARK = {"red": 0.15, "green": 0.15, "blue": 0.22}

def rc(r1, r2, c1, c2, fmt):
    return {"repeatCell": {
        "range": {"sheetId": tid, "startRowIndex": r1, "endRowIndex": r2, "startColumnIndex": c1, "endColumnIndex": c2},
        "cell": {"userEnteredFormat": fmt},
        "fields": "userEnteredFormat"
    }}

TYPE_A_ROW = 6   # row 7
TYPE_B_ROW = 31  # row 32
TYPE_C_ROW = 55  # row 56

requests = [
    # 메인 타이틀
    rc(1, 2, 1, 4, {
        "textFormat": {"bold": True, "fontSize": 18, "foregroundColorStyle": {"rgbColor": WHITE}},
        "backgroundColor": DARK,
    }),
    {"mergeCells": {"range": {"sheetId": tid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 1, "endColumnIndex": 4}, "mergeType": "MERGE_ALL"}},
    # 설명 텍스트 (행4~5) 이탤릭
    rc(3, 5, 1, 4, {"textFormat": {"italic": True, "fontSize": 10}}),
    # TYPE A 헤더
    rc(TYPE_A_ROW, TYPE_A_ROW + 1, 1, 4, {
        "textFormat": {"bold": True, "fontSize": 12, "foregroundColorStyle": {"rgbColor": WHITE}},
        "backgroundColor": {"red": 0.27, "green": 0.51, "blue": 0.71},
    }),
    # TYPE B 헤더
    rc(TYPE_B_ROW, TYPE_B_ROW + 1, 1, 4, {
        "textFormat": {"bold": True, "fontSize": 12, "foregroundColorStyle": {"rgbColor": WHITE}},
        "backgroundColor": {"red": 0.42, "green": 0.62, "blue": 0.42},
    }),
    # TYPE C 헤더
    rc(TYPE_C_ROW, TYPE_C_ROW + 1, 1, 4, {
        "textFormat": {"bold": True, "fontSize": 12, "foregroundColorStyle": {"rgbColor": WHITE}},
        "backgroundColor": {"red": 0.68, "green": 0.47, "blue": 0.32},
    }),
    # 제목 라벨 굵게 (A, B, C 각각)
    rc(8, 9, 1, 2, {"textFormat": {"bold": True}}),
    rc(33, 34, 1, 2, {"textFormat": {"bold": True}}),
    rc(57, 58, 1, 2, {"textFormat": {"bold": True}}),
    # 본문 영역 연한 배경
    rc(10, 30, 2, 3, {"backgroundColor": {"red": 0.96, "green": 0.97, "blue": 1.0}}),
    rc(35, 54, 2, 3, {"backgroundColor": {"red": 0.95, "green": 0.98, "blue": 0.95}}),
    rc(59, 76, 2, 3, {"backgroundColor": {"red": 0.98, "green": 0.96, "blue": 0.93}}),
    # 열 너비
    {"updateDimensionProperties": {"range": {"sheetId": tid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 30}, "fields": "pixelSize"}},
    {"updateDimensionProperties": {"range": {"sheetId": tid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},
    {"updateDimensionProperties": {"range": {"sheetId": tid, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3}, "properties": {"pixelSize": 650}, "fields": "pixelSize"}},
]

sh.batch_update({"requests": requests})
print("메일 템플릿 시트 완료!")
print(f"URL: {sh.url}")
