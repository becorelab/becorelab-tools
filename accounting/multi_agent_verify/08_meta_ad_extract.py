"""
메타 광고 14개월치 일일 보고서 추출 스크립트
입력: 옵시디언 일일 보고서 (2025-01-01 ~ 2026-04-10)
출력: 08_meta_ad_data.json, 08_meta_ad_report.md
"""
import os
import re
import json
import sys
import io
from datetime import date, timedelta
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"C:/Users/info/Documents/비코어랩/01. Becorelab AI Agent Team/📢 Ad Performance"
OUT_DIR = r"C:/Users/info/ClaudeAITeam/accounting/multi_agent_verify"
OUT_JSON = os.path.join(OUT_DIR, "08_meta_ad_data.json")
OUT_REPORT = os.path.join(OUT_DIR, "08_meta_ad_report.md")

START = date(2025, 1, 1)
END = date(2026, 4, 10)


def clean_num(s):
    """숫자 파싱 (콤마, 원, %, 이모지, 화살표 제거)"""
    if s is None:
        return 0
    s = str(s).strip()
    # 이모지/화살표/상태 문자 제거
    for ch in ["✅", "⚠️", "🔴", "▲", "▼", "→", "원", ",", "건", "%"]:
        s = s.replace(ch, "")
    s = s.strip()
    if s in ("", "-", "–"):
        return 0
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return 0


def split_row(line):
    """| a | b | c | 형태의 row를 리스트로 분리"""
    line = line.strip()
    if not line.startswith("|"):
        return None
    parts = [p.strip() for p in line.strip("|").split("|")]
    return parts


def is_separator(line):
    """구분선 |------|------| 체크"""
    return bool(re.match(r"^\|[\s\-:|]+\|?\s*$", line.strip()))


def parse_table(lines, start_idx):
    """
    start_idx 부터 테이블 파싱
    returns: (header, rows, next_idx)
    """
    i = start_idx
    n = len(lines)
    # 헤더 찾기
    while i < n and not lines[i].strip().startswith("|"):
        i += 1
    if i >= n:
        return None, [], i
    header = split_row(lines[i])
    i += 1
    # 구분선 스킵
    if i < n and is_separator(lines[i]):
        i += 1
    rows = []
    while i < n:
        ln = lines[i]
        if not ln.strip().startswith("|"):
            break
        if is_separator(ln):
            i += 1
            continue
        parts = split_row(ln)
        if parts:
            rows.append(parts)
        i += 1
    return header, rows, i


def parse_core_kpi(rows):
    """핵심 지표 테이블 파싱"""
    d = {}
    m = {
        "지출": "spend",
        "전환": "conversions",
        "ROAS": "roas",
        "결과당비용": "cost_per_result",
        "CPC": "cpc",
        "CTR": "ctr",
        "CPM": "cpm",
        "AOV": "aov",
        "도달": "reach",
        "빈도": "frequency",
    }
    for row in rows:
        if len(row) < 2:
            continue
        key = row[0].strip()
        val = row[1].strip()
        if key in m:
            d[m[key]] = clean_num(val)
    return d


def parse_funnel(rows):
    """퍼널 테이블 파싱"""
    d = {}
    m = {
        "링크 클릭": "link_click",
        "장바구니 담기 (ATC)": "atc",
        "결제 시작 (IC)": "ic",
        "구매 완료": "purchase",
    }
    for row in rows:
        if len(row) < 2:
            continue
        key = row[0].strip()
        val = row[1].strip()
        if key in m:
            d[m[key]] = clean_num(val)
    return d


def parse_campaigns(rows):
    """캠페인 테이블 파싱 (여러 헤더 형태 대응)"""
    result = []
    for row in rows:
        if len(row) < 5:
            continue
        name = row[0].strip()
        if not name or name in ("캠페인", "-"):
            continue
        # 보통: 캠페인 | 상태 | 지출 | 전환 | ROAS | 결과당비용 | CPC | CTR | AOV
        # 상태 컬럼 있을 수도 / 없을 수도 있음
        try:
            # 상태가 있는 형태 (col count = 9)
            if len(row) >= 9:
                c = {
                    "name": name,
                    "spend": clean_num(row[2]),
                    "conversions": clean_num(row[3]),
                    "roas": clean_num(row[4]),
                    "cpc": clean_num(row[6]),
                    "ctr": clean_num(row[7]),
                    "aov": clean_num(row[8]),
                }
            else:
                c = {
                    "name": name,
                    "spend": clean_num(row[1]) if len(row) > 1 else 0,
                    "conversions": clean_num(row[2]) if len(row) > 2 else 0,
                    "roas": clean_num(row[3]) if len(row) > 3 else 0,
                    "cpc": clean_num(row[5]) if len(row) > 5 else 0,
                    "ctr": clean_num(row[6]) if len(row) > 6 else 0,
                    "aov": clean_num(row[7]) if len(row) > 7 else 0,
                }
            result.append(c)
        except Exception:
            continue
    return result


def parse_creatives(rows):
    """소재 테이블 파싱 | 소재 | 지출 | 지출비중 | 전환 | ROAS | CPC | CTR |"""
    result = []
    for row in rows:
        if len(row) < 7:
            continue
        name = row[0].strip()
        if not name or name == "소재":
            continue
        try:
            c = {
                "name": name,
                "spend": clean_num(row[1]),
                "share": clean_num(row[2]),
                "conversions": clean_num(row[3]),
                "roas": clean_num(row[4]),
                "cpc": clean_num(row[5]),
                "ctr": clean_num(row[6]),
            }
            result.append(c)
        except Exception:
            continue
    return result


def parse_file(path, dt_str):
    """한 파일 파싱"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")

    data = {
        "date": dt_str,
        "combined": None,
        "ilbia": None,
        "laundry": None,
        "campaigns_ilbia": [],
        "campaigns_laundry": [],
        "creatives_ilbia": [],
        "creatives_laundry": [],
    }

    # 합산 줄
    for ln in lines:
        m = re.search(r"합산:\s*지출\s*([\d,]+)원\s*\|\s*전환\s*(\d+)건\s*\|\s*ROAS\s*([\d.]+)", ln)
        if m:
            data["combined"] = {
                "spend": clean_num(m.group(1)),
                "conversions": clean_num(m.group(2)),
                "roas": clean_num(m.group(3)),
            }
            break

    # 섹션 분리
    # 🟣 일비아 계정 ~ --- (또는 🟠까지)
    # 🟠 세탁제품 계정 ~ ## ⚡

    def find_section(start_marker, end_markers):
        start = -1
        for i, ln in enumerate(lines):
            if start_marker in ln:
                start = i
                break
        if start == -1:
            return None, None
        end = len(lines)
        for i in range(start + 1, len(lines)):
            for em in end_markers:
                if lines[i].strip().startswith(em):
                    return start, i
        return start, end

    ilbia_start, ilbia_end = find_section("🟣 일비아 계정", ["## 🟠", "## ⚡", "---"])
    laundry_start, laundry_end = find_section("🟠 세탁제품 계정", ["## ⚡", "## 📌", "---"])

    def parse_section(start, end, is_ilbia):
        if start is None:
            return
        sec = lines[start:end]
        # "데이터 없음" 체크
        sec_text = "\n".join(sec)
        if "데이터 없음" in sec_text:
            return

        acct = {}
        # 핵심 지표
        i = 0
        while i < len(sec):
            ln = sec[i].strip()
            if ln.startswith("### 핵심 지표"):
                _, rows, next_i = parse_table(sec, i + 1)
                kpi = parse_core_kpi(rows)
                acct.update(kpi)
                i = next_i
                continue
            if ln.startswith("### 퍼널 분석"):
                _, rows, next_i = parse_table(sec, i + 1)
                funnel = parse_funnel(rows)
                acct.update(funnel)
                i = next_i
                continue
            if ln.startswith("### 캠페인별 성과"):
                _, rows, next_i = parse_table(sec, i + 1)
                camps = parse_campaigns(rows)
                if is_ilbia:
                    data["campaigns_ilbia"] = camps
                else:
                    data["campaigns_laundry"] = camps
                i = next_i
                continue
            if ln.startswith("### 소재별 성과"):
                _, rows, next_i = parse_table(sec, i + 1)
                cres = parse_creatives(rows)
                if is_ilbia:
                    data["creatives_ilbia"] = cres
                else:
                    data["creatives_laundry"] = cres
                i = next_i
                continue
            i += 1

        # 지출 0이면 null (실질적으로 데이터 없음)
        if acct and acct.get("spend", 0) == 0 and acct.get("conversions", 0) == 0:
            return
        if not acct:
            return

        if is_ilbia:
            data["ilbia"] = acct
        else:
            data["laundry"] = acct

    parse_section(ilbia_start, ilbia_end, True)
    parse_section(laundry_start, laundry_end, False)

    return data


def categorize_creative(name):
    """소재명 카테고리 분류"""
    n = name.lower()
    # 원본 그대로도 매칭
    if "식세기리타겟" in name or "식세기 리타겟" in name:
        return "식세기리타겟"
    if "식세기" in name:
        return "식세기"
    if "캡슐세제" in name or "캡슐" in name:
        return "캡슐세제"
    if "얼룩" in name:
        return "얼룩제거제"
    if "섬유탈취" in name or "탈취" in name:
        return "섬유탈취제"
    if "건조기시트" in name or "건조기" in name or "드라이어시트" in name:
        return "건조기시트"
    if "세탁세제" in name:
        return "세탁세제"
    if "세제" in name:
        return "세제기타"
    return "기타"


def main():
    print(f"[시작] 메타 광고 데이터 추출 {START} ~ {END}")

    daily_list = []
    missing = []
    cur = START
    total_days = (END - START).days + 1
    parsed = 0

    while cur <= END:
        dt_str = cur.isoformat()
        year = cur.year
        path = os.path.join(BASE, str(year), f"{dt_str}.md")
        if os.path.exists(path):
            try:
                d = parse_file(path, dt_str)
                daily_list.append(d)
                parsed += 1
            except Exception as e:
                print(f"[에러] {dt_str}: {e}")
                missing.append(dt_str)
        else:
            missing.append(dt_str)
        cur += timedelta(days=1)

        if parsed % 30 == 0 and parsed > 0:
            print(f"  진행 {parsed}/{total_days} ({dt_str})")

    print(f"[완료] 파싱 {parsed}개, 누락 {len(missing)}개")

    # 월별 집계
    monthly = defaultdict(lambda: {
        "ilbia": {"spend": 0, "conversions": 0, "revenue": 0, "link_click": 0, "atc": 0, "ic": 0, "purchase": 0},
        "laundry": {"spend": 0, "conversions": 0, "revenue": 0, "link_click": 0, "atc": 0, "ic": 0, "purchase": 0},
        "combined": {"spend": 0, "conversions": 0, "revenue": 0},
    })

    for d in daily_list:
        ym = d["date"][:7]
        if d.get("ilbia"):
            i = d["ilbia"]
            monthly[ym]["ilbia"]["spend"] += i.get("spend", 0)
            monthly[ym]["ilbia"]["conversions"] += i.get("conversions", 0)
            # revenue = spend * roas
            monthly[ym]["ilbia"]["revenue"] += i.get("spend", 0) * i.get("roas", 0)
            monthly[ym]["ilbia"]["link_click"] += i.get("link_click", 0)
            monthly[ym]["ilbia"]["atc"] += i.get("atc", 0)
            monthly[ym]["ilbia"]["ic"] += i.get("ic", 0)
            monthly[ym]["ilbia"]["purchase"] += i.get("purchase", 0)
        if d.get("laundry"):
            l = d["laundry"]
            monthly[ym]["laundry"]["spend"] += l.get("spend", 0)
            monthly[ym]["laundry"]["conversions"] += l.get("conversions", 0)
            monthly[ym]["laundry"]["revenue"] += l.get("spend", 0) * l.get("roas", 0)
            monthly[ym]["laundry"]["link_click"] += l.get("link_click", 0)
            monthly[ym]["laundry"]["atc"] += l.get("atc", 0)
            monthly[ym]["laundry"]["ic"] += l.get("ic", 0)
            monthly[ym]["laundry"]["purchase"] += l.get("purchase", 0)
        if d.get("combined"):
            c = d["combined"]
            monthly[ym]["combined"]["spend"] += c.get("spend", 0)
            monthly[ym]["combined"]["conversions"] += c.get("conversions", 0)
            monthly[ym]["combined"]["revenue"] += c.get("spend", 0) * c.get("roas", 0)

    # ROAS 계산 (revenue/spend)
    monthly_out = {}
    for ym in sorted(monthly.keys()):
        m = monthly[ym]
        out = {}
        for acct in ("ilbia", "laundry", "combined"):
            a = m[acct]
            roas = (a["revenue"] / a["spend"]) if a["spend"] > 0 else 0
            out[acct] = {
                "spend": round(a["spend"]),
                "conversions": a["conversions"],
                "revenue": round(a["revenue"]),
                "roas": round(roas, 2),
            }
            if "link_click" in a:
                out[acct]["link_click"] = a.get("link_click", 0)
                out[acct]["atc"] = a.get("atc", 0)
                out[acct]["ic"] = a.get("ic", 0)
                out[acct]["purchase"] = a.get("purchase", 0)
        monthly_out[ym] = out

    # 캠페인 14개월 누적 (계정별)
    def agg_campaigns(key):
        agg = defaultdict(lambda: {"spend": 0, "conversions": 0, "revenue": 0, "days": 0})
        for d in daily_list:
            for c in d.get(key, []):
                name = c["name"]
                agg[name]["spend"] += c.get("spend", 0)
                agg[name]["conversions"] += c.get("conversions", 0)
                agg[name]["revenue"] += c.get("spend", 0) * c.get("roas", 0)
                if c.get("spend", 0) > 0:
                    agg[name]["days"] += 1
        result = []
        for name, a in agg.items():
            roas = (a["revenue"] / a["spend"]) if a["spend"] > 0 else 0
            result.append({
                "name": name,
                "total_spend": round(a["spend"]),
                "total_conversions": a["conversions"],
                "avg_roas": round(roas, 2),
                "active_days": a["days"],
            })
        result.sort(key=lambda x: x["total_spend"], reverse=True)
        return result

    top_camp_ilbia = agg_campaigns("campaigns_ilbia")
    top_camp_laundry = agg_campaigns("campaigns_laundry")

    # 소재 카테고리 분석 (일비아 기준 — 세탁은 희소)
    cat_agg = defaultdict(lambda: {"spend": 0, "conversions": 0, "revenue": 0})
    for d in daily_list:
        for c in d.get("creatives_ilbia", []):
            cat = categorize_creative(c["name"])
            cat_agg[cat]["spend"] += c.get("spend", 0)
            cat_agg[cat]["conversions"] += c.get("conversions", 0)
            cat_agg[cat]["revenue"] += c.get("spend", 0) * c.get("roas", 0)
        for c in d.get("creatives_laundry", []):
            cat = categorize_creative(c["name"])
            cat_agg[cat]["spend"] += c.get("spend", 0)
            cat_agg[cat]["conversions"] += c.get("conversions", 0)
            cat_agg[cat]["revenue"] += c.get("spend", 0) * c.get("roas", 0)

    total_cat_spend = sum(v["spend"] for v in cat_agg.values())
    creative_categories = {}
    for cat, a in cat_agg.items():
        roas = (a["revenue"] / a["spend"]) if a["spend"] > 0 else 0
        share = (a["spend"] / total_cat_spend) if total_cat_spend > 0 else 0
        creative_categories[cat] = {
            "spend": round(a["spend"]),
            "conversions": a["conversions"],
            "avg_roas": round(roas, 2),
            "share": round(share, 4),
        }

    # 총합
    ilbia_spend = sum(m["ilbia"]["spend"] for m in monthly_out.values())
    ilbia_rev = sum(m["ilbia"]["revenue"] for m in monthly_out.values())
    ilbia_conv = sum(m["ilbia"]["conversions"] for m in monthly_out.values())
    laundry_spend = sum(m["laundry"]["spend"] for m in monthly_out.values())
    laundry_rev = sum(m["laundry"]["revenue"] for m in monthly_out.values())
    laundry_conv = sum(m["laundry"]["conversions"] for m in monthly_out.values())
    combined_spend = sum(m["combined"]["spend"] for m in monthly_out.values())
    combined_rev = sum(m["combined"]["revenue"] for m in monthly_out.values())
    combined_conv = sum(m["combined"]["conversions"] for m in monthly_out.values())

    totals = {
        "ilbia_spend": ilbia_spend,
        "ilbia_revenue": ilbia_rev,
        "ilbia_conversions": ilbia_conv,
        "ilbia_avg_roas": round(ilbia_rev / ilbia_spend, 2) if ilbia_spend > 0 else 0,
        "laundry_spend": laundry_spend,
        "laundry_revenue": laundry_rev,
        "laundry_conversions": laundry_conv,
        "laundry_avg_roas": round(laundry_rev / laundry_spend, 2) if laundry_spend > 0 else 0,
        "combined_spend": combined_spend,
        "combined_revenue": combined_rev,
        "combined_conversions": combined_conv,
        "combined_avg_roas": round(combined_rev / combined_spend, 2) if combined_spend > 0 else 0,
    }

    result = {
        "source": "옵시디언 일일 보고서",
        "date_range": {
            "start": START.isoformat(),
            "end": END.isoformat(),
            "days_parsed": parsed,
            "days_missing": missing,
        },
        "daily": daily_list,
        "monthly": monthly_out,
        "top_campaigns": {
            "ilbia": top_camp_ilbia[:20],
            "laundry": top_camp_laundry[:20],
        },
        "creative_categories": creative_categories,
        "totals": totals,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[저장] {OUT_JSON}")

    # 보고서 작성
    write_report(result)
    print(f"[저장] {OUT_REPORT}")

    # 콘솔 요약
    print("\n" + "=" * 60)
    print("[요약] 14개월 메타 광고")
    print("=" * 60)
    print(f"기간: {START} ~ {END}")
    print(f"파싱: {parsed}일, 누락: {len(missing)}일")
    print(f"\n[총합]")
    print(f"  일비아    : 지출 {ilbia_spend:>12,}원  매출 {ilbia_rev:>12,.0f}원  ROAS {totals['ilbia_avg_roas']:.2f}")
    print(f"  세탁제품  : 지출 {laundry_spend:>12,}원  매출 {laundry_rev:>12,.0f}원  ROAS {totals['laundry_avg_roas']:.2f}")
    print(f"  합산      : 지출 {combined_spend:>12,}원  매출 {combined_rev:>12,.0f}원  ROAS {totals['combined_avg_roas']:.2f}")

    if combined_spend > 0:
        print(f"\n[비중] 일비아 {ilbia_spend/combined_spend*100:.1f}% / 세탁제품 {laundry_spend/combined_spend*100:.1f}%")

    print(f"\n[월별]")
    print(f"{'월':8} {'일비아지출':>12} {'일비아ROAS':>10} {'세탁지출':>12} {'세탁ROAS':>10} {'합산지출':>12} {'합산ROAS':>10}")
    for ym in sorted(monthly_out.keys()):
        m = monthly_out[ym]
        print(f"{ym:8} {m['ilbia']['spend']:>12,} {m['ilbia']['roas']:>10.2f} {m['laundry']['spend']:>12,} {m['laundry']['roas']:>10.2f} {m['combined']['spend']:>12,} {m['combined']['roas']:>10.2f}")

    print(f"\n[소재 카테고리 Top]")
    sorted_cats = sorted(creative_categories.items(), key=lambda x: x[1]["spend"], reverse=True)
    for cat, v in sorted_cats:
        print(f"  {cat:12} 지출 {v['spend']:>12,}원  ROAS {v['avg_roas']:.2f}  비중 {v['share']*100:.1f}%  전환 {v['conversions']}")


def write_report(result):
    lines = []
    lines.append("# 📊 메타 광고 14개월 분석 보고서")
    lines.append("")
    r = result["date_range"]
    lines.append(f"- 기간: {r['start']} ~ {r['end']}")
    lines.append(f"- 파싱: {r['days_parsed']}일 / 누락: {len(r['days_missing'])}일")
    lines.append(f"- 소스: 옵시디언 일일 보고서")
    lines.append("")

    t = result["totals"]
    lines.append("## 총합")
    lines.append("")
    lines.append("| 구분 | 지출 | 전환 | 매출 | ROAS |")
    lines.append("|------|-----:|-----:|-----:|-----:|")
    lines.append(f"| 일비아 | {t['ilbia_spend']:,}원 | {t['ilbia_conversions']:,}건 | {t['ilbia_revenue']:,}원 | {t['ilbia_avg_roas']} |")
    lines.append(f"| 세탁제품 | {t['laundry_spend']:,}원 | {t['laundry_conversions']:,}건 | {t['laundry_revenue']:,}원 | {t['laundry_avg_roas']} |")
    lines.append(f"| 합산 | {t['combined_spend']:,}원 | {t['combined_conversions']:,}건 | {t['combined_revenue']:,}원 | {t['combined_avg_roas']} |")
    lines.append("")

    if t["combined_spend"] > 0:
        il_pct = t["ilbia_spend"] / t["combined_spend"] * 100
        ln_pct = t["laundry_spend"] / t["combined_spend"] * 100
        lines.append(f"- 계정 비중: 일비아 **{il_pct:.1f}%** / 세탁제품 **{ln_pct:.1f}%**")
        lines.append("")

    lines.append("## 월별 성과")
    lines.append("")
    lines.append("| 월 | 일비아 지출 | 일비아 ROAS | 세탁 지출 | 세탁 ROAS | 합산 지출 | 합산 ROAS |")
    lines.append("|----|-----:|-----:|-----:|-----:|-----:|-----:|")
    for ym in sorted(result["monthly"].keys()):
        m = result["monthly"][ym]
        lines.append(f"| {ym} | {m['ilbia']['spend']:,}원 | {m['ilbia']['roas']} | {m['laundry']['spend']:,}원 | {m['laundry']['roas']} | {m['combined']['spend']:,}원 | {m['combined']['roas']} |")
    lines.append("")

    lines.append("## 일비아 캠페인 Top 10 (14개월 누적 지출 기준)")
    lines.append("")
    lines.append("| 순위 | 캠페인 | 총 지출 | 전환 | 평균 ROAS | 활성일 |")
    lines.append("|------|--------|-------:|-----:|-----:|-----:|")
    for i, c in enumerate(result["top_campaigns"]["ilbia"][:10], 1):
        lines.append(f"| {i} | {c['name']} | {c['total_spend']:,}원 | {c['total_conversions']}건 | {c['avg_roas']} | {c['active_days']}일 |")
    lines.append("")

    if result["top_campaigns"]["laundry"]:
        lines.append("## 세탁제품 캠페인 Top 10")
        lines.append("")
        lines.append("| 순위 | 캠페인 | 총 지출 | 전환 | 평균 ROAS | 활성일 |")
        lines.append("|------|--------|-------:|-----:|-----:|-----:|")
        for i, c in enumerate(result["top_campaigns"]["laundry"][:10], 1):
            lines.append(f"| {i} | {c['name']} | {c['total_spend']:,}원 | {c['total_conversions']}건 | {c['avg_roas']} | {c['active_days']}일 |")
        lines.append("")

    lines.append("## 소재 카테고리 효율 랭킹")
    lines.append("")
    lines.append("| 카테고리 | 지출 | 비중 | 전환 | 평균 ROAS |")
    lines.append("|---------|-----:|-----:|-----:|-----:|")
    sorted_cats = sorted(result["creative_categories"].items(), key=lambda x: x[1]["spend"], reverse=True)
    for cat, v in sorted_cats:
        lines.append(f"| {cat} | {v['spend']:,}원 | {v['share']*100:.1f}% | {v['conversions']}건 | {v['avg_roas']} |")
    lines.append("")

    # 인사이트 5개
    lines.append("## 핵심 인사이트")
    lines.append("")
    insights = []
    # 1. 14개월 총 지출 규모
    insights.append(f"**1. 광고비 규모**: 14개월간 총 **{t['combined_spend']:,}원** 집행 (월평균 약 {t['combined_spend']//15:,}원), 매출 **{t['combined_revenue']:,}원** 발생, 메타 픽셀 기준 ROAS **{t['combined_avg_roas']}**.")
    # 2. 계정 비중
    if t["combined_spend"] > 0:
        il_pct = t["ilbia_spend"] / t["combined_spend"] * 100
        insights.append(f"**2. 계정 편중**: 일비아 계정이 전체의 **{il_pct:.1f}%**를 차지, 세탁제품 계정은 **{100-il_pct:.1f}%**로 비중이 낮음.")
    # 3. 최고 효율 카테고리
    if sorted_cats:
        best_cat = max(sorted_cats, key=lambda x: x[1]["avg_roas"] if x[1]["spend"] > 100000 else 0)
        insights.append(f"**3. 최고 효율 카테고리**: **{best_cat[0]}** (ROAS {best_cat[1]['avg_roas']}, 지출 {best_cat[1]['spend']:,}원)")
        worst_cat = min([c for c in sorted_cats if c[1]["spend"] > 100000], key=lambda x: x[1]["avg_roas"], default=None)
        if worst_cat:
            insights.append(f"**4. 최저 효율 카테고리**: **{worst_cat[0]}** (ROAS {worst_cat[1]['avg_roas']}, 지출 {worst_cat[1]['spend']:,}원)")
    # 5. 월별 추세
    if len(result["monthly"]) >= 2:
        mk = sorted(result["monthly"].keys())
        first_m = result["monthly"][mk[0]]["combined"]
        last_m = result["monthly"][mk[-1]]["combined"]
        insights.append(f"**5. 월별 추세**: {mk[0]} 지출 {first_m['spend']:,}원(ROAS {first_m['roas']}) → {mk[-1]} 지출 {last_m['spend']:,}원(ROAS {last_m['roas']})")

    for ins in insights:
        lines.append(f"- {ins}")
    lines.append("")

    if r["days_missing"]:
        lines.append(f"## 누락 일자 ({len(r['days_missing'])}일)")
        lines.append("")
        lines.append(", ".join(r["days_missing"][:50]) + (" ..." if len(r["days_missing"]) > 50 else ""))
        lines.append("")

    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
