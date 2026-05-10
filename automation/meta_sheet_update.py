"""메타 광고 데이터 → 성락 오빠 구글시트 자동 업데이트

매일 아침 8시 크론 실행:
  - 어제 날짜의 캠페인별 인사이트 조회
  - 전환(daily), 전환(daily) ATC 시트에 자동 입력
  - 수식 열(CTR/CPC/CPM/CVR/ROAS)은 기존 수식이 자동 계산
"""
import os
import sys
import json
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from config import META_ACCESS_TOKEN, META_AD_ACCOUNTS, META_API_VERSION

import gspread
from google.oauth2.service_account import Credentials

META_BASE = f"https://graph.facebook.com/{META_API_VERSION}"
SHEET_ID = "1_n7vHG1Gf1cOktmMiIG7cpEI2m34f4XeWaTd4dFskB0"
SA_KEY = "/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json"

WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]


def get_insights(account_id: str, date_str: str) -> list:
    """Meta API에서 캠페인별 인사이트 조회 (하루치)"""
    fields = ",".join([
        "campaign_name", "campaign_id",
        "spend", "impressions", "clicks",
        "actions", "action_values",
    ])
    params = {
        "access_token": META_ACCESS_TOKEN,
        "fields": fields,
        "level": "campaign",
        "limit": "100",
        "time_range": json.dumps({"since": date_str, "until": date_str}),
    }
    resp = requests.get(f"{META_BASE}/{account_id}/insights", params=params, timeout=30)
    data = resp.json()
    if "error" in data:
        print(f"  ❌ API 에러: {data['error'].get('message', '')}")
        return []
    return data.get("data", [])


def extract_action(actions, action_type):
    if not actions:
        return 0
    for a in actions:
        if a.get("action_type") == action_type:
            return int(float(a.get("value", 0)))
    return 0


def extract_action_value(action_values, action_type):
    if not action_values:
        return 0
    for a in action_values:
        if a.get("action_type") == action_type:
            return int(float(a.get("value", 0)))
    return 0


def parse_campaign_data(rows: list) -> dict:
    """캠페인별 데이터를 분류"""
    result = {"purchase": [], "atc": [], "traffic": []}
    for row in rows:
        name = row.get("campaign_name", "")
        spend = int(float(row.get("spend", 0)))
        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))
        actions = row.get("actions", [])
        action_values = row.get("action_values", [])

        purchases = extract_action(actions, "purchase")
        purchase_value = extract_action_value(action_values, "purchase")
        atc_count = extract_action(actions, "add_to_cart")

        entry = {
            "name": name,
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "purchases": purchases,
            "purchase_value": purchase_value,
            "atc": atc_count,
        }

        if "ATC" in name.upper():
            result["atc"].append(entry)
        elif "traffic" in name.lower() or "트래픽" in name:
            result["traffic"].append(entry)
        else:
            result["purchase"].append(entry)

    return result


def find_date_row(ws, date_label: str, search_from_bottom=True) -> int:
    """시트에서 날짜 라벨에 해당하는 행 번호 찾기"""
    all_dates = ws.col_values(1)
    if search_from_bottom:
        for i in range(len(all_dates) - 1, 0, -1):
            if all_dates[i].strip() == date_label:
                return i + 1
    else:
        for i, d in enumerate(all_dates):
            if d.strip() == date_label:
                return i + 1
    return 0


def get_product_key(campaign_name: str) -> str:
    """캠페인 이름에서 제품 구분"""
    name_lower = campaign_name.lower()
    if "식세기" in name_lower or "식기세척" in name_lower:
        return "food"
    elif "건조기" in name_lower or "시트" in name_lower:
        return "dryer"
    else:
        return "other"


def update_conversion_daily(sh, date_label: str, campaigns: list):
    """전환(daily) 시트 업데이트"""
    ws = sh.worksheet("전환(daily)")
    row = find_date_row(ws, date_label)
    if not row:
        print(f"  ⚠️ 전환(daily)에서 '{date_label}' 행을 찾을 수 없음")
        return False

    total_spend = sum(c["spend"] for c in campaigns)
    total_impressions = sum(c["impressions"] for c in campaigns)
    total_clicks = sum(c["clicks"] for c in campaigns)
    total_purchases = sum(c["purchases"] for c in campaigns)
    total_pv = sum(c["purchase_value"] for c in campaigns)

    updates = [
        {"range": f"B{row}", "values": [[total_spend]]},
        {"range": f"C{row}", "values": [[total_impressions]]},
        {"range": f"D{row}", "values": [[total_clicks]]},
        {"range": f"H{row}", "values": [[total_purchases]]},
        {"range": f"I{row}", "values": [[total_pv]]},
    ]

    food_campaigns = [c for c in campaigns if get_product_key(c["name"]) == "food"]
    other_campaigns = [c for c in campaigns if get_product_key(c["name"]) != "food"]

    if food_campaigns:
        food_spend = sum(c["spend"] for c in food_campaigns)
        food_pv = sum(c["purchase_value"] for c in food_campaigns)
        updates.append({"range": f"O{row}", "values": [[food_spend]]})
        updates.append({"range": f"P{row}", "values": [[food_pv]]})

    if other_campaigns:
        other_spend = sum(c["spend"] for c in other_campaigns)
        other_pv = sum(c["purchase_value"] for c in other_campaigns)
        updates.append({"range": f"W{row}", "values": [[other_spend]]})
        updates.append({"range": f"X{row}", "values": [[other_pv]]})

    ws.batch_update(updates, value_input_option="RAW")
    print(f"  ✅ 전환(daily) [{row}행] 지출=₩{total_spend:,} 전환={total_purchases} 매출=₩{total_pv:,}")
    return True


def update_atc_daily(sh, date_label: str, campaigns: list):
    """전환(daily) ATC 시트 업데이트"""
    if not campaigns:
        print(f"  ⏭️ ATC 캠페인 데이터 없음")
        return True

    ws = sh.worksheet("전환(daily) ATC")
    row = find_date_row(ws, date_label)
    if not row:
        print(f"  ⚠️ 전환(daily) ATC에서 '{date_label}' 행을 찾을 수 없음")
        return False

    total_spend = sum(c["spend"] for c in campaigns)
    total_impressions = sum(c["impressions"] for c in campaigns)
    total_clicks = sum(c["clicks"] for c in campaigns)
    total_atc = sum(c["atc"] for c in campaigns)
    total_pv = sum(c["purchase_value"] for c in campaigns)

    updates = [
        {"range": f"B{row}", "values": [[total_spend]]},
        {"range": f"C{row}", "values": [[total_impressions]]},
        {"range": f"D{row}", "values": [[total_clicks]]},
        {"range": f"I{row}", "values": [[total_atc]]},
        {"range": f"J{row}", "values": [[total_pv]]},
    ]

    ws.batch_update(updates, value_input_option="RAW")
    print(f"  ✅ 전환(daily) ATC [{row}행] 지출=₩{total_spend:,} ATC={total_atc} 매출=₩{total_pv:,}")
    return True


def make_date_label(dt: datetime) -> str:
    """datetime → 시트 날짜 라벨 (예: '05 8 금')"""
    weekday = WEEKDAYS_KR[dt.weekday()]
    return f"{dt.month:02d} {dt.day} {weekday}"


def run(target_date: str = None):
    """메인 실행"""
    if target_date:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        dt = datetime.now() - timedelta(days=1)

    date_str = dt.strftime("%Y-%m-%d")
    date_label = make_date_label(dt)

    print(f"=== 메타 광고 → 구글시트 업데이트 ===")
    print(f"  날짜: {date_str} ({date_label})")
    print(f"  시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    account_id = META_AD_ACCOUNTS.get("일비아", "act_939432264476274")
    print(f"[1/3] Meta API 조회 (일비아)...")
    rows = get_insights(account_id, date_str)
    if not rows:
        print("  ⚠️ 데이터 없음 (광고 미집행일 가능)")
        return

    campaigns = parse_campaign_data(rows)
    print(f"  Purchase 캠페인: {len(campaigns['purchase'])}개")
    print(f"  ATC 캠페인: {len(campaigns['atc'])}개")
    for c in campaigns["purchase"]:
        print(f"    {c['name']}: ₩{c['spend']:,} / 전환 {c['purchases']} / 매출 ₩{c['purchase_value']:,}")
    for c in campaigns["atc"]:
        print(f"    {c['name']}: ₩{c['spend']:,} / ATC {c['atc']}")

    print(f"\n[2/3] 구글시트 연결...")
    creds = Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    print(f"\n[3/3] 시트 업데이트 ('{date_label}')...")
    update_conversion_daily(sh, date_label, campaigns["purchase"])
    update_atc_daily(sh, date_label, campaigns["atc"])

    print(f"\n완료! ✅")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run(target)
