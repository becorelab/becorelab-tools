#!/usr/bin/env python3
"""쿠팡 광고 대시보드 v2 — 구글시트 자동 업데이트

대상 시트: 🚀 쿠팡 광고 대시보드
시트 ID: 1RqEKC5KT0O_aZWnsDH4UdX3grfYSpg68hqyJteRVmBw

워크시트:
- 비코어랩 요약 / 비코어랩 캠페인별 / 비코어랩 검색/비검색
- 채움컴퍼니 요약 / 채움컴퍼니 캠페인별 / 채움컴퍼니 검색/비검색
- 키워드 TOP

흐름:
1. coupang_data/ 에서 최신 JSON 파일 탐색
2. 계정별 집계 (요약/캠페인별/검색비검색/키워드TOP)
3. 구글시트에 새 날짜만 상단에 삽입 (내림차순 — 최신이 위)
4. 좌정렬 유지

숫자 형식:
- 광고비/매출/CPC: 1,234 (₩ 없음, 쉼표 구분)
- ROAS: 209% (정수 %)
- CTR: 0.16 (소수, % 없음)
- 전환율: 15.5 (소수, % 없음)
"""
import os
import sys
import json
import glob
import re
from datetime import datetime
from collections import defaultdict
import warnings

warnings.filterwarnings("ignore")

import gspread
from google.oauth2.service_account import Credentials

# ── 설정 ──────────────────────────────────────────────────────
SHEET_ID = "1RqEKC5KT0O_aZWnsDH4UdX3grfYSpg68hqyJteRVmBw"
MGMT_SHEET_ID = "1bmN5H7lB-kIr9Oo5vqUokXanTM0O7xeCMgHoP24WAJg"
SA_KEY = "/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json"
DATA_DIR = "/Users/macmini_ky/ClaudeAITeam/marketing/coupang_data"

ACCOUNTS = {
    "A00290275": {
        "name": "비코어랩",
        "summary_tab": "비코어랩 요약",
        "campaign_tab": "비코어랩 캠페인별",
        "zone_tab": "비코어랩 검색/비검색",
        "mgmt_summary_tab": "📊 비코어랩 요약",
        "mgmt_campaign_tab": "📊 비코어랩 캠페인별",
        "mgmt_zone_tab": None,  # 비코어랩은 캠페인필터 구조라 스킵
    },
    "A00940134": {
        "name": "채움컴퍼니",
        "summary_tab": "채움컴퍼니 요약",
        "campaign_tab": "채움컴퍼니 캠페인별",
        "zone_tab": "채움컴퍼니 검색/비검색",
        "mgmt_summary_tab": "📊 채움컴퍼니 요약",
        "mgmt_campaign_tab": "📊 채움컴퍼니 캠페인별",
        "mgmt_zone_tab": "📊 채움컴퍼니 검색/비검색",
    },
}


# ── 포맷터 (대시보드용) ──────────────────────────────────────────
def fmt_num(val):
    """정수 → '1,234' (쉼표 구분, ₩ 없음)"""
    return f"{int(round(val)):,}"


def fmt_pct_int(val):
    """소수 → '209%' (정수 퍼센트)"""
    return f"{int(round(val))}%"


def fmt_decimal(val, places=2):
    """소수 → '0.16' (퍼센트 기호 없음)"""
    return str(round(val, places))


# ── 포맷터 (관리시트용: ₩ 접두사, % 소수점) ──────────────────────
def mgmt_money(val):
    return f"₩{int(round(val)):,}"


def mgmt_pct(val, places=1):
    return f"{round(val, places):.{places}f}%"


def fmt_date(raw_date):
    """20260410.0 → '2026-04-10'"""
    s = str(int(float(raw_date)))
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def safe_div(a, b):
    return a / b if b else 0


# ── JSON 파일 탐색 ────────────────────────────────────────────
def find_latest_json_files(vendor_id, report_type="daily_keyword"):
    """vendor_id에 해당하는 최신 JSON 파일들을 찾아 반환.
    여러 기간 파일을 합쳐 전체 커버리지를 최대화.
    """
    pattern = os.path.join(DATA_DIR, f"{vendor_id}_pa_{report_type}_*.json")
    files = glob.glob(pattern)
    if not files:
        return []

    date_re = re.compile(rf"{vendor_id}_pa_{report_type}_(\d{{8}})_(\d{{8}})\.json")
    parsed = []
    for f in files:
        m = date_re.search(os.path.basename(f))
        if m:
            parsed.append((f, m.group(1), m.group(2)))

    if not parsed:
        return files

    # 종료일 내림차순 정렬 후, 커버 범위를 최대화하도록 선택
    parsed.sort(key=lambda x: x[2], reverse=True)

    selected = []
    covered_end = None
    for fpath, start, end in parsed:
        if covered_end is None or start < covered_end:
            selected.append(fpath)
            if covered_end is None:
                covered_end = start
            else:
                covered_end = min(covered_end, start)

    return selected


def find_all_json_files(vendor_id):
    """키워드 레벨 우선, 없으면 캠페인 레벨."""
    keyword_files = find_latest_json_files(vendor_id, "daily_keyword")
    campaign_files = find_latest_json_files(vendor_id, "daily_campaign")

    if keyword_files:
        return keyword_files, "keyword"
    elif campaign_files:
        return campaign_files, "campaign"
    return [], None


# ── JSON 파싱 & 집계 ──────────────────────────────────────────
def load_json_data(file_paths):
    """여러 JSON 파일을 로드.
    파일 간 날짜 중복이 없으므로 단순 합산.
    동일 날짜가 여러 파일에 있을 경우에만 날짜 기준으로 최신 파일 우선.
    """
    # 파일별 날짜 범위 파악 → 날짜 중복 시 최신 파일(종료일 기준) 우선
    date_file_map = {}  # date -> file_path (최신 파일 우선)
    file_data = {}
    for fpath in file_paths:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        file_data[fpath] = data
        for row in data:
            d = str(row.get("날짜", ""))
            if d not in date_file_map:
                date_file_map[d] = fpath

    # 각 날짜에 대해 해당 파일의 모든 행을 그대로 사용 (dedup 없이 합산)
    all_rows = []
    dates_loaded = set()
    for fpath in file_paths:
        for row in file_data[fpath]:
            d = str(row.get("날짜", ""))
            if date_file_map.get(d) == fpath:
                all_rows.append(row)
        # 이 파일에서 로드한 날짜 기록
        for row in file_data[fpath]:
            d = str(row.get("날짜", ""))
            if date_file_map.get(d) == fpath:
                dates_loaded.add(d)

    return all_rows


def _get_sales(row):
    """매출 필드 — 1일 기준 사용 (시트 기존 데이터와 일관성)"""
    return float(row.get("총 전환매출액(1일)", 0) or 0)


def _get_orders(row):
    """주문 필드 — 1일 기준"""
    return float(row.get("총 주문수(1일)", 0) or 0)


def aggregate_daily_summary(rows):
    """날짜별 전체 합산"""
    daily = defaultdict(lambda: {"cost": 0, "sales": 0, "orders": 0, "impressions": 0, "clicks": 0})
    for row in rows:
        date_str = fmt_date(row.get("날짜", 0))
        d = daily[date_str]
        d["cost"] += float(row.get("광고비", 0) or 0)
        d["sales"] += _get_sales(row)
        d["orders"] += _get_orders(row)
        d["impressions"] += float(row.get("노출수", 0) or 0)
        d["clicks"] += float(row.get("클릭수", 0) or 0)

    result = []
    for date_str in sorted(daily.keys(), reverse=True):  # 내림차순
        d = daily[date_str]
        cost, sales, clicks = d["cost"], d["sales"], d["clicks"]
        impressions, orders = d["impressions"], d["orders"]

        roas = safe_div(sales, cost) * 100
        ctr = safe_div(clicks, impressions) * 100
        cpc = safe_div(cost, clicks)
        cvr = safe_div(orders, clicks) * 100

        result.append({
            "date": date_str,
            "cost": fmt_num(cost),
            "sales": fmt_num(sales),
            "roas": fmt_pct_int(roas),
            "orders": str(int(orders)),
            "impressions": str(int(impressions)),
            "clicks": str(int(clicks)),
            "ctr": fmt_decimal(ctr),
            "cpc": fmt_num(cpc),
            "cvr": fmt_decimal(cvr, 1),
            "_cost": cost, "_sales": sales, "_roas": roas,
            "_orders": orders, "_impressions": impressions, "_clicks": clicks,
            "_ctr": ctr, "_cpc": cpc, "_cvr": cvr,
        })
    return result


def aggregate_daily_by_campaign(rows):
    """날짜×캠페인별 합산"""
    daily_camp = defaultdict(lambda: {"cost": 0, "sales": 0, "orders": 0, "impressions": 0, "clicks": 0})
    for row in rows:
        date_str = fmt_date(row.get("날짜", 0))
        campaign = str(row.get("캠페인", row.get("캠페인명", "기타")))
        key = (date_str, campaign)
        d = daily_camp[key]
        d["cost"] += float(row.get("광고비", 0) or 0)
        d["sales"] += _get_sales(row)
        d["orders"] += _get_orders(row)
        d["impressions"] += float(row.get("노출수", 0) or 0)
        d["clicks"] += float(row.get("클릭수", 0) or 0)

    result = []
    for (date_str, campaign) in sorted(daily_camp.keys(), reverse=True):  # 내림차순
        d = daily_camp[(date_str, campaign)]
        cost, sales, clicks = d["cost"], d["sales"], d["clicks"]
        impressions, orders = d["impressions"], d["orders"]

        roas = safe_div(sales, cost) * 100
        ctr = safe_div(clicks, impressions) * 100
        cpc = safe_div(cost, clicks)
        cvr = safe_div(orders, clicks) * 100

        result.append({
            "date": date_str,
            "campaign": campaign,
            "cost": fmt_num(cost),
            "sales": fmt_num(sales),
            "roas": fmt_pct_int(roas),
            "orders": str(int(orders)),
            "impressions": str(int(impressions)),
            "clicks": str(int(clicks)),
            "ctr": fmt_decimal(ctr),
            "cpc": fmt_num(cpc),
            "cvr": fmt_decimal(cvr, 1),
            "_cost": cost, "_sales": sales, "_roas": roas,
            "_orders": orders, "_impressions": impressions, "_clicks": clicks,
            "_ctr": ctr, "_cpc": cpc, "_cvr": cvr,
        })
    return result


def aggregate_daily_by_zone(rows):
    """날짜×노출지면별 합산 → 검색/비검색 시트용"""
    zone_map = {"검색 영역": "검색 영역", "비검색 영역": "비검색 영역"}
    daily_zone = defaultdict(lambda: {"cost": 0, "sales": 0, "orders": 0, "clicks": 0})

    for row in rows:
        date_str = fmt_date(row.get("날짜", 0))
        zone_raw = row.get("광고 노출 지면") or row.get("노출 영역") or ""
        zone = zone_map.get(zone_raw)
        if not zone:
            continue
        key = (date_str, zone)
        d = daily_zone[key]
        d["cost"] += float(row.get("광고비", 0) or 0)
        d["sales"] += _get_sales(row)
        d["orders"] += _get_orders(row)
        d["clicks"] += float(row.get("클릭수", 0) or 0)

    result = []
    for (date_str, zone) in sorted(daily_zone.keys(), reverse=True):  # 내림차순
        d = daily_zone[(date_str, zone)]
        cost, sales, clicks, orders = d["cost"], d["sales"], d["clicks"], d["orders"]

        roas = safe_div(sales, cost) * 100
        cpc = safe_div(cost, clicks)

        result.append({
            "date": date_str,
            "zone": zone,
            "cost": fmt_num(cost),
            "sales": fmt_num(sales),
            "roas": fmt_pct_int(roas),
            "orders": str(int(orders)),
            "clicks": str(int(clicks)),
            "cpc": fmt_num(cpc),
        })
    return result


def aggregate_keyword_top(all_account_rows, top_n=200):
    """전체 계정 합산 키워드별 광고비 TOP N"""
    kw_data = defaultdict(lambda: {"account": "", "cost": 0, "sales": 0, "orders": 0, "impressions": 0, "clicks": 0})

    for account_name, rows in all_account_rows:
        for row in rows:
            keyword = str(row.get("키워드", "")).strip()
            if not keyword:
                continue
            d = kw_data[(account_name, keyword)]
            d["account"] = account_name
            d["cost"] += float(row.get("광고비", 0) or 0)
            d["sales"] += _get_sales(row)
            d["orders"] += _get_orders(row)
            d["impressions"] += float(row.get("노출수", 0) or 0)
            d["clicks"] += float(row.get("클릭수", 0) or 0)

    # 광고비 내림차순
    sorted_kw = sorted(kw_data.items(), key=lambda x: x[1]["cost"], reverse=True)[:top_n]

    result = []
    for (account_name, keyword), d in sorted_kw:
        cost, sales, clicks = d["cost"], d["sales"], d["clicks"]
        impressions, orders = d["impressions"], d["orders"]

        roas = safe_div(sales, cost) * 100
        ctr = safe_div(clicks, impressions) * 100
        cpc = safe_div(cost, clicks)

        result.append([
            account_name,
            keyword,
            fmt_num(cost),
            fmt_num(sales),
            fmt_pct_int(roas),
            str(int(orders)),
            str(int(impressions)),
            str(int(clicks)),
            fmt_decimal(ctr),
            fmt_num(cpc),
        ])
    return result


# ── 구글시트 업데이트 ─────────────────────────────────────────
def connect_sheet():
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


def insert_rows_at_top(ws, rows, num_cols):
    """헤더 바로 아래(2행부터)에 행 삽입 — 내림차순 유지.
    gspread의 insert_rows는 내부적으로 insertDimension + update를 씀.
    """
    if not rows:
        return

    # 2행 위치에 빈 행 삽입
    ws.insert_rows(rows, row=2, value_input_option="RAW")


def apply_left_align(sh, ws, start_row, end_row, num_cols):
    """좌정렬 적용"""
    request = {
        "repeatCell": {
            "range": {
                "sheetId": ws.id,
                "startRowIndex": start_row - 1,
                "endRowIndex": end_row,
                "startColumnIndex": 0,
                "endColumnIndex": num_cols,
            },
            "cell": {
                "userEnteredFormat": {
                    "horizontalAlignment": "LEFT",
                }
            },
            "fields": "userEnteredFormat.horizontalAlignment",
        }
    }
    sh.batch_update({"requests": [request]})


def update_summary_tab(sh, tab_name, summary_data):
    """요약 탭: 날짜|광고비|매출|ROAS|주문|노출|클릭|CTR|CPC|전환율"""
    HEADERS = ["날짜", "광고비", "매출", "ROAS", "주문", "노출", "클릭", "CTR", "CPC", "전환율"]

    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        print(f"  ⚠️ 탭 '{tab_name}' 없음 — 새로 생성")
        ws = sh.add_worksheet(title=tab_name, rows=1000, cols=len(HEADERS))
        ws.update(values=[HEADERS], range_name=f"A1:{chr(64 + len(HEADERS))}1")

    existing_dates = get_existing_dates(ws)
    new_entries = [d for d in summary_data if d["date"] not in existing_dates]

    if not new_entries:
        print(f"  ⏭️ {tab_name}: 새로운 데이터 없음")
        return 0

    # 이미 내림차순 정렬된 상태 — 그대로 상단에 삽입
    rows_to_insert = []
    for d in new_entries:
        rows_to_insert.append([
            d["date"], d["cost"], d["sales"], d["roas"],
            d["orders"], d["impressions"], d["clicks"],
            d["ctr"], d["cpc"], d["cvr"],
        ])

    insert_rows_at_top(ws, rows_to_insert, len(HEADERS))
    apply_left_align(sh, ws, 2, 2 + len(rows_to_insert), len(HEADERS))

    dates = [d["date"] for d in new_entries]
    print(f"  ✅ {tab_name}: {len(new_entries)}일치 추가 ({dates[0]} ~ {dates[-1]})")
    return len(new_entries)


def update_campaign_tab(sh, tab_name, campaign_data):
    """캠페인별 탭: 날짜|캠페인|광고비|매출|ROAS|주문|노출|클릭|CTR|CPC|전환율"""
    HEADERS = ["날짜", "캠페인", "광고비", "매출", "ROAS", "주문", "노출", "클릭", "CTR", "CPC", "전환율"]

    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        print(f"  ⚠️ 탭 '{tab_name}' 없음 — 새로 생성")
        ws = sh.add_worksheet(title=tab_name, rows=5000, cols=len(HEADERS))
        ws.update(values=[HEADERS], range_name=f"A1:{chr(64 + len(HEADERS))}1")

    existing_dates = get_existing_dates(ws)
    new_entries = [d for d in campaign_data if d["date"] not in existing_dates]

    if not new_entries:
        print(f"  ⏭️ {tab_name}: 새로운 데이터 없음")
        return 0

    rows_to_insert = []
    for d in new_entries:
        rows_to_insert.append([
            d["date"], d["campaign"], d["cost"], d["sales"], d["roas"],
            d["orders"], d["impressions"], d["clicks"],
            d["ctr"], d["cpc"], d["cvr"],
        ])

    insert_rows_at_top(ws, rows_to_insert, len(HEADERS))
    apply_left_align(sh, ws, 2, 2 + len(rows_to_insert), len(HEADERS))

    dates = sorted(set(d["date"] for d in new_entries), reverse=True)
    print(f"  ✅ {tab_name}: {len(new_entries)}행 추가 ({dates[0]} ~ {dates[-1]})")
    return len(new_entries)


def update_zone_tab(sh, tab_name, zone_data):
    """검색/비검색 탭: 날짜|노출지면|광고비|매출|ROAS|주문|클릭|CPC"""
    HEADERS = ["날짜", "노출지면", "광고비", "매출", "ROAS", "주문", "클릭", "CPC"]

    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        print(f"  ⚠️ 탭 '{tab_name}' 없음 — 새로 생성")
        ws = sh.add_worksheet(title=tab_name, rows=5000, cols=len(HEADERS))
        ws.update(values=[HEADERS], range_name=f"A1:{chr(64 + len(HEADERS))}1")

    existing_dates = get_existing_dates(ws)
    new_entries = [d for d in zone_data if d["date"] not in existing_dates]

    if not new_entries:
        print(f"  ⏭️ {tab_name}: 새로운 데이터 없음")
        return 0

    rows_to_insert = []
    for d in new_entries:
        rows_to_insert.append([
            d["date"], d["zone"], d["cost"], d["sales"],
            d["roas"], d["orders"], d["clicks"], d["cpc"],
        ])

    insert_rows_at_top(ws, rows_to_insert, len(HEADERS))
    apply_left_align(sh, ws, 2, 2 + len(rows_to_insert), len(HEADERS))

    dates = sorted(set(d["date"] for d in new_entries), reverse=True)
    print(f"  ✅ {tab_name}: {len(new_entries)}행 추가 ({dates[0]} ~ {dates[-1]})")
    return len(new_entries)


def update_keyword_top(sh, keyword_rows):
    """키워드 TOP 탭: 전체 교체 (매번 최신 데이터로)"""
    HEADERS = ["계정", "키워드", "광고비", "매출", "ROAS", "주문", "노출", "클릭", "CTR", "CPC"]
    tab_name = "키워드 TOP"

    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab_name, rows=250, cols=len(HEADERS))

    # 전체 교체
    all_values = [HEADERS] + keyword_rows
    ws.clear()
    ws.update(values=all_values, range_name=f"A1", value_input_option="RAW")

    # 좌정렬
    apply_left_align(sh, ws, 1, len(all_values) + 1, len(HEADERS))

    print(f"  ✅ {tab_name}: {len(keyword_rows)}개 키워드 업데이트")
    return len(keyword_rows)


# ── 관리시트 업데이트 ────────────────────────────────────────────
def mgmt_update_summary(sh, tab_name, summary_data):
    """관리시트 요약 탭: ₩/% 포맷, 상단 삽입(내림차순)"""
    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return 0

    existing_dates = get_existing_dates(ws)
    new_entries = [d for d in summary_data if d["date"] not in existing_dates]
    if not new_entries:
        print(f"  ⏭️ {tab_name}: 새로운 데이터 없음")
        return 0

    new_entries.sort(key=lambda x: x["date"], reverse=True)
    rows = []
    for d in new_entries:
        rows.append([
            d["date"], mgmt_money(d["_cost"]), mgmt_money(d["_sales"]),
            mgmt_pct(d["_roas"]), str(int(d["_orders"])),
            f'{int(d["_impressions"]):,}', f'{int(d["_clicks"]):,}',
            mgmt_pct(d["_ctr"], 2), mgmt_money(d["_cpc"]),
            mgmt_pct(d["_cvr"], 1), "",
        ])

    insert_rows_at_top(ws, rows, 11)
    apply_left_align(sh, ws, 2, 2 + len(rows), 11)
    dates = [d["date"] for d in new_entries]
    print(f"  ✅ {tab_name}: {len(new_entries)}일 추가 ({dates[0]} ~ {dates[-1]})")
    return len(new_entries)


def mgmt_update_campaign(sh, tab_name, campaign_data, raw_rows=None):
    """관리시트 캠페인별 탭: ₩/% 포맷, 상단 삽입(내림차순), 검색/비검색 열 포함"""
    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return 0

    existing_dates = get_existing_dates(ws)
    new_entries = [d for d in campaign_data if d["date"] not in existing_dates]
    if not new_entries:
        print(f"  ⏭️ {tab_name}: 새로운 데이터 없음")
        return 0

    zone_agg = defaultdict(lambda: {"cost": 0, "sales": 0})
    if raw_rows:
        for row in raw_rows:
            d = fmt_date(row.get("날짜", 0))
            camp = str(row.get("캠페인", row.get("캠페인명", "기타")))
            zone = row.get("광고 노출 지면") or row.get("노출 영역") or ""
            cost = float(row.get("광고비", 0) or 0)
            sales = float(row.get("총 전환매출액(1일)", 0) or 0)
            if zone == "검색 영역":
                zone_agg[(d, camp, "s")]["cost"] += cost
                zone_agg[(d, camp, "s")]["sales"] += sales
            elif zone in ("비검색 영역", "오디언스 플러스"):
                zone_agg[(d, camp, "ns")]["cost"] += cost
                zone_agg[(d, camp, "ns")]["sales"] += sales

    new_entries.sort(key=lambda x: x["date"], reverse=True)
    rows = []
    for d in new_entries:
        s = zone_agg.get((d["date"], d["campaign"], "s"), {"cost": 0, "sales": 0})
        ns = zone_agg.get((d["date"], d["campaign"], "ns"), {"cost": 0, "sales": 0})
        s_roas = safe_div(s["sales"], s["cost"]) * 100
        ns_roas = safe_div(ns["sales"], ns["cost"]) * 100
        rows.append([
            d["date"], d["campaign"], mgmt_money(d["_cost"]), mgmt_money(d["_sales"]),
            mgmt_pct(d["_roas"]), str(int(d["_orders"])),
            f'{int(d["_impressions"]):,}', f'{int(d["_clicks"]):,}',
            mgmt_pct(d["_ctr"], 2), mgmt_money(d["_cpc"]),
            mgmt_pct(d["_cvr"], 1), "",
            mgmt_money(s["cost"]), mgmt_money(s["sales"]), mgmt_pct(s_roas),
            mgmt_money(ns["cost"]), mgmt_money(ns["sales"]), mgmt_pct(ns_roas),
        ])

    insert_rows_at_top(ws, rows, 18)
    apply_left_align(sh, ws, 2, 2 + len(rows), 18)
    dates = sorted(set(d["date"] for d in new_entries), reverse=True)
    print(f"  ✅ {tab_name}: {len(new_entries)}행 추가 ({dates[0]} ~ {dates[-1]})")
    return len(new_entries)


def mgmt_update_zone(sh, tab_name, rows_data):
    """관리시트 검색/비검색 탭: 가로 병렬 (검색|비검색|합계), 하단 추가"""
    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return 0

    existing_dates = get_existing_dates(ws, date_col=1)
    if not existing_dates:
        all_vals = ws.get_all_values()
        for i, row in enumerate(all_vals):
            if row and re.match(r"^\d{4}-\d{2}-\d{2}$", str(row[0]).strip()):
                existing_dates.add(row[0].strip())

    dates_in_data = set()
    daily = defaultdict(lambda: {
        "search": {"cost": 0, "sales": 0, "orders": 0, "clicks": 0},
        "nonsearch": {"cost": 0, "sales": 0, "orders": 0, "clicks": 0},
    })
    for row in rows_data:
        date_str = fmt_date(row.get("날짜", 0))
        zone = row.get("광고 노출 지면") or row.get("노출 영역") or ""
        cost = float(row.get("광고비", 0) or 0)
        sales = float(row.get("총 전환매출액(1일)", 0) or 0)
        orders = float(row.get("총 주문수(1일)", 0) or 0)
        clicks = float(row.get("클릭수", 0) or 0)

        if zone == "검색 영역":
            d = daily[date_str]["search"]
        elif zone in ("비검색 영역", "오디언스 플러스"):
            d = daily[date_str]["nonsearch"]
        else:
            continue
        d["cost"] += cost
        d["sales"] += sales
        d["orders"] += orders
        d["clicks"] += clicks
        dates_in_data.add(date_str)

    new_dates = sorted(dates_in_data - existing_dates)
    if not new_dates:
        print(f"  ⏭️ {tab_name}: 새로운 데이터 없음")
        return 0

    rows_to_add = []
    for date_str in new_dates:
        s = daily[date_str]["search"]
        ns = daily[date_str]["nonsearch"]
        total_cost = s["cost"] + ns["cost"]
        total_sales = s["sales"] + ns["sales"]
        total_roas = safe_div(total_sales, total_cost) * 100

        rows_to_add.append([
            date_str,
            mgmt_money(s["cost"]), mgmt_money(s["sales"]),
            mgmt_pct(safe_div(s["sales"], s["cost"]) * 100),
            str(int(s["orders"])), str(int(s["clicks"])),
            mgmt_money(safe_div(s["cost"], s["clicks"])),
            mgmt_money(ns["cost"]), mgmt_money(ns["sales"]),
            mgmt_pct(safe_div(ns["sales"], ns["cost"]) * 100),
            str(int(ns["orders"])), str(int(ns["clicks"])),
            mgmt_money(safe_div(ns["cost"], ns["clicks"])),
            mgmt_money(total_cost), mgmt_money(total_sales),
            mgmt_pct(total_roas),
        ])

    ws.append_rows(rows_to_add, value_input_option="RAW")
    total_rows = len(ws.get_all_values())
    apply_left_align(sh, ws, total_rows - len(rows_to_add) + 1, total_rows + 1, 16)
    print(f"  ✅ {tab_name}: {len(new_dates)}일 추가 ({new_dates[0]} ~ {new_dates[-1]})")
    return len(new_dates)


# ── 메인 ──────────────────────────────────────────────────────
def run(vendor_ids=None, dry_run=False):
    if vendor_ids is None:
        vendor_ids = list(ACCOUNTS.keys())

    print(f"=== 쿠팡 광고 대시보드 v2 업데이트 ===")
    print(f"  시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  계정: {', '.join(ACCOUNTS[v]['name'] for v in vendor_ids)}")
    print(f"  데이터 경로: {DATA_DIR}")
    print(f"  시트: {SHEET_ID}")
    print()

    # 계정별 데이터 로드 & 집계
    all_account_data = {}
    all_keyword_rows_input = []  # (account_name, rows) 튜플 리스트

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
        by_zone = aggregate_daily_by_zone(rows)

        if summary:
            print(f"  📅 기간: {summary[0]['date']} ~ {summary[-1]['date']} ({len(summary)}일)")
        print()

        all_account_data[vid] = {
            "summary": summary,
            "by_campaign": by_campaign,
            "by_zone": by_zone,
        }

        all_keyword_rows_input.append((acct["name"], rows))
        all_account_data[vid]["raw_rows"] = rows

    if dry_run:
        print("\n[DRY RUN] 시트 업데이트를 건너뜁니다.")
        for vid, data in all_account_data.items():
            print(f"\n── {ACCOUNTS[vid]['name']} 요약 (최근 5일) ──")
            for d in data["summary"][:5]:
                print(f"  {d['date']}  광고비={d['cost']}  매출={d['sales']}  ROAS={d['roas']}  주문={d['orders']}")
        return all_account_data

    if not all_account_data:
        print("❌ 업데이트할 데이터가 없습니다.")
        return {}

    # 구글시트 연결 — 대시보드
    print("[시트] 대시보드 구글시트 연결 중...")
    sh = connect_sheet()
    print(f"  ✅ 시트 연결: {sh.title}")
    print()

    total_updated = 0
    for vid, data in all_account_data.items():
        acct = ACCOUNTS[vid]
        print(f"[{acct['name']}] 대시보드 시트 업데이트...")

        n = update_summary_tab(sh, acct["summary_tab"], data["summary"])
        total_updated += n
        n = update_campaign_tab(sh, acct["campaign_tab"], data["by_campaign"])
        total_updated += n
        n = update_zone_tab(sh, acct["zone_tab"], data["by_zone"])
        total_updated += n

    if all_keyword_rows_input:
        print("\n[키워드 TOP] 업데이트...")
        keyword_rows = aggregate_keyword_top(all_keyword_rows_input)
        n = update_keyword_top(sh, keyword_rows)
        total_updated += n

    # 관리시트 업데이트
    print("\n[관리시트] 구글시트 연결 중...")
    try:
        creds = Credentials.from_service_account_file(
            SA_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        gc = gspread.authorize(creds)
        mgmt_sh = gc.open_by_key(MGMT_SHEET_ID)
        print(f"  ✅ 관리시트 연결: {mgmt_sh.title}")

        for vid, data in all_account_data.items():
            acct = ACCOUNTS[vid]
            print(f"[{acct['name']}] 관리시트 업데이트...")

            n = mgmt_update_summary(mgmt_sh, acct["mgmt_summary_tab"], data["summary"])
            total_updated += n
            n = mgmt_update_campaign(mgmt_sh, acct["mgmt_campaign_tab"], data["by_campaign"], data.get("raw_rows"))
            total_updated += n

            if acct.get("mgmt_zone_tab"):
                n = mgmt_update_zone(mgmt_sh, acct["mgmt_zone_tab"], data["raw_rows"])
                total_updated += n

        # 관리시트 키워드 TOP
        if all_keyword_rows_input:
            print("\n[관리시트 키워드 TOP] 업데이트...")
            try:
                mgmt_kw_ws = mgmt_sh.worksheet("📊 키워드 TOP")
                HEADERS = ["계정", "키워드", "광고비", "매출", "ROAS", "주문", "노출", "클릭", "CTR", "CPC"]
                mgmt_kw_rows = []
                for row in keyword_rows:
                    mgmt_kw_rows.append(row)
                all_values = [HEADERS] + mgmt_kw_rows
                mgmt_kw_ws.clear()
                mgmt_kw_ws.update(values=all_values, range_name="A1", value_input_option="RAW")
                apply_left_align(mgmt_sh, mgmt_kw_ws, 1, len(all_values) + 1, len(HEADERS))
                print(f"  ✅ 📊 키워드 TOP: {len(mgmt_kw_rows)}개 업데이트")
                total_updated += len(mgmt_kw_rows)
            except gspread.WorksheetNotFound:
                print("  ⚠️ 📊 키워드 TOP 탭 없음 — 건너뜀")
    except Exception as e:
        print(f"  ❌ 관리시트 업데이트 실패: {e}")

    print(f"\n{'='*50}")
    print(f"✅ 완료! 총 {total_updated}개 행 업데이트")
    print(f"📊 대시보드: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
    print(f"📊 관리시트: https://docs.google.com/spreadsheets/d/{MGMT_SHEET_ID}")
    return all_account_data


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv or "--dry" in sys.argv

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
