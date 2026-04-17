"""구글 시트에 메일 템플릿 시트 추가"""
import sys
import gspread
from google.oauth2.service_account import Credentials

sys.stdout.reconfigure(encoding="utf-8")

KEY_PATH = r"C:\Users\info\claudeaiteam\sourcing\analyzer\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
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
    ["", "{채널명}, {유튜버님 이름} 등은 자동으로 치환됩니다."],
    [""],
    # ── 타입 A ──
    ["", "TYPE A — 살림/생활 채널 (기본형)"],
    [""],
    ["", "제목:", "[iLBiA 쿠팡 파트너스] {채널명}님, 생활세제 협업 제안드립니다"],
    [""],
    ["", "본문:"],
    ["", "", "안녕하세요, {채널명}님!"],
    ["", "", ""],
    ["", "", "생활세제 브랜드 iLBiA(일비아)의 마케팅팀입니다."],
    ["", "", "{채널명}님의 영상을 즐겨 보고 있는데, 살림에 진심이신 모습이 정말 인상 깊었습니다."],
    ["", "", ""],
    ["", "", "저희가 만드는 건조기 시트, 식기세척기 세제, 캡슐 세제, 얼룩 제거제는"],
    ["", "", "{채널명}님 채널의 시청자분들이 실제로 관심 가질 제품이라 생각해 연락드렸습니다."],
    ["", "", ""],
    ["", "", "■ 협업 방식"],
    ["", "", "  • 저희 제품 풀세트 무료 제공 (소비자가 약 5~7만원 상당)"],
    ["", "", "  • 쿠팡 파트너스 링크 활용 (수수료 3~6.7%)"],
    ["", "", "  • 월 매출 30만원 초과 시 보너스 5만원 별도 지급"],
    ["", "", "  • 영상 형식/일정 모두 자유 (숏츠, 브이로그, 추천 등)"],
    ["", "", ""],
    ["", "", "관심이 있으시다면 이 메일에 편하게 답장해주세요."],
    ["", "", "제품 발송 주소 안내드리겠습니다."],
    ["", "", ""],
    ["", "", "감사합니다."],
    ["", "", "비코어랩 마케팅팀 드림"],
    [""],
    # ── 타입 B ──
    ["", "TYPE B — 육아/반려동물 채널 (공감형)"],
    [""],
    ["", "제목:", "[iLBiA] {채널명}님, 아이/반려동물 가정에 딱 맞는 세제 협업 제안"],
    [""],
    ["", "본문:"],
    ["", "", "안녕하세요, {채널명}님!"],
    ["", "", ""],
    ["", "", "생활세제 브랜드 iLBiA(일비아) 마케팅팀입니다."],
    ["", "", "{채널명}님 영상을 보면서, 아이(반려동물)와 함께하는 일상이 정말 따뜻하더라고요."],
    ["", "", ""],
    ["", "", "저희 '얼룩 제거제'와 '섬유 탈취제'는 아이 옷 얼룩이나"],
    ["", "", "반려동물 냄새 고민이 있는 가정에서 특히 반응이 좋은 제품이에요."],
    ["", "", ""],
    ["", "", "■ 제안 내용"],
    ["", "", "  • 제품 풀세트 무료 발송 (건조기 시트, 세제, 얼룩 제거제 등)"],
    ["", "", "  • 쿠팡 파트너스 링크로 수수료 수익 (3~6.7%)"],
    ["", "", "  • 월 매출 30만원 초과 시 보너스 5만원"],
    ["", "", "  • 콘텐츠 형식 100% 자유"],
    ["", "", ""],
    ["", "", "실제로 써보시고 마음에 드실 때만 영상 만들어주시면 됩니다."],
    ["", "", "부담 없이 답장 주세요!"],
    ["", "", ""],
    ["", "", "감사합니다."],
    ["", "", "비코어랩 마케팅팀 드림"],
    [""],
    # ── 타입 C ──
    ["", "TYPE C — 자취/미니멀 라이프 채널 (가성비 강조형)"],
    [""],
    ["", "제목:", "[iLBiA] {채널명}님, 가성비 생활세제 협업 제안"],
    [""],
    ["", "본문:"],
    ["", "", "안녕하세요, {채널명}님!"],
    ["", "", ""],
    ["", "", "생활세제 브랜드 iLBiA(일비아)입니다."],
    ["", "", "{채널명}님의 실용적인 생활 꿀팁 영상 잘 보고 있습니다."],
    ["", "", ""],
    ["", "", "저희 제품은 쿠팡에서 가성비 좋은 생활세제로 입소문나고 있는데,"],
    ["", "", "{채널명}님 시청자분들의 취향과 잘 맞을 것 같아 연락드렸습니다."],
    ["", "", ""],
    ["", "", "■ 혜택"],
    ["", "", "  • 세제 풀세트 무료 제공 (5~7만원 상당)"],
    ["", "", "  • 쿠팡 파트너스 수수료 3~6.7%"],
    ["", "", "  • 월 매출 30만원 초과 시 보너스 5만원"],
    ["", "", "  • 콘텐츠 자유 (숏츠 30초도 OK)"],
    ["", "", ""],
    ["", "", "관심 있으시면 편하게 답장 주세요!"],
    ["", "", ""],
    ["", "", "감사합니다."],
    ["", "", "비코어랑 마케팅팀 드림"],
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
