"""
네이버 검색광고(SA) 일별 수집기
목적: 파워링크·쇼핑검색 키워드/그룹 단위 성과를 매일 SQLite(naver_sa.db)에 저장
담당: 비코어랩 AI팀 모리 (2026-07-08 구현 / 2026-07-08 전환지표 버그수정)

⚠️ API 중요 함정:
  - /stats 호출 시 반드시 ids= (복수형) 사용.
    id= (단수형)은 부분집계 버그값 반환 (검증됨 — 절대 id= 쓰지 말 것).
  - 배치 크기 20으로 시작. 11001 등 오류 시 반으로 줄여 재시도.
  - 쇼핑검색 그룹은 키워드가 없으므로 그룹 자체를 shopping_group 엔티티로 수집.
  - /stats의 convAmt는 purchase+add_to_cart 합산(뻥튀기). 절대 전환지표에 쓰지 말 것!
    전환수/전환매출/ROAS는 반드시 AD_CONVERSION_DETAIL의 purchase 행만 사용.

다음 개발자 안내:
  - 인증 모듈: automation/naver_ad_to_sheet.py (load_sa_credentials, _sa_get 재사용)
  - DB 경로: /Users/macmini_ky/ClaudeAITeam/advertising/naver_sa.db
  - 크론: ~/Library/LaunchAgents/com.becorelab.naver-sa-collect.plist (매일 07:10)
  - 실행: python3 naver_sa_collect.py             ← 어제 하루
           python3 naver_sa_collect.py --backfill 30  ← 과거 30일
           python3 naver_sa_collect.py --date YYYY-MM-DD  ← 단일 날짜 재수집
  - 전환지표 수집 흐름:
      1) POST /stat-reports {"reportTp":"AD_CONVERSION_DETAIL","statDt":"...T00:00:00.000Z"}
      2) GET /stat-reports/{jobId} 폴링(3초/45회) → BUILT → downloadUrl
      3) GET downloadUrl(base 제거한 경로만) → TSV(헤더없음, 탭구분, 15컬럼)
      4) [12]=='purchase' 행만 집계: entity=[4]!='-'?[4]:[3], ccnt=[13], conv_amt=[14]
"""

import sys
import json
import time
import sqlite3
import argparse
import warnings
from datetime import datetime, timedelta
from urllib.parse import quote

# FutureWarning 무시 (naver_ad_to_sheet가 gspread 등 임포트)
warnings.filterwarnings("ignore", category=FutureWarning)

# 인증 모듈 재사용 (새로 구현 금지)
sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/automation")
import naver_ad_to_sheet as n

# ── 설정 ──────────────────────────────────────────────────────────
DB_PATH = "/Users/macmini_ky/ClaudeAITeam/advertising/naver_sa.db"
BATCH_SIZE = 20          # ids= 배치 초기 크기
CALL_INTERVAL = 0.25     # 호출 간격(초)
RETRY_COUNT = 2          # HTTP 오류 재시도 횟수
RETRY_SLEEP = 2.0        # 재시도 대기(초)

# stats 수집 fields (광고비·노출·클릭·CPC·CTR만 — 전환은 AD_CONVERSION_DETAIL로 별도 수집)
STAT_FIELDS = '["impCnt","clkCnt","salesAmt","cpc","ctr"]'


# ── 로깅 ──────────────────────────────────────────────────────────
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── DB 초기화 ──────────────────────────────────────────────────────
def init_db(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS entities (
      id TEXT PRIMARY KEY,
      kind TEXT NOT NULL,
      name TEXT NOT NULL,
      ad_type TEXT NOT NULL,
      campaign_id TEXT, campaign_name TEXT,
      adgroup_id TEXT, adgroup_name TEXT,
      bid INTEGER, qi INTEGER,
      status TEXT, updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS daily_stats (
      entity_id TEXT NOT NULL,
      stat_date TEXT NOT NULL,
      imp INTEGER DEFAULT 0,
      clk INTEGER DEFAULT 0,
      cpc INTEGER DEFAULT 0,
      cost INTEGER DEFAULT 0,
      ccnt INTEGER DEFAULT 0,
      conv_amt INTEGER DEFAULT 0,
      ctr REAL DEFAULT 0,
      roas REAL DEFAULT 0,
      UNIQUE(entity_id, stat_date)
    );

    CREATE INDEX IF NOT EXISTS idx_ds_date ON daily_stats(stat_date);
    """)
    conn.commit()


# ── API 호출 (재시도 포함) ─────────────────────────────────────────
def sa_get(cred, path):
    """_sa_get 래퍼: HTTP 오류 시 RETRY_COUNT 회 재시도, 실패 시 None 반환"""
    for attempt in range(RETRY_COUNT + 1):
        try:
            return n._sa_get(cred, path)
        except Exception as e:
            if attempt < RETRY_COUNT:
                log(f"  ⚠️ GET {path[:60]} 실패({e}), {RETRY_SLEEP}s 후 재시도 ({attempt+1}/{RETRY_COUNT})")
                time.sleep(RETRY_SLEEP)
            else:
                log(f"  ✗ GET {path[:80]} 최종 실패: {e}")
                return None


def sa_post(cred, path, body_dict):
    """SA API POST 요청 (JSON body), 실패 시 예외 그대로 전파"""
    import urllib.request as _ur
    body = json.dumps(body_dict).encode()
    req = _ur.Request(
        cred["base"] + path,
        data=body,
        headers=n._sa_headers(cred, "POST", path),
        method="POST",
    )
    return _ur.urlopen(req, timeout=30).read().decode()


# ── AD_CONVERSION_DETAIL: purchase 전환만 집계 ─────────────────────
def fetch_purchase_conversion(cred, date_str):
    """StatReport AD_CONVERSION_DETAIL → purchase 행만 집계.

    반환: {entity_id: {"ccnt": int, "conv_amt": int}}
    실패(생성 오류, BUILT 타임아웃, ERROR status) 시 {} 반환 → 전환 0 처리.
    엔티티 매핑:
      keywordId(r[4]) != '-'  → entity_id = keywordId   (파워링크 키워드)
      keywordId(r[4]) == '-'  → entity_id = adgroupId   (쇼핑 그룹)
    """
    stat_dt = f"{date_str}T00:00:00.000Z"

    # 1) 리포트 생성
    try:
        resp = sa_post(cred, "/stat-reports", {
            "reportTp": "AD_CONVERSION_DETAIL",
            "statDt": stat_dt,
        })
    except Exception as e:
        log(f"  ✗ AD_CONVERSION_DETAIL 생성 실패({date_str}): {e} → 전환 스킵")
        return {}

    job_data = json.loads(resp)
    job_id = job_data.get("reportJobId")
    if not job_id:
        log(f"  ✗ AD_CONVERSION_DETAIL jobId 없음({date_str}) resp={resp[:120]} → 전환 스킵")
        return {}

    log(f"  AD_CONVERSION_DETAIL 생성 완료: jobId={job_id}")

    # 2) 폴링 (3초 간격, 최대 45회=135초 — 리포트 빌드 지연 대비)
    download_url = None
    for attempt in range(45):
        time.sleep(3)
        try:
            poll_raw = sa_get(cred, f"/stat-reports/{job_id}")
            if poll_raw is None:
                log(f"  ⚠️ 폴링 응답 없음({attempt+1}/45), 재시도")
                continue
            poll_data = json.loads(poll_raw)
            status = poll_data.get("status")
            if status == "BUILT":
                download_url = poll_data.get("downloadUrl", "")
                log(f"  리포트 BUILT (시도 {attempt+1}/20)")
                break
            elif status == "ERROR":
                log(f"  ✗ 리포트 ERROR({date_str}) → 전환 스킵(0 처리)")
                return {}
            else:
                log(f"  리포트 폴링 {attempt+1}/20: status={status}")
        except Exception as e:
            log(f"  ⚠️ 폴링 오류({attempt+1}): {e}")

    if not download_url:
        log(f"  ✗ 리포트 BUILT 실패 (45회 초과 또는 URL 없음) ({date_str}) → 전환 스킵")
        return {}

    # 3) TSV 다운로드 (downloadUrl에서 base 제거 → 경로만 sa_get)
    dl_path = download_url.replace(cred["base"], "")
    try:
        tsv_raw = sa_get(cred, dl_path)
    except Exception as e:
        log(f"  ✗ TSV 다운로드 실패: {e} → 전환 스킵")
        return {}

    if not tsv_raw or not tsv_raw.strip():
        log(f"  ℹ️ TSV 비어있음({date_str}) → purchase 전환 없음")
        return {}

    # 4) TSV 파싱 — purchase 행만 집계
    lines = tsv_raw.strip().split("\n")
    conv_map = {}
    purchase_sample_count = 0
    skipped_col = 0

    for line in lines:
        if not line.strip():
            continue
        cols = line.split("\t")

        # 컬럼수 검증 (15개 미만이면 인덱스 오류 위험)
        if len(cols) < 15:
            skipped_col += 1
            if skipped_col <= 3:
                log(f"  ⚠️ 컬럼수 부족({len(cols)}개 < 15) — 행 스킵: {line[:80]}")
            continue

        conversion_type = cols[12]
        if conversion_type != "purchase":
            continue  # add_to_cart 등 완전 무시

        # 처음 3개 purchase 행 육안 확인용 출력
        if purchase_sample_count < 3:
            log(
                f"  [SAMPLE purchase #{purchase_sample_count+1}] "
                f"날짜={cols[0]} adgroupId={cols[3]} keywordId={cols[4]} "
                f"type={cols[12]} ccnt={cols[13]} conv_amt={cols[14]}"
            )
            purchase_sample_count += 1

        # 엔티티 매핑
        keyword_id = cols[4]
        adgroup_id = cols[3]
        entity_id = keyword_id if keyword_id != "-" else adgroup_id

        try:
            ccnt = int(cols[13])
            conv_amt_val = int(cols[14])
        except (ValueError, IndexError) as e:
            log(f"  ⚠️ 숫자 파싱 실패(entity={entity_id}): ccnt={cols[13]} conv_amt={cols[14]} err={e}")
            continue

        if entity_id not in conv_map:
            conv_map[entity_id] = {"ccnt": 0, "conv_amt": 0}
        conv_map[entity_id]["ccnt"] += ccnt
        conv_map[entity_id]["conv_amt"] += conv_amt_val

    total_ccnt = sum(v["ccnt"] for v in conv_map.values())
    total_conv_amt = sum(v["conv_amt"] for v in conv_map.values())
    if purchase_sample_count == 0:
        log(f"  ℹ️ {date_str} purchase 행 없음 (전환 0건)")
    else:
        log(
            f"  purchase 집계 완료({date_str}): {len(conv_map)}개 엔티티 / "
            f"전환수 합계={total_ccnt} / 전환매출 합계={total_conv_amt:,}"
        )
    return conv_map


def update_conversion_stats(conn, conv_map, date_str):
    """purchase 전환 집계 → daily_stats.ccnt/conv_amt/roas UPDATE.

    1) 해당 날짜 전체 ccnt/conv_amt/roas 0으로 초기화 (전환 없는 엔티티 보장)
    2) conv_map 엔티티만 실값으로 UPDATE (roas = conv_amt/cost*100)
    """
    # 전체 초기화
    conn.execute(
        "UPDATE daily_stats SET ccnt=0, conv_amt=0, roas=0 WHERE stat_date=?",
        (date_str,),
    )

    if not conv_map:
        conn.commit()
        log(f"  [{date_str}] 전환 UPDATE 완료: purchase 전환 없음 (전체 0)")
        return

    # cost 조회 (roas 계산용)
    cost_rows = conn.execute(
        "SELECT entity_id, cost FROM daily_stats WHERE stat_date=?",
        (date_str,),
    ).fetchall()
    cost_map = {r[0]: r[1] for r in cost_rows}

    updated = 0
    for entity_id, cv in conv_map.items():
        cost = cost_map.get(entity_id, 0)
        roas = round(cv["conv_amt"] / cost * 100, 1) if cost > 0 else 0
        conn.execute(
            """UPDATE daily_stats
               SET ccnt=?, conv_amt=?, roas=?
               WHERE entity_id=? AND stat_date=?""",
            (cv["ccnt"], cv["conv_amt"], roas, entity_id, date_str),
        )
        updated += 1

    conn.commit()
    log(f"  [{date_str}] 전환 UPDATE 완료: {updated}개 엔티티 ccnt/conv_amt/roas 갱신")


# ── 엔티티 디스커버리 ─────────────────────────────────────────────
def discover_entities(cred):
    """ELIGIBLE 캠페인 → 그룹 → 키워드 순으로 전체 엔티티 목록 수집.
    반환: list of dict (entity row 형태)"""

    # 1. 캠페인 목록
    raw = sa_get(cred, "/ncc/campaigns")
    if not raw:
        raise RuntimeError("캠페인 목록 조회 실패")
    campaigns = json.loads(raw)
    eligible_camps = [c for c in campaigns if c.get("status") == "ELIGIBLE"]
    log(f"캠페인: 전체 {len(campaigns)}개 / ELIGIBLE {len(eligible_camps)}개")

    entities = []

    for camp in eligible_camps:
        cid = camp["nccCampaignId"]
        cname = camp.get("name", cid)
        ctype = camp.get("campaignTp", "")
        ad_type = "쇼핑검색" if ctype == "SHOPPING" else "파워링크"

        # 2. 광고그룹 목록
        time.sleep(CALL_INTERVAL)
        raw2 = sa_get(cred, f"/ncc/adgroups?nccCampaignId={quote(cid)}")
        if not raw2:
            log(f"  ⚠️ {cname} 그룹 조회 실패 — 스킵")
            continue
        adgroups = json.loads(raw2)
        eligible_grps = [g for g in adgroups if g.get("status") == "ELIGIBLE"]
        log(f"  [{ad_type}] {cname}: 그룹 {len(adgroups)}개 / ELIGIBLE {len(eligible_grps)}개")

        for grp in eligible_grps:
            gid = grp["nccAdgroupId"]
            gname = grp.get("name", gid)

            if ad_type == "쇼핑검색":
                # 쇼핑은 키워드 없음 — 그룹 자체가 수집 단위
                entities.append({
                    "id": gid,
                    "kind": "shopping_group",
                    "name": gname,
                    "ad_type": ad_type,
                    "campaign_id": cid,
                    "campaign_name": cname,
                    "adgroup_id": gid,
                    "adgroup_name": gname,
                    "bid": grp.get("bidAmt"),
                    "qi": None,
                    "status": grp.get("status"),
                })
            else:
                # 파워링크: 키워드 목록 수집
                time.sleep(CALL_INTERVAL)
                raw3 = sa_get(cred, f"/ncc/keywords?nccAdgroupId={quote(gid)}")
                if not raw3:
                    log(f"    ⚠️ {gname} 키워드 조회 실패 — 스킵")
                    continue
                keywords = json.loads(raw3)
                active_kws = [k for k in keywords if k.get("status") == "ELIGIBLE"]

                for kw in active_kws:
                    kid = kw["nccKeywordId"]
                    qi_obj = kw.get("nccQi") or {}
                    entities.append({
                        "id": kid,
                        "kind": "keyword",
                        "name": kw.get("keyword", kid),
                        "ad_type": ad_type,
                        "campaign_id": cid,
                        "campaign_name": cname,
                        "adgroup_id": gid,
                        "adgroup_name": gname,
                        "bid": kw.get("bidAmt"),
                        "qi": qi_obj.get("qiGrade"),
                        "status": kw.get("status"),
                    })

    log(f"엔티티 디스커버리 완료: 총 {len(entities)}개 (파워링크 키워드 + 쇼핑 그룹)")
    return entities


# ── entities upsert ───────────────────────────────────────────────
def upsert_entities(conn, entities):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [{**e, "updated_at": now} for e in entities]
    conn.executemany("""
        INSERT INTO entities
          (id, kind, name, ad_type, campaign_id, campaign_name,
           adgroup_id, adgroup_name, bid, qi, status, updated_at)
        VALUES
          (:id, :kind, :name, :ad_type, :campaign_id, :campaign_name,
           :adgroup_id, :adgroup_name, :bid, :qi, :status, :updated_at)
        ON CONFLICT(id) DO UPDATE SET
          kind=excluded.kind, name=excluded.name, ad_type=excluded.ad_type,
          campaign_id=excluded.campaign_id, campaign_name=excluded.campaign_name,
          adgroup_id=excluded.adgroup_id, adgroup_name=excluded.adgroup_name,
          bid=excluded.bid, qi=excluded.qi, status=excluded.status,
          updated_at=excluded.updated_at
    """, rows)
    conn.commit()
    log(f"entities upsert 완료: {len(entities)}개")


# ── 배치 stats 수집 ───────────────────────────────────────────────
def fetch_stats_batch(cred, ids, date_str, batch_size=None):
    """ids 리스트의 당일 실적을 배치로 수집. {id: row_dict} 반환.
    오류(11001 등) 시 배치를 반으로 줄여 재시도."""
    if batch_size is None:
        batch_size = BATCH_SIZE

    result = {}
    fields_enc = quote(STAT_FIELDS)
    tr_enc = quote(json.dumps({"since": date_str, "until": date_str}, separators=(",", ":")))

    def fetch_chunk(chunk):
        ids_param = quote(",".join(chunk))
        path = f"/stats?ids={ids_param}&fields={fields_enc}&timeRange={tr_enc}"
        raw = sa_get(cred, path)
        if raw is None:
            return None
        return json.loads(raw)

    # 배치 분할 수집
    i = 0
    while i < len(ids):
        chunk = ids[i:i + batch_size]
        time.sleep(CALL_INTERVAL)
        data = fetch_chunk(chunk)

        if data is None:
            # 배치 크기 반으로 줄여 재시도
            if batch_size > 1:
                smaller = max(1, batch_size // 2)
                log(f"  ⚠️ 배치 오류 — 크기 {batch_size}→{smaller}으로 줄여 재시도")
                sub_result = fetch_stats_batch(cred, chunk, date_str, batch_size=smaller)
                result.update(sub_result)
            else:
                log(f"  ✗ 단일 id 조회 실패, 스킵: {chunk[0][:30]}")
            i += len(chunk)
            continue

        for row in data.get("data", []):
            eid = row.get("id")
            if eid:
                result[eid] = row

        i += len(chunk)

    return result


# ── daily_stats upsert (광고비·노출·클릭·CPC·CTR만) ──────────────
def upsert_daily_stats(conn, entity_ids, stats_map, date_str):
    """모든 entity_ids에 대해 daily_stats upsert. 실적 없으면 0 행 저장.
    ⚠️ ccnt/conv_amt/roas는 여기서 저장하지 않음 — update_conversion_stats에서 처리.
       /stats의 convAmt는 purchase+add_to_cart 합산이라 절대 쓰면 안 됨."""
    rows = []
    for eid in entity_ids:
        row = stats_map.get(eid, {})
        rows.append({
            "entity_id": eid,
            "stat_date": date_str,
            "imp": int(row.get("impCnt", 0) or 0),
            "clk": int(row.get("clkCnt", 0) or 0),
            "cpc": int(row.get("cpc", 0) or 0),
            "cost": int(row.get("salesAmt", 0) or 0),
            "ctr": float(row.get("ctr", 0) or 0),
        })

    conn.executemany("""
        INSERT INTO daily_stats
          (entity_id, stat_date, imp, clk, cpc, cost, ctr)
        VALUES
          (:entity_id, :stat_date, :imp, :clk, :cpc, :cost, :ctr)
        ON CONFLICT(entity_id, stat_date) DO UPDATE SET
          imp=excluded.imp, clk=excluded.clk, cpc=excluded.cpc,
          cost=excluded.cost, ctr=excluded.ctr
    """, rows)
    conn.commit()

    with_perf = sum(1 for r in rows if r["imp"] > 0 or r["clk"] > 0 or r["cost"] > 0)
    log(f"  [{date_str}] daily_stats upsert: 실적있는 엔티티 {with_perf}/{len(rows)}")


# ── 단일 날짜 수집 ────────────────────────────────────────────────
def collect_date(cred, conn, entities, date_str):
    """엔티티 타입별(nkw vs grp)로 분리해 배치 수집. 같은 배치에 섞이면 400 오류.
    stats(광고비/노출/클릭) → upsert → AD_CONVERSION_DETAIL(purchase만) → UPDATE."""
    # 키워드(nkw-)와 쇼핑그룹(grp-)을 분리
    kw_ids = [e["id"] for e in entities if e["kind"] == "keyword"]
    shop_ids = [e["id"] for e in entities if e["kind"] == "shopping_group"]
    all_ids = [e["id"] for e in entities]

    log(f"=== {date_str} 실적 수집 시작 (키워드 {len(kw_ids)}개 / 쇼핑그룹 {len(shop_ids)}개) ===")

    stats_map = {}
    if kw_ids:
        stats_map.update(fetch_stats_batch(cred, kw_ids, date_str))
    if shop_ids:
        stats_map.update(fetch_stats_batch(cred, shop_ids, date_str))

    upsert_daily_stats(conn, all_ids, stats_map, date_str)

    # AD_CONVERSION_DETAIL: purchase만 집계해 ccnt/conv_amt/roas UPDATE
    log(f"  [{date_str}] AD_CONVERSION_DETAIL 수집 시작 (purchase only)...")
    conv_map = fetch_purchase_conversion(cred, date_str)
    update_conversion_stats(conn, conv_map, date_str)


# ── 메인 ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="네이버 SA 일별 수집기")
    parser.add_argument("--backfill", type=int, metavar="N",
                        help="오늘-1부터 N일 전까지 수집 (엔티티 디스커버리 1회)")
    parser.add_argument("--date", type=str, metavar="YYYY-MM-DD",
                        help="단일 날짜 재수집")
    args = parser.parse_args()

    today = datetime.now().date()

    # 수집 날짜 목록 결정
    if args.date:
        dates = [args.date]
    elif args.backfill:
        n_days = args.backfill
        dates = [
            (today - timedelta(days=d)).strftime("%Y-%m-%d")
            for d in range(1, n_days + 1)
        ]
    else:
        # 기본: 어제 하루
        yesterday = today - timedelta(days=1)
        dates = [yesterday.strftime("%Y-%m-%d")]

    log(f"수집 날짜: {dates[0]} ~ {dates[-1]} ({len(dates)}일)")

    # DB 연결 + 초기화
    import os
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    # 자격증명 로드
    cred = n.load_sa_credentials()
    log(f"SA 자격증명 로드 완료 (customer: {cred['customer_id']})")

    # 엔티티 디스커버리 (1회)
    log("=== 엔티티 디스커버리 시작 ===")
    entities = discover_entities(cred)
    upsert_entities(conn, entities)

    # 날짜별 실적 수집
    for date_str in dates:
        collect_date(cred, conn, entities, date_str)

    # DB 요약
    cur = conn.cursor()
    e_count = cur.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    d_count = cur.execute("SELECT COUNT(DISTINCT stat_date) FROM daily_stats").fetchone()[0]
    p_count = cur.execute(
        "SELECT COUNT(*) FROM daily_stats WHERE imp>0 OR clk>0 OR cost>0"
    ).fetchone()[0]
    t_count = cur.execute("SELECT COUNT(*) FROM daily_stats").fetchone()[0]

    log("=" * 50)
    log(f"DB 요약: 엔티티 {e_count}개 / 수집 날짜 {d_count}일 / "
        f"실적>0 행 {p_count}/{t_count}")
    log("수집 완료!")

    conn.close()


if __name__ == "__main__":
    main()
