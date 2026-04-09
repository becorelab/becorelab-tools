"""메타 광고 일일보고서 자동 생성 → 옵시디언 마크다운 저장
토큰 0으로 데이터 수집/정리, 분석은 두리가 읽고 수행
"""
import os
import sys
import json
import io
import requests
from datetime import datetime, timedelta, date

# Windows 콘솔 UTF-8 출력
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    META_ACCESS_TOKEN,
    META_AD_ACCOUNTS,
    META_API_VERSION,
    OBSIDIAN_AD_DIR,
)

BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"

# 이상 징후 기준값
THRESHOLDS = {
    "roas_good": 2.0,
    "roas_warn": 1.5,
    "roas_bad": 1.0,
    "cpp_warn": 20000,
    "ctr_target": 1.5,
    "atc_rate_target": 15.0,
    "aov_target": 36000,
}


def api_get(endpoint, params=None):
    """메타 API GET 요청"""
    p = {"access_token": META_ACCESS_TOKEN}
    if params:
        p.update(params)
    resp = requests.get(f"{BASE_URL}/{endpoint}", params=p, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_campaigns(account_id):
    """계정의 캠페인 목록"""
    data = api_get(
        f"{account_id}/campaigns",
        {
            "fields": "name,status,daily_budget,objective,bid_strategy",
            "limit": 50,
        },
    )
    return data.get("data", [])


def get_insights(account_id, target_date, level="campaign", campaign_id=None):
    """인사이트 데이터 조회
    level: campaign, ad, adset
    """
    endpoint = f"{campaign_id}/insights" if campaign_id else f"{account_id}/insights"
    fields = ",".join([
        "campaign_name", "campaign_id",
        "spend", "impressions", "clicks", "cpc", "cpm", "ctr",
        "actions", "action_values", "cost_per_action_type",
        "frequency", "reach",
    ])
    if level == "ad":
        fields += ",ad_name,ad_id"

    params = {
        "fields": fields,
        "time_range": json.dumps({
            "since": target_date,
            "until": target_date,
        }),
        "level": level,
        "limit": 100,
    }
    data = api_get(endpoint, params)
    return data.get("data", [])


def get_account_insights(account_id, target_date):
    """계정 전체 인사이트"""
    data = api_get(
        f"{account_id}/insights",
        {
            "fields": "spend,impressions,clicks,cpc,cpm,ctr,actions,action_values,frequency,reach",
            "time_range": json.dumps({
                "since": target_date,
                "until": target_date,
            }),
        },
    )
    return data.get("data", [{}])[0] if data.get("data") else {}


def extract_action(actions, action_type):
    """actions 배열에서 특정 타입의 값 추출"""
    if not actions:
        return 0
    for a in actions:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0


def extract_action_value(action_values, action_type):
    """action_values 배열에서 특정 타입의 값 추출"""
    if not action_values:
        return 0
    for a in action_values:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0


def calc_metrics(row):
    """인사이트 row에서 주요 지표 계산"""
    spend = float(row.get("spend", 0))
    impressions = int(row.get("impressions", 0))
    clicks = int(row.get("clicks", 0))
    actions = row.get("actions", [])
    action_values = row.get("action_values", [])

    purchases = extract_action(actions, "purchase")
    purchase_value = extract_action_value(action_values, "purchase")
    atc = extract_action(actions, "add_to_cart")
    ic = extract_action(actions, "initiate_checkout")
    link_clicks = extract_action(actions, "link_click")

    roas = purchase_value / spend if spend > 0 else 0
    cpp = spend / purchases if purchases > 0 else 0
    aov = purchase_value / purchases if purchases > 0 else 0
    cpc = float(row.get("cpc", 0))
    cpm = float(row.get("cpm", 0))
    ctr = float(row.get("ctr", 0))
    frequency = float(row.get("frequency", 0))
    reach = int(row.get("reach", 0))

    # 퍼널
    click_to_atc = (atc / link_clicks * 100) if link_clicks > 0 else 0
    atc_to_ic = (ic / atc * 100) if atc > 0 else 0
    ic_to_purchase = (purchases / ic * 100) if ic > 0 else 0

    return {
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "purchases": int(purchases),
        "purchase_value": purchase_value,
        "roas": roas,
        "cpp": cpp,
        "aov": aov,
        "cpc": cpc,
        "cpm": cpm,
        "ctr": ctr,
        "frequency": frequency,
        "reach": reach,
        "link_clicks": int(link_clicks),
        "atc": int(atc),
        "ic": int(ic),
        "click_to_atc": click_to_atc,
        "atc_to_ic": atc_to_ic,
        "ic_to_purchase": ic_to_purchase,
    }


def status_icon(value, good, warn):
    """값에 따른 상태 아이콘"""
    if value >= good:
        return "✅"
    elif value >= warn:
        return "⚠️"
    else:
        return "🔴"


def roas_icon(roas):
    return status_icon(roas, THRESHOLDS["roas_good"], THRESHOLDS["roas_warn"])


def fmt_krw(v):
    """원화 포맷"""
    if v >= 10000:
        return f"{v:,.0f}원"
    return f"{v:,.0f}원"


def fmt_pct(v):
    return f"{v:.1f}%"


def generate_report(target_date, prev_date=None):
    """일일 보고서 마크다운 생성"""
    lines = []
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekdays_kr[dt.weekday()]

    lines.append(f"# 📊 메타 광고 일일 리포트 | {target_date} ({weekday})")
    lines.append("")
    lines.append(f"> 자동 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    all_alerts = []
    total_spend = 0
    total_purchases = 0
    total_value = 0

    for account_key, account_id in META_AD_ACCOUNTS.items():
        account_name = "일비아" if account_key == "ilbia" else "세탁제품"
        emoji = "🟣" if account_key == "ilbia" else "🟠"

        # 계정 전체 인사이트
        acct_data = get_account_insights(account_id, target_date)
        if not acct_data:
            lines.append(f"## {emoji} {account_name} 계정")
            lines.append("데이터 없음")
            lines.append("")
            continue

        acct_metrics = calc_metrics(acct_data)
        total_spend += acct_metrics["spend"]
        total_purchases += acct_metrics["purchases"]
        total_value += acct_metrics["purchase_value"]

        # 전일 데이터
        prev_metrics = None
        if prev_date:
            prev_data = get_account_insights(account_id, prev_date)
            if prev_data:
                prev_metrics = calc_metrics(prev_data)

        lines.append(f"## {emoji} {account_name} 계정")
        lines.append("")

        # 핵심 지표 테이블
        lines.append("### 핵심 지표")
        lines.append("")
        lines.append("| 지표 | 값 | 전일 대비 | 상태 |")
        lines.append("|------|-----|----------|------|")

        def delta_str(cur, prev_val):
            if prev_val and prev_val != 0:
                pct = (cur - prev_val) / prev_val * 100
                arrow = "▲" if pct > 0 else "▼" if pct < 0 else "→"
                return f"{arrow} {abs(pct):.0f}%"
            return "-"

        m = acct_metrics
        pm = prev_metrics

        lines.append(f"| 지출 | {fmt_krw(m['spend'])} | {delta_str(m['spend'], pm['spend'] if pm else None)} | - |")
        lines.append(f"| 전환 | {m['purchases']}건 | {delta_str(m['purchases'], pm['purchases'] if pm else None)} | - |")
        lines.append(f"| ROAS | {m['roas']:.2f} | {delta_str(m['roas'], pm['roas'] if pm else None)} | {roas_icon(m['roas'])} |")
        lines.append(f"| 결과당비용 | {fmt_krw(m['cpp'])} | {delta_str(m['cpp'], pm['cpp'] if pm else None)} | {'⚠️' if m['cpp'] > THRESHOLDS['cpp_warn'] else '✅'} |")
        lines.append(f"| CPC | {fmt_krw(m['cpc'])} | {delta_str(m['cpc'], pm['cpc'] if pm else None)} | - |")
        lines.append(f"| CTR | {fmt_pct(m['ctr'])} | {delta_str(m['ctr'], pm['ctr'] if pm else None)} | {'✅' if m['ctr'] >= THRESHOLDS['ctr_target'] else '⚠️'} |")
        lines.append(f"| CPM | {fmt_krw(m['cpm'])} | {delta_str(m['cpm'], pm['cpm'] if pm else None)} | - |")
        lines.append(f"| AOV | {fmt_krw(m['aov'])} | {delta_str(m['aov'], pm['aov'] if pm else None)} | {'✅' if m['aov'] >= THRESHOLDS['aov_target'] else '🔴'} |")
        lines.append(f"| 도달 | {m['reach']:,} | {delta_str(m['reach'], pm['reach'] if pm else None)} | - |")
        lines.append(f"| 빈도 | {m['frequency']:.2f} | - | {'⚠️' if m['frequency'] > 2.5 else '✅'} |")
        lines.append("")

        # 퍼널 분석
        lines.append("### 퍼널 분석")
        lines.append("")
        lines.append("| 단계 | 수 | 전환율 | 상태 |")
        lines.append("|------|-----|--------|------|")
        lines.append(f"| 링크 클릭 | {m['link_clicks']} | - | - |")
        lines.append(f"| 장바구니 담기 (ATC) | {m['atc']} | Click→ATC {fmt_pct(m['click_to_atc'])} | {'✅' if m['click_to_atc'] >= THRESHOLDS['atc_rate_target'] else '🔴'} |")
        lines.append(f"| 결제 시작 (IC) | {m['ic']} | ATC→IC {fmt_pct(m['atc_to_ic'])} | - |")
        lines.append(f"| 구매 완료 | {m['purchases']} | IC→Purchase {fmt_pct(m['ic_to_purchase'])} | - |")
        lines.append("")

        # 캠페인별 성과
        campaigns = get_insights(account_id, target_date, level="campaign")
        if campaigns:
            lines.append("### 캠페인별 성과")
            lines.append("")
            lines.append("| 캠페인 | 상태 | 지출 | 전환 | ROAS | 결과당비용 | CPC | CTR | AOV |")
            lines.append("|--------|------|------|------|------|----------|-----|-----|-----|")

            for c in sorted(campaigns, key=lambda x: float(x.get("spend", 0)), reverse=True):
                cm = calc_metrics(c)
                if cm["spend"] == 0:
                    continue
                cname = c.get("campaign_name", "?")
                lines.append(
                    f"| {cname} | - | {fmt_krw(cm['spend'])} | {cm['purchases']}건 | "
                    f"{cm['roas']:.2f} {roas_icon(cm['roas'])} | {fmt_krw(cm['cpp'])} | "
                    f"{fmt_krw(cm['cpc'])} | {fmt_pct(cm['ctr'])} | {fmt_krw(cm['aov'])} |"
                )

                # 이상 징후 수집
                if cm["spend"] > 10000:
                    if cm["roas"] < THRESHOLDS["roas_bad"]:
                        all_alerts.append(f"🔴 {cname}: ROAS {cm['roas']:.2f} (적자)")
                    elif cm["roas"] < THRESHOLDS["roas_warn"]:
                        all_alerts.append(f"⚠️ {cname}: ROAS {cm['roas']:.2f} (목표 미달)")
                    if cm["cpp"] > THRESHOLDS["cpp_warn"]:
                        all_alerts.append(f"⚠️ {cname}: 결과당비용 {fmt_krw(cm['cpp'])}")

            lines.append("")

        # 소재별 성과 (광고 레벨)
        ads = get_insights(account_id, target_date, level="ad")
        if ads:
            active_ads = [a for a in ads if float(a.get("spend", 0)) > 0]
            if active_ads:
                lines.append("### 소재별 성과")
                lines.append("")
                lines.append("| 소재 | 지출 | 지출비중 | 전환 | ROAS | CPC | CTR |")
                lines.append("|------|------|---------|------|------|-----|-----|")

                total_ad_spend = sum(float(a.get("spend", 0)) for a in active_ads)
                for a in sorted(active_ads, key=lambda x: float(x.get("spend", 0)), reverse=True)[:10]:
                    am = calc_metrics(a)
                    ad_name = a.get("ad_name", "?")
                    share = (am["spend"] / total_ad_spend * 100) if total_ad_spend > 0 else 0
                    lines.append(
                        f"| {ad_name} | {fmt_krw(am['spend'])} | {fmt_pct(share)} | "
                        f"{am['purchases']}건 | {am['roas']:.2f} {roas_icon(am['roas'])} | "
                        f"{fmt_krw(am['cpc'])} | {fmt_pct(am['ctr'])} |"
                    )

                lines.append("")

        lines.append("---")
        lines.append("")

    # 합산 요약
    total_roas = total_value / total_spend if total_spend > 0 else 0
    lines.insert(3, f"**합산: 지출 {fmt_krw(total_spend)} | 전환 {total_purchases}건 | ROAS {total_roas:.2f} {roas_icon(total_roas)}**")
    lines.insert(4, "")

    # 이상 징후
    if all_alerts:
        lines.append("## ⚡ 이상 징후")
        lines.append("")
        for alert in all_alerts:
            lines.append(f"- {alert}")
        lines.append("")

    # 판단 기준 참고
    lines.append("## 📌 판단 기준")
    lines.append("")
    lines.append("| 지표 | 목표 | 경고 | 위험 |")
    lines.append("|------|------|------|------|")
    lines.append("| ROAS | 2.0+ ✅ | 1.5~2.0 ⚠️ | 1.0 미만 🔴 |")
    lines.append("| 결과당비용 | 16,000원 이하 | 20,000원 초과 ⚠️ | - |")
    lines.append("| CTR | 1.5%+ ✅ | 1.0~1.5% ⚠️ | - |")
    lines.append("| Click→ATC | 15%+ ✅ | 10~15% ⚠️ | 10% 미만 🔴 |")
    lines.append("| AOV | 36,000원+ ✅ | - | 미만 🔴 |")
    lines.append("| 빈도 (7일) | 2.5 이하 ✅ | 2.5 초과 ⚠️ | - |")
    lines.append("")

    return "\n".join(lines)


def save_report(target_date, content):
    """보고서를 옵시디언 볼트에 저장"""
    year = target_date[:4]
    year_dir = os.path.join(OBSIDIAN_AD_DIR, year)
    os.makedirs(year_dir, exist_ok=True)

    filepath = os.path.join(year_dir, f"{target_date}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def run_single(target_date):
    """특정 날짜 보고서 생성"""
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    prev_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    report = generate_report(target_date, prev_date)
    filepath = save_report(target_date, report)
    return filepath


def run_backfill(start_date, end_date):
    """과거 데이터 일괄 생성"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    current = start
    results = []
    total = (end - start).days + 1

    while current <= end:
        target = current.strftime("%Y-%m-%d")
        prev = (current - timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            report = generate_report(target, prev)
            filepath = save_report(target, report)
            results.append({"date": target, "status": "ok", "path": filepath})
            print(f"[{len(results)}/{total}] ✅ {target}")
        except Exception as e:
            results.append({"date": target, "status": "error", "error": str(e)})
            print(f"[{len(results)}/{total}] ❌ {target}: {e}")
        current += timedelta(days=1)

    return results


def run_yesterday():
    """어제 보고서 생성 (매일 자동 실행용)"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return run_single(yesterday)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="메타 광고 일일보고서 생성")
    parser.add_argument("--date", help="특정 날짜 (YYYY-MM-DD)")
    parser.add_argument("--backfill", nargs=2, metavar=("START", "END"),
                        help="과거 데이터 일괄 생성 (START END)")
    parser.add_argument("--yesterday", action="store_true", help="어제 보고서 생성")

    args = parser.parse_args()

    if args.backfill:
        results = run_backfill(args.backfill[0], args.backfill[1])
        ok = sum(1 for r in results if r["status"] == "ok")
        print(f"\n완료: {ok}/{len(results)}건 성공")
    elif args.date:
        path = run_single(args.date)
        print(f"✅ 저장: {path}")
    elif args.yesterday:
        path = run_yesterday()
        print(f"✅ 저장: {path}")
    else:
        path = run_yesterday()
        print(f"✅ 저장: {path}")
