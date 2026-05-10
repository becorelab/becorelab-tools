#!/usr/bin/env python3
"""쿠팡 광고 JSON → 구글시트 대시보드 자동 업데이트

흐름:
1. coupang_data/ 에서 최신 JSON 파일 탐색
2. 계정별(비코어랩/채움) 캠페인·일별 집계
3. 구글시트 대시보드에 새 날짜만 추가
4. ROAS 조건부 서식 적용

시트 구조:
- 📊 비코어랩 요약: 날짜|광고비|매출|ROAS|주문|노출|클릭|CTR|CPC|전환율|메모
- 📊 비코어랩 캠페인별: 날짜|캠페인|광고비|매출|ROAS|주문|노출|클릭|CTR|CPC|전환율|메모
- 📊 채움 요약 / 📊 채움 캠페인별: 동일 구조
"""
import os
import sys
import json
import glob
import re
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))

import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

# ── 설정 ──────────────────────────────────────────────────────
SHEET_ID = "1bmN5H7lB-kIr9Oo5vqUokXanTM0O7xeCMgHoP24WAJg"
SA_KEY = "/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json"
DATA_DIR = "/Users/macmini_ky/ClaudeAITeam/marketing/coupang_data"

ACCOUNTS = {
    "A00290275": {
        "name": "비코어랩",
        "summary_tab": "📊 비코어랩 요약",
        "campaign_tab": "📊 비코어랩 캠페인별",
    },
    "A00940134": {
        "name": "채움컴퍼니",
        "summary_tab": "📊 채움 요약",
        "campaign_tab": "📊 채움 캠페인별",
    },
}

# JSON 필드 매핑 (캠페인 레벨 JSON)
FIELD_MAP = {
    "date": "날짜",
    "campaign": "캠페인명",
    "impressions": "노출수",
    "clicks": "클릭수",
    "cost": "광고비",
    "ctr": "클릭률",
    "sales": "총 전환매출액(14일)",
    "orders": "총 주문수(14일)",
}

# 키워드 레벨에도 같은 필드가 있음 (추가 필드: 광고그룹, 키워드, 노출지면 등)


# ── 포맷터 ─────────────────────────────────────────────────────
def fmt_currency(val):
    """정수 → '₩1,234,567'"""
    v = int(round(val))
    return f"₩{v:,}"


def fmt_pct(val):
    """소수 → '1.75%'"""
    return f"{val:.2f}%"


def fmt_date(raw_date):
    """20260410.0 또는 20260410 → '2026-04-10'"""
    s = str(int(float(raw_date)))
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


# ── JSON 파일 탐색 ────────────────────────────────────────────
def find_latest_json_files(vendor_id, report_type="daily_campaign"):
    """vendor_id에 해당하는 최신 JSON 파일들을 찾아 반환.
    report_type: 'daily_campaign' 또는 'daily_keyword'
    여러 기간 파일이 있으면 가장 넓은 범위(종료일 기준 최신)를 우선하되,
    겹치지 않는 기간의 파일도 모두 포함.
    """
    pattern = os.path.join(DATA_DIR, f"{vendor_id}_pa_{report_type}_*.json")
    files = glob.glob(pattern)
    if not files:
        return []

    # 파일명에서 시작~종료 날짜 추출
    date_re = re.compile(rf"{vendor_id}_pa_{report_type}_(\d{{8}})_(\d{{8}})\.json")
    parsed = []
    for f in files:
        m = date_re.search(os.path.basename(f))
        if m:
            parsed.append((f, m.group(1), m.group(2)))

    if not parsed:
        return files  # 파싱 안 되면 전부 반환

    # 종료일 내림차순 정렬 후, 커버 범위를 최대화하도록 선택
    parsed.sort(key=lambda x: x[2], reverse=True)

    selected = []
    covered_end = None
    for fpath, start, end in parsed:
        if covered_end is None or start < covered_end:
            # 이 파일이 커버하는 범위가 필요
            selected.append(fpath)
            if covered_end is None:
                covered_end = start
            else:
                covered_end = min(covered_end, start)

    return selected


def find_all_json_files(vendor_id):
    """캠페인 레벨 → 키워드 레벨 순서로 탐색.
    캠페인 레벨이 있으면 그걸 쓰고, 없으면 키워드 레벨 사용."""
    campaign_files = find_latest_json_files(vendor_id, "daily_campaign")
    keyword_files = find_latest_json_files(vendor_id, "daily_keyword")

    if campaign_files:
        return campaign_files, "campaign"
    elif keyword_files:
        return keyword_files, "keyword"
    return [], None


# ── JSON 파싱 & 집계 ──────────────────────────────────────────
def load_json_data(file_paths):
    """여러 JSON 파일을 로드하고 합침. 중복 제거(날짜+캠페인+키워드 기준)."""
    all_rows = []
    seen = set()
    for fpath in file_paths:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        for row in data:
            # 중복 키: 날짜 + 캠페인명 + (키워드/노출지면 있으면 포함)
            date_val = str(row.get("날짜", ""))
            campaign = str(row.get("캠페인명", ""))
            keyword = str(row.get("키워드", ""))
            surface = str(row.get("광고 노출 지면", row.get("노출지면", "")))
            option_id = str(row.get("광고집행 옵션ID", ""))
            dedup_key = (date_val, campaign, keyword, surface, option_id)
            if dedup_key not in seen:
                seen.add(dedup_key)
                all_rows.append(row)
    return all_rows


def aggregate_daily_summary(rows):
    """날짜별 전체 합산 → [{date, cost, sales, roas, orders, impressions, clicks, ctr, cpc, cvr}]"""
    daily = defaultdict(lambda: {"cost": 0, "sales": 0, "orders": 0, "impressions": 0, "clicks": 0})
    for row in rows:
        date_str = fmt_date(row.get("날짜", 0))
        d = daily[date_str]
        d["cost"] += float(row.get("광고비", 0) or 0)
        d["sales"] += float(row.get("총 전환매출액(14일)", row.get("총 전환매출액(1일)", 0)) or 0)
        d["orders"] += float(row.get("총 주문수(14일)", row.get("총 주문수(1일)", 0)) or 0)
        d["impressions"] += float(row.get("노출수", 0) or 0)
        d["clicks"] += float(row.get("클릭수", 0) or 0)

    result = []
    for date_str in sorted(daily.keys()):
        d = daily[date_str]
        cost = d["cost"]
        sales = d["sales"]
        clicks = d["clicks"]
        impressions = d["impressions"]
        orders = d["orders"]

        roas = (sales / cost * 100) if cost > 0 else 0
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cpc = (cost / clicks) if clicks > 0 else 0
        cvr = (orders / clicks * 100) if clicks > 0 else 0

        result.append({
            "date": date_str,
            "cost": fmt_currency(cost),
            "sales": fmt_currency(sales),
            "roas": fmt_pct(roas),
            "orders": str(int(orders)),
            "impressions": f"{int(impressions):,}",
            "clicks": str(int(clicks)),
            "ctr": fmt_pct(ctr),
            "cpc": fmt_currency(cpc),
            "cvr": fmt_pct(cvr),
        })
    return result


def aggregate_daily_by_campaign(rows):
    """날짜×캠페인별 합산"""
    daily_camp = defaultdict(lambda: {"cost": 0, "sales": 0, "orders": 0, "impressions": 0, "clicks": 0})
    for row in rows:
        date_str = fmt_date(row.get("날짜", 0))
        campaign = str(row.get("캠페인명", "기타"))
        key = (date_str, campaign)
        d = daily_camp[key]
        d["cost"] += float(row.get("광고비", 0) or 0)
        d["sales"] += float(row.get("총 전환매출액(14일)", row.get("총 전환매출액(1일)", 0)) or 0)
        d["orders"] += float(row.get("총 주문수(14일)", row.get("총 주문수(1일)", 0)) or 0)
        d["impressions"] += float(row.get("노출수", 0) or 0)
        d["clicks"] += float(row.get("클릭수", 0) or 0)

    result = []
    for (date_str, campaign) in sorted(daily_camp.keys()):
        d = daily_camp[(date_str, campaign)]
        cost = d["cost"]
        sales = d["sales"]
        clicks = d["clicks"]
        impressions = d["impressions"]
        orders = d["orders"]

        roas = (sales / cost * 100) if cost > 0 else 0
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cpc = (cost / clicks) if clicks > 0 else 0
        cvr = (orders / clicks * 100) if clicks > 0 else 0

        result.append({
            "date": date_str,
            "campaign": campaign,
            "cost": fmt_currency(cost),
            "sales": fmt_currency(sales),
            "roas": fmt_pct(roas),
            "orders": str(int(orders)),
            "impressions": f"{int(impressions):,}",
            "clicks": str(int(clicks)),
            "ctr": fmt_pct(ctr),
            "cpc": fmt_currency(cpc),
            "cvr": fmt_pct(cvr),
        })
    return result


# ── 구글시트 업데이트 ─────────────────────────────────────────
def connect_sheet():
    """구글시트 연결"""
    creds = Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def get_existing_dates(ws, date_col=1):
    """시트에서 이미 입력된 날짜 목록 반환"""
    values = ws.col_values(date_col)
    dates = set()
    for v in values[1:]:  # 헤더 스킵
        v = v.strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            dates.add(v)
    return dates


def update_summary_tab(sh, tab_name, summary_data):
    """요약 탭 업데이트: A=날짜, B=광고비, ..., K=메모"""
    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        print(f"  ⚠️ 탭 '{tab_name}' 없음 — 새로 생성합니다")
        ws = sh.add_worksheet(title=tab_name, rows=1000, cols=11)
        ws.update(values=[["날짜", "광고비", "매출", "ROAS", "주문", "노출", "클릭", "CTR", "CPC", "전환율", "메모"]], range_name="A1:K1")

    existing_dates = get_existing_dates(ws)
    new_rows = [d for d in summary_data if d["date"] not in existing_dates]

    if not new_rows:
        print(f"  ⏭️ {tab_name}: 새로운 데이터 없음")
        return 0

    # 날짜순 정렬
    new_rows.sort(key=lambda x: x["date"])

    # 마지막 행 찾기
    all_values = ws.col_values(1)
    next_row = len(all_values) + 1

    # 행 데이터 생성
    rows_to_append = []
    for d in new_rows:
        rows_to_append.append([
            d["date"],
            d["cost"],
            d["sales"],
            d["roas"],
            d["orders"],
            d["impressions"],
            d["clicks"],
            d["ctr"],
            d["cpc"],
            d["cvr"],
            "",  # 메모
        ])

    # 배치 업데이트
    end_row = next_row + len(rows_to_append) - 1
    cell_range = f"A{next_row}:K{end_row}"
    ws.update(values=rows_to_append, range_name=cell_range, value_input_option="RAW")

    print(f"  ✅ {tab_name}: {len(new_rows)}일치 추가 ({new_rows[0]['date']} ~ {new_rows[-1]['date']})")
    return len(new_rows)


def update_campaign_tab(sh, tab_name, campaign_data):
    """캠페인별 탭 업데이트: A=날짜, B=캠페인, C=광고비, ..., L=메모"""
    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        print(f"  ⚠️ 탭 '{tab_name}' 없음 — 새로 생성합니다")
        ws = sh.add_worksheet(title=tab_name, rows=5000, cols=12)
        ws.update(values=[["날짜", "캠페인", "광고비", "매출", "ROAS", "주문", "노출", "클릭", "CTR", "CPC", "전환율", "메모"]], range_name="A1:L1")

    existing_dates = get_existing_dates(ws)
    new_rows = [d for d in campaign_data if d["date"] not in existing_dates]

    if not new_rows:
        print(f"  ⏭️ {tab_name}: 새로운 데이터 없음")
        return 0

    new_rows.sort(key=lambda x: (x["date"], x["campaign"]))

    all_values = ws.col_values(1)
    next_row = len(all_values) + 1

    rows_to_append = []
    for d in new_rows:
        rows_to_append.append([
            d["date"],
            d["campaign"],
            d["cost"],
            d["sales"],
            d["roas"],
            d["orders"],
            d["impressions"],
            d["clicks"],
            d["ctr"],
            d["cpc"],
            d["cvr"],
            "",  # 메모
        ])

    end_row = next_row + len(rows_to_append) - 1
    cell_range = f"A{next_row}:L{end_row}"
    ws.update(values=rows_to_append, range_name=cell_range, value_input_option="RAW")

    print(f"  ✅ {tab_name}: {len(new_rows)}행 추가 ({new_rows[0]['date']} ~ {new_rows[-1]['date']})")
    return len(new_rows)


def apply_roas_formatting(sh, tab_name, roas_col_letter):
    """ROAS 열에 조건부 서식 적용: <300% 빨강, >=350% 초록"""
    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return

    sheet_id = ws.id
    roas_col_idx = ord(roas_col_letter) - ord('A')

    # 기존 조건부 서식 삭제 후 재적용
    requests = []

    # 빨간색 배경: ROAS < 300%
    # ROAS 텍스트값에서 숫자 추출하여 비교하는 커스텀 포뮬라 사용
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": roas_col_idx,
                    "endColumnIndex": roas_col_idx + 1,
                }],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{
                            "userEnteredValue": f'=AND({roas_col_letter}2<>"", VALUE(SUBSTITUTE(SUBSTITUTE({roas_col_letter}2,"%",""),",",""))<300)'
                        }]
                    },
                    "format": {
                        "backgroundColor": {"red": 1.0, "green": 0.8, "blue": 0.8}
                    }
                }
            },
            "index": 0
        }
    })

    # 초록색 배경: ROAS >= 350%
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": roas_col_idx,
                    "endColumnIndex": roas_col_idx + 1,
                }],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{
                            "userEnteredValue": f'=AND({roas_col_letter}2<>"", VALUE(SUBSTITUTE(SUBSTITUTE({roas_col_letter}2,"%",""),",",""))>=350)'
                        }]
                    },
                    "format": {
                        "backgroundColor": {"red": 0.85, "green": 0.95, "blue": 0.85}
                    }
                }
            },
            "index": 0
        }
    })

    try:
        sh.batch_update({"requests": requests})
        print(f"  🎨 {tab_name}: ROAS 조건부 서식 적용 완료")
    except Exception as e:
        print(f"  ⚠️ {tab_name}: 조건부 서식 적용 실패 — {e}")


# ── 메인 ──────────────────────────────────────────────────────
def run(vendor_ids=None, dry_run=False):
    """메인 실행

    Args:
        vendor_ids: 처리할 벤더 ID 리스트. None이면 전체.
        dry_run: True면 시트 업데이트 없이 데이터만 확인.
    """
    if vendor_ids is None:
        vendor_ids = list(ACCOUNTS.keys())

    print(f"=== 쿠팡 광고 대시보드 업데이트 ===")
    print(f"  시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  계정: {', '.join(ACCOUNTS[v]['name'] for v in vendor_ids)}")
    print(f"  데이터 경로: {DATA_DIR}")
    print()

    # 계정별 데이터 로드 & 집계
    all_account_data = {}
    for vid in vendor_ids:
        acct = ACCOUNTS[vid]
        print(f"[{acct['name']}] JSON 파일 탐색...")

        files, file_type = find_all_json_files(vid)
        if not files:
            print(f"  ⚠️ JSON 파일 없음 — 건너뜀")
            continue

        print(f"  📁 {file_type} 파일 {len(files)}개 로드")
        for f in files:
            print(f"    {os.path.basename(f)}")

        rows = load_json_data(files)
        print(f"  📊 총 {len(rows)}행 로드 (중복 제거 후)")

        summary = aggregate_daily_summary(rows)
        by_campaign = aggregate_daily_by_campaign(rows)

        print(f"  📅 기간: {summary[0]['date']} ~ {summary[-1]['date']} ({len(summary)}일)")
        print(f"  📋 캠페인별: {len(by_campaign)}행")
        print()

        all_account_data[vid] = {
            "summary": summary,
            "by_campaign": by_campaign,
        }

    if dry_run:
        print("\n[DRY RUN] 시트 업데이트를 건너뜁니다.")
        for vid, data in all_account_data.items():
            print(f"\n── {ACCOUNTS[vid]['name']} 요약 (최근 5일) ──")
            for d in data["summary"][-5:]:
                print(f"  {d['date']}  광고비={d['cost']}  매출={d['sales']}  ROAS={d['roas']}  주문={d['orders']}")
        return all_account_data

    if not all_account_data:
        print("❌ 업데이트할 데이터가 없습니다.")
        return {}

    # 구글시트 연결
    print("[시트] 구글시트 연결 중...")
    sh = connect_sheet()
    print(f"  ✅ 시트 연결: {sh.title}")
    print()

    total_updated = 0
    for vid, data in all_account_data.items():
        acct = ACCOUNTS[vid]
        print(f"[{acct['name']}] 시트 업데이트...")

        # 요약 탭
        n = update_summary_tab(sh, acct["summary_tab"], data["summary"])
        total_updated += n

        # 캠페인별 탭
        n = update_campaign_tab(sh, acct["campaign_tab"], data["by_campaign"])
        total_updated += n

    # 조건부 서식 적용
    print("\n[서식] ROAS 조건부 서식 적용...")
    for vid in all_account_data:
        acct = ACCOUNTS[vid]
        apply_roas_formatting(sh, acct["summary_tab"], "D")   # 요약: D=ROAS
        apply_roas_formatting(sh, acct["campaign_tab"], "E")   # 캠페인별: E=ROAS

    print(f"\n{'='*50}")
    print(f"✅ 완료! 총 {total_updated}개 행 업데이트")
    sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    print(f"📊 시트: {sheet_url}")
    return all_account_data


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv or "--dry" in sys.argv

    # 특정 계정만 지정 가능
    vids = None
    for arg in sys.argv[1:]:
        if arg in ACCOUNTS:
            if vids is None:
                vids = []
            vids.append(arg)
        elif arg == "becorelab":
            if vids is None:
                vids = []
            vids.append("A00290275")
        elif arg == "chaewoom":
            if vids is None:
                vids = []
            vids.append("A00940134")

    run(vendor_ids=vids, dry_run=dry)
