"""네이버 광고(SA + 애드부스트/GFA) → 성락 오빠 구글시트 자동 입력

매일 06:45 크론 실행 (쿠팡 다운로드 06:30 이후):
  - SA(검색광고): 네이버 검색광고 API(HMAC)로 전날 ELIGIBLE 캠페인 stats 합산
      → SA(daily) 탭 전날 행에 입력
  - GFA(애드부스트): browser_cookie3로 크롬 naver 쿠키 추출 → 내부 대시보드 API 호출
      → GFA_PMAX 타입 캠페인만 합산 → GFA(daily) 탭 전날 행에 입력
      → 쿠키 추출 실패/세션 만료 시 로그 남기고 GFA 스킵 (SA는 정상 진행)

⚠️ 보안:
  - SA 자격증명(API_KEY/SECRET/CUSTOMER_ID)은 코드에 하드코딩하지 않고
    기존 MCP 모듈(mcp-server/apps/naver_searchad.py)에서 런타임에 추출해 재사용.
  - GFA는 크롬 로그인 쿠키 사용 (비번 미취급).

시트 열 구조 (A열 날짜·E/F/H/J/K 수식은 보존, 원본값만 입력):
  A=일자(보존) B=지출 C=노출 D=클릭 E=CPC(수식) F=CTR(수식)
  G=전환수 H=CVR(수식) I=전환매출 J=ROAS(수식) K=전환당비용(SA수식)/장바구니(GFA)
  → SA  입력: B, C, D, G, I  (E/F/H/J/K 수식 보존)
  → GFA 입력: B, C, D, G, I  (E/F/H/J 수식, K 장바구니 보존)
"""
import os
import re
import sys
import json
import time
import hmac
import hashlib
import base64
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from urllib.parse import quote

import gspread
from google.oauth2.service_account import Credentials

# ── 설정 ────────────────────────────────────────────────
SHEET_ID = "1_n7vHG1Gf1cOktmMiIG7cpEI2m34f4XeWaTd4dFskB0"
SA_KEY = "/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json"
MCP_NAVER_MODULE = "/Users/macmini_ky/ClaudeAITeam/mcp-server/apps/naver_searchad.py"
LOG_DIR = "/Users/macmini_ky/ClaudeAITeam/automation/logs"

GFA_AD_ACCOUNT_ID = "1982005"
GFA_API = f"https://ads.naver.com/apis/dashboard/v1/adAccounts/{GFA_AD_ACCOUNT_ID}/campaigns/search"

WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]

# ── 로깅 ────────────────────────────────────────────────
_log_lines = []


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line)
    _log_lines.append(line)


def flush_log(date_str):
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"naver_ad_sheet_{date_str}.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(_log_lines) + "\n")


# ── 날짜 라벨 ───────────────────────────────────────────
def make_date_label(dt):
    """datetime → 시트 날짜 라벨 (예: '06 2 화')"""
    return f"{dt.month:02d} {dt.day} {WEEKDAYS_KR[dt.weekday()]}"


def find_date_row(ws, date_label):
    """시트 A열에서 날짜 라벨 행 번호 찾기 (아래에서부터 검색)"""
    all_dates = ws.col_values(1)
    for i in range(len(all_dates) - 1, 0, -1):
        if all_dates[i].strip() == date_label:
            return i + 1
    return 0


# ── SA 자격증명 (MCP 모듈에서 추출, 하드코딩 금지) ──────
def load_sa_credentials():
    """mcp-server/apps/naver_searchad.py 에서 SA 자격증명을 런타임 추출.
    (Python 3.9 가 해당 모듈의 'X | None' 타입힌트를 import 시 파싱 못 하므로
     import 대신 소스에서 상수만 정규식으로 읽어옴)"""
    src = open(MCP_NAVER_MODULE, encoding="utf-8").read()

    def grab(name):
        m = re.search(rf'{name}\s*=\s*"([^"]+)"', src)
        if not m:
            raise RuntimeError(f"{name} 를 MCP 모듈에서 찾지 못함")
        return m.group(1)

    return {
        "base": grab("NAVER_AD_BASE"),
        "customer_id": grab("NAVER_CUSTOMER_ID"),
        "api_key": grab("NAVER_API_KEY"),
        "secret_key": grab("NAVER_SECRET_KEY"),
    }


def _sa_headers(cred, method, path):
    """네이버 검색광고 API 인증 헤더 (HMAC-SHA256)"""
    ts = str(int(time.time() * 1000))
    sign_path = path.split("?")[0]
    sign = f"{ts}.{method}.{sign_path}"
    sig = hmac.new(cred["secret_key"].encode(), sign.encode(), hashlib.sha256).digest()
    return {
        "X-Customer": cred["customer_id"],
        "X-API-KEY": cred["api_key"],
        "X-Timestamp": ts,
        "X-Signature": base64.b64encode(sig).decode(),
        "Content-Type": "application/json",
    }


def _sa_get(cred, path):
    req = urllib.request.Request(cred["base"] + path, headers=_sa_headers(cred, "GET", path))
    return urllib.request.urlopen(req, timeout=30).read().decode()


def collect_sa(date_str):
    """SA(검색광고) 전날 데이터 수집 → 합산 dict 반환
    {spend, impressions, clicks, conversions, conv_value, n_campaigns}"""
    cred = load_sa_credentials()

    camps = json.loads(_sa_get(cred, "/ncc/campaigns"))
    eligible = [c["nccCampaignId"] for c in camps if c.get("status") == "ELIGIBLE"]
    log(f"  SA ELIGIBLE 캠페인 {len(eligible)}개")

    fields = '["impCnt","clkCnt","salesAmt","ccnt","convAmt"]'
    tr = json.dumps({"since": date_str, "until": date_str}, separators=(",", ":"))

    tot = {"impCnt": 0, "clkCnt": 0, "salesAmt": 0, "ccnt": 0, "convAmt": 0}
    for cid in eligible:
        # /stats 는 단일 id(id=) 형태만 허용 (ids= 배열은 11001 오류)
        path = f"/stats?id={quote(cid)}&fields={quote(fields)}&timeRange={quote(tr)}"
        try:
            d = json.loads(_sa_get(cred, path))
        except Exception as e:
            log(f"    ⚠️ SA stats 실패 {cid}: {e}")
            continue
        for row in d.get("data", []):
            for k in tot:
                tot[k] += row.get(k, 0) or 0

    return {
        "spend": int(tot["salesAmt"]),
        "impressions": int(tot["impCnt"]),
        "clicks": int(tot["clkCnt"]),
        "conversions": int(tot["ccnt"]),
        "conv_value": int(tot["convAmt"]),
        "n_campaigns": len(eligible),
    }


# ── GFA (애드부스트) ────────────────────────────────────
def _get_naver_cookies():
    """크롬에서 naver.com 쿠키 추출. 로그인 세션 쿠키 없으면 None."""
    import browser_cookie3
    cj = browser_cookie3.chrome(domain_name="naver.com")
    cookies = {c.name: c.value for c in cj}
    if "NID_AUT" not in cookies or "NID_SES" not in cookies:
        return None
    return cookies


def collect_gfa(date_str):
    """GFA(애드부스트) 전날 데이터 수집 → 합산 dict 또는 None(스킵).
    GFA_PMAX 타입 캠페인만 합산. 금액 Micros÷1e6, 전환매출=purchasedConversionsValue."""
    try:
        cookies = _get_naver_cookies()
    except Exception as e:
        log(f"  ⚠️ GFA 쿠키 추출 실패 → GFA 스킵: {e}")
        return None

    if not cookies:
        log("  ⚠️ GFA 로그인 세션(NID_AUT/NID_SES) 없음 → GFA 스킵")
        return None

    cookie_hdr = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = {
        "Content-Type": "application/json",
        "Cookie": cookie_hdr,
        "Referer": "https://ads.naver.com/",
        "Origin": "https://ads.naver.com",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    if cookies.get("XSRF-TOKEN"):
        headers["X-XSRF-TOKEN"] = cookies["XSRF-TOKEN"]

    body = json.dumps({"startDate": date_str, "endDate": date_str}).encode()
    req = urllib.request.Request(GFA_API, data=body, headers=headers, method="POST")
    try:
        raw = urllib.request.urlopen(req, timeout=40).read().decode()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:200]
        except Exception:
            pass
        if e.code in (401, 403):
            log(f"  ⚠️ GFA 세션 만료(HTTP {e.code}) → GFA 스킵: {detail}")
        else:
            log(f"  ⚠️ GFA API 오류(HTTP {e.code}) → GFA 스킵: {detail}")
        return None
    except Exception as e:
        log(f"  ⚠️ GFA API 호출 실패 → GFA 스킵: {e}")
        return None

    data = json.loads(raw)
    results = data.get("results", [])

    pmax = [r for r in results if r.get("campaign", {}).get("type") == "GFA_PMAX"]
    log(f"  GFA 전체 캠페인 {len(results)}개 중 GFA_PMAX {len(pmax)}개 합산")

    spend = imp = clk = conv = conv_value = 0
    for r in pmax:
        m = r.get("metrics", {})
        spend += (m.get("grossCostMicros", 0) or 0)
        imp += int(m.get("impressions", 0) or 0)
        clk += int(m.get("clicks", 0) or 0)
        conv += int(m.get("conversions", 0) or 0)
        conv_value += (m.get("purchasedConversionsValueMicros", 0) or 0)

    return {
        "spend": round(spend / 1e6),
        "impressions": imp,
        "clicks": clk,
        "conversions": conv,
        "conv_value": round(conv_value / 1e6),  # 실구매 매출
        "n_campaigns": len(pmax),
    }


# ── 시트 입력 ───────────────────────────────────────────
def write_to_sheet(sh, tab, date_label, vals):
    """전날 행에 B/C/D/G/I 원본값만 입력 (E/F/H/J/K 수식 보존)"""
    ws = sh.worksheet(tab)
    row = find_date_row(ws, date_label)
    if not row:
        log(f"  ⚠️ {tab} 에서 '{date_label}' 행을 찾지 못함 → 입력 스킵")
        return False

    updates = [
        {"range": f"B{row}", "values": [[vals["spend"]]]},
        {"range": f"C{row}", "values": [[vals["impressions"]]]},
        {"range": f"D{row}", "values": [[vals["clicks"]]]},
        {"range": f"G{row}", "values": [[vals["conversions"]]]},
        {"range": f"I{row}", "values": [[vals["conv_value"]]]},
    ]
    ws.batch_update(updates, value_input_option="RAW")
    log(
        f"  ✅ {tab} [{row}행] 지출=₩{vals['spend']:,} 노출={vals['impressions']:,} "
        f"클릭={vals['clicks']} 전환={vals['conversions']} 매출=₩{vals['conv_value']:,}"
    )
    return True


# ── 메인 ────────────────────────────────────────────────
def run(target_date=None):
    if target_date:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        dt = datetime.now() - timedelta(days=1)

    date_str = dt.strftime("%Y-%m-%d")
    date_label = make_date_label(dt)

    log("=== 네이버 광고(SA+GFA) → 구글시트 ===")
    log(f"  대상 날짜: {date_str} ({date_label})")

    # 구글시트 연결
    creds = Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    # 1) SA (API키 방식 - 실패해도 GFA 진행은 별개)
    log("[1/2] SA(검색광고) 수집...")
    try:
        sa = collect_sa(date_str)
        log(
            f"  SA 합계: 지출=₩{sa['spend']:,} 노출={sa['impressions']:,} "
            f"클릭={sa['clicks']} 전환={sa['conversions']} 매출=₩{sa['conv_value']:,}"
        )
        write_to_sheet(sh, "SA(daily)", date_label, sa)
    except Exception as e:
        log(f"  ❌ SA 처리 실패: {e}")

    # 2) GFA (쿠키 방식 - 실패 시 스킵)
    log("[2/2] GFA(애드부스트) 수집...")
    gfa = collect_gfa(date_str)
    if gfa is None:
        log("  ⏭️ GFA 스킵됨 (위 사유 참조)")
    else:
        log(
            f"  GFA 합계: 지출=₩{gfa['spend']:,} 노출={gfa['impressions']:,} "
            f"클릭={gfa['clicks']} 전환={gfa['conversions']} 실구매매출=₩{gfa['conv_value']:,}"
        )
        write_to_sheet(sh, "GFA(daily)", date_label, gfa)

    log("완료 ✅")
    flush_log(datetime.now().strftime("%Y-%m-%d"))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run(target)
