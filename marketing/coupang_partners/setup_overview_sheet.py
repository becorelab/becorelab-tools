"""구글 시트 프로젝트 개요 시트 생성"""
import sys
import gspread
from google.oauth2.service_account import Credentials

sys.stdout.reconfigure(encoding="utf-8")

KEY_PATH = "/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json"
SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"

creds = Credentials.from_service_account_file(KEY_PATH, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
])
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)

# 기존 개요 시트 있으면 삭제
for ws in sh.worksheets():
    if ws.title == "프로젝트 개요":
        sh.del_worksheet(ws)
        break

overview = sh.add_worksheet(title="프로젝트 개요", rows=42, cols=6, index=0)
sid = overview.id

content = [
    [""],
    ["", "🎬 쿠팡 파트너스 유튜버 협업 프로젝트"],
    [""],
    ["", "브랜드", "iLBiA (일비아) — 주식회사 비코어랩"],
    ["", "목표", "마이크로 유튜버(1만~10만)와 쿠팡 파트너스 협업으로 매출 확대"],
    ["", "대상 제품", "건조기 시트, 식기세척기 세제, 캡슐 세제, 얼룩 제거제, 섬유 탈취제"],
    [""],
    ["", "📋 진행 프로세스"],
    [""],
    ["", "STEP", "내용", "담당", "상태"],
    ["", "① 유튜버 발굴", "AI가 쿠팡 파트너스 활동 중인 살림/생활 유튜버 자동 검색", "하치(AI)", "✅ 완료"],
    ["", "② 1차 스크리닝", "AI가 채널 적합도 분석 (구독자, 카테고리, 활동성, 제품 매칭)", "하치(AI)", "✅ 완료"],
    ["", "③ 검토 & 승인", "→ [후보 리스트] 시트에서 승인/거절/보류 선택", "대표님 & 성락 대리님", "⬅️ 현재"],
    ["", "④ 제안 메일 발송", "승인된 유튜버에게 맞춤 협업 제안 메일 자동 발송", "하치(AI)", "대기"],
    ["", "⑤ 회신 관리", "답장 감지 → 텔레그램 알림 → 후속 대응", "대표님 + 두리(AI)", "대기"],
    ["", "⑥ 샘플 발송", "협업 확정 시 제품 풀세트 발송", "대표님", "대기"],
    ["", "⑦ 영상 확인", "업로드된 영상 검수 + 쿠팡 파트너스 링크 확인", "하치(AI)", "대기"],
    [""],
    ["", "💰 제안 조건 (원고료 없음)"],
    [""],
    ["", "항목", "상세"],
    ["", "제품 풀세트 무료 제공", "건조기 시트 + 세제 + 얼룩제거제 등 (소비자가 5~7만원 상당)"],
    ["", "쿠팡 파트너스 수수료", "기본 3% + 유튜브 쇼핑 제휴 시 6.7%"],
    ["", "성과 보너스", "월 매출 30만원 초과 시 5만원 지급"],
    ["", "장기 파트너십", "반응 좋은 상위 유튜버 → 정식 원고료 계약(30~50만원) 전환"],
    [""],
    ["", "📌 [후보 리스트] 시트 사용법"],
    [""],
    ["", "1.", "각 유튜버의 채널URL 클릭 → 채널 확인"],
    ["", "2.", "선정이유, 추천제품 참고"],
    ["", "3.", "승인 컬럼(J열) 드롭다운에서 선택: 승인 / 거절 / 보류"],
    ["", "4.", "메모 컬럼에 코멘트 자유롭게 작성"],
    ["", "5.", "승인 완료 후 → AI가 맞춤 메일 자동 발송"],
    [""],
    ["", "⚡ 타겟 유튜버 선별 기준"],
    [""],
    ["", "✓", "구독자 1만~10만명 (마이크로 유튜버)"],
    ["", "✓", "살림/생활/육아/자취/청소 카테고리"],
    ["", "✓", "최근 30일 내 영상 업로드 활동 중"],
    ["", "✓", "이미 쿠팡 파트너스 링크를 사용 중 (수락률 높음)"],
    ["", "✓", "영상 설명란에 비즈니스 이메일 공개"],
]

overview.update(values=content, range_name="A1:E41")

# 디자인
WHITE = {"red": 1, "green": 1, "blue": 1}
DARK = {"red": 0.15, "green": 0.15, "blue": 0.22}
BLUE_HEADER = {"red": 0.22, "green": 0.33, "blue": 0.53}
SECTION_BG = {"red": 0.92, "green": 0.94, "blue": 0.98}
HIGHLIGHT = {"red": 1, "green": 0.95, "blue": 0.8}
GREEN_BG = {"red": 0.85, "green": 0.92, "blue": 0.85}
LIGHT_GRAY = {"red": 0.95, "green": 0.95, "blue": 0.95}
BORDER_COLOR = {"red": 0.7, "green": 0.7, "blue": 0.7}
INNER_BORDER = {"red": 0.85, "green": 0.85, "blue": 0.85}

def repeat_cell(r1, r2, c1, c2, fmt):
    return {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2, "startColumnIndex": c1, "endColumnIndex": c2},
        "cell": {"userEnteredFormat": fmt},
        "fields": "userEnteredFormat"
    }}

requests = [
    # 타이틀 B2
    repeat_cell(1, 2, 1, 5, {
        "textFormat": {"bold": True, "fontSize": 18, "foregroundColorStyle": {"rgbColor": WHITE}},
        "backgroundColor": DARK,
    }),
    # 타이틀 병합
    {"mergeCells": {
        "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 1, "endColumnIndex": 5},
        "mergeType": "MERGE_ALL"
    }},
    # 기본 정보 B4:B6 라벨
    repeat_cell(3, 6, 1, 2, {"textFormat": {"bold": True}, "backgroundColor": LIGHT_GRAY}),
    # 섹션 헤더들
    repeat_cell(7, 8, 1, 5, {"textFormat": {"bold": True, "fontSize": 13}, "backgroundColor": SECTION_BG}),
    repeat_cell(18, 19, 1, 5, {"textFormat": {"bold": True, "fontSize": 13}, "backgroundColor": SECTION_BG}),
    repeat_cell(26, 27, 1, 5, {"textFormat": {"bold": True, "fontSize": 13}, "backgroundColor": SECTION_BG}),
    repeat_cell(33, 34, 1, 5, {"textFormat": {"bold": True, "fontSize": 13}, "backgroundColor": SECTION_BG}),
    # 프로세스 테이블 헤더 (행10)
    repeat_cell(9, 10, 1, 5, {
        "textFormat": {"bold": True, "fontSize": 10, "foregroundColorStyle": {"rgbColor": WHITE}},
        "backgroundColor": BLUE_HEADER,
        "horizontalAlignment": "CENTER",
    }),
    # 현재 단계 강조 (행13)
    repeat_cell(12, 13, 1, 5, {"backgroundColor": HIGHLIGHT, "textFormat": {"bold": True}}),
    # 제안 조건 헤더 (행21)
    repeat_cell(20, 21, 1, 3, {"textFormat": {"bold": True}, "backgroundColor": GREEN_BG}),
    # 프로세스 테이블 테두리
    {"updateBorders": {
        "range": {"sheetId": sid, "startRowIndex": 9, "endRowIndex": 17, "startColumnIndex": 1, "endColumnIndex": 5},
        "top": {"style": "SOLID", "color": BORDER_COLOR},
        "bottom": {"style": "SOLID", "color": BORDER_COLOR},
        "left": {"style": "SOLID", "color": BORDER_COLOR},
        "right": {"style": "SOLID", "color": BORDER_COLOR},
        "innerHorizontal": {"style": "SOLID", "color": INNER_BORDER},
        "innerVertical": {"style": "SOLID", "color": INNER_BORDER},
    }},
    # 제안 조건 테두리
    {"updateBorders": {
        "range": {"sheetId": sid, "startRowIndex": 20, "endRowIndex": 25, "startColumnIndex": 1, "endColumnIndex": 3},
        "top": {"style": "SOLID", "color": BORDER_COLOR},
        "bottom": {"style": "SOLID", "color": BORDER_COLOR},
        "left": {"style": "SOLID", "color": BORDER_COLOR},
        "right": {"style": "SOLID", "color": BORDER_COLOR},
        "innerHorizontal": {"style": "SOLID", "color": INNER_BORDER},
        "innerVertical": {"style": "SOLID", "color": INNER_BORDER},
    }},
    # 열 너비
    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 30}, "fields": "pixelSize"}},
    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 200}, "fields": "pixelSize"}},
    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3}, "properties": {"pixelSize": 450}, "fields": "pixelSize"}},
    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 4}, "properties": {"pixelSize": 180}, "fields": "pixelSize"}},
    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 4, "endIndex": 5}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},
    # 1행 높이 작게
    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 15}, "fields": "pixelSize"}},
    # 타이틀 행 높이
    {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 50}, "fields": "pixelSize"}},
    # 시트 보호 (프로젝트 개요는 읽기 전용)
    {"addProtectedRange": {
        "protectedRange": {
            "range": {"sheetId": sid},
            "description": "프로젝트 개요 — 수정 금지",
            "warningOnly": True,
        }
    }},
]

sh.batch_update({"requests": requests})
print("프로젝트 개요 시트 완료!")
print(f"URL: {sh.url}")
