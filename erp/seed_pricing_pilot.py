"""채널별 가격관리 파일럿 — 기준판매가 시트(gid 2120879076) 이식.
테이블 생성 + 자사몰/쿠팡/스마트스토어 3채널 + 53개 SKU 시드."""
import sqlite3, os, re

DB = os.path.join(os.path.dirname(__file__), "erp.db")


def group_of(name):
    """품목명에서 구성(N개)을 떼어 품목군 이름을 만든다."""
    b = re.sub(r'\s*\d+\s*개입?(\([^)]*\))?\s*$', '', name).strip()
    b = re.sub(r'[x×]\s*$', '', b).strip()
    return b or name

# (name, pack, cost, consumer, 자사몰, 쿠팡, 스마트스토어, code)
ITEMS = [
    ("캡슐세제 1개", 1, 3448, 24900, 14900, 12050, 15900, "IB-00601"),
    ("캡슐세제 2개", 2, 6896, 49800, 28900, 24100, 28900, "IB-00601_2"),
    ("캡슐세제 3개", 3, 10344, 74700, 41100, 35420, 41100, "IB-00601_3"),
    ("캡슐세제 4개", 4, 13792, 99600, 50200, 47220, 50200, "IB-00601_4"),
    ("캡슐표백제 1개", 1, 2769, 18900, 11900, 10620, 11900, None),
    ("캡슐표백제 2개", 2, 5538, 37800, 23200, 21230, 25800, None),
    ("캡슐표백제 3개", 3, 8307, 56700, 33600, 28280, None, None),
    ("캡슐표백제 4개", 4, 11076, 75600, 42600, 37700, 45800, None),
    ("하트 식세기세제 1개", 1, 3146, 19800, 13900, 12940, 14900, "IB-00101H"),
    ("하트 식세기세제 2개", 2, 6292, 39600, 26500, 25880, 27500, "IB-00101H_2"),
    ("하트 식세기세제 3개", 3, 9437, 59400, 37500, 35630, None, "IB-00101H_3"),
    ("하트 식세기세제 4개", 4, 12584, None, None, 43500, 46900, None),
    ("하트 식세기세제 패키지", 1, 12547, 76800, 42900, 41190, 43900, "IB-00101HS"),
    ("하트 식세기세제 3개(틴케이스+집게)", 3, 9437, 73400, 39900, None, 40900, "IB-00101H_3C"),
    ("건조기시트 1개", 1, 3932, 18900, 13900, 12970, 14900, "IB-00301"),
    ("건조기시트 2개", 2, 7865, 37800, 26800, 23360, 29900, "IB-00301_2"),
    ("건조기시트 3개", 3, 11797, 56700, 38100, 34290, None, "IB-00301_3"),
    ("건조기시트 4개", 4, 15728, None, None, None, 53900, None),
    ("건조기시트 1개_바이올렛머스크 40매", 1, 3932, 18900, 13900, None, None, "IB-00301v"),
    ("건조기시트 1개_바이올렛머스크 42매", 1, 4632, 20900, 14600, None, 15600, "IB-00301v42"),
    ("건조기시트 바이올렛머스크 42매 2개", 2, 9264, 41800, 27800, None, 28800, "IB-00301v42_2"),
    ("건조기시트 바이올렛머스크 42매 3개", 3, 13896, 62700, 38900, None, 39900, "IB-00301v42_3"),
    ("원형 식세기세제 1개", 1, 3304, 18900, 13500, 13500, 14500, "IB-00101"),
    ("원형 식세기세제 2개", 2, 6608, 37800, 26000, 27000, 31900, "IB-00101_2"),
    ("원형 식세기세제 3개", 3, 9912, 56700, 37200, 36110, None, "IB-00101_3"),
    ("원형 식세기세제 4개", 4, 13216, None, None, None, 42900, None),
    ("원형 식세기세제 6개", 6, 19825, 113400, 70800, 55180, 71800, "IB-00101_6"),
    ("얼룩제거제 350ml x 1개", 1, 3012, 18900, 12900, 11510, 13900, "IB-00701_350ml"),
    ("얼룩제거제 350ml x 2개", 2, 6024, 37800, 22800, 23020, 25900, "IB-00701_350ml_2"),
    ("얼룩제거제 350ml x 3개", 3, 9036, 56700, 18800, 34530, None, "IB-00701_350ml_3"),
    ("얼룩제거제 100ml 1개", 1, 1712, 15500, 9900, 8750, 10900, "IB-00701_100ml"),
    ("얼룩제거제 100ml 2개", 2, 3424, 31000, 17800, 17500, 21900, "IB-00701_100ml_2"),
    ("얼룩제거제 100ml 3개", 3, 5136, 93000, 17800, 26250, None, "IB-00701_100ml_3"),
    ("얼룩제거제 100ml + 350ml", 1, 4724, 34400, 21800, 35000, 22800, "IB-00701_combo"),
    ("스타일링 섬유탈취제 400ml 1개", 1, 2737, 18900, 12900, 11510, 13900, "IB-00801"),
    ("스타일링 섬유탈취제 400ml 2개", 2, 5474, 37800, 24400, 23020, 26800, "IB-00801_2"),
    ("스타일링 섬유탈취제 400ml 3개", 3, 8211, 56700, 34200, 34530, None, "IB-00801_3"),
    ("스타일링 섬유탈취제 100ml 1개", 1, 1557, 16900, 9900, 9840, 10900, "IB-00802"),
    ("스타일링 섬유탈취제 100ml 2개", 2, 3114, 33800, 18400, 19180, 21800, "IB-00802_2"),
    ("스타일링 섬유탈취제 100ml 3개", 3, 4671, 50700, 25200, 28020, 28900, "IB-00802_3"),
    ("올인원 수세미 1개", 1, 1519, 12000, 8900, None, 9900, "IB-00501"),
    ("올인원 수세미 2개", 2, 3039, 24000, 16200, None, 17200, "IB-00501_2"),
    ("올인원 수세미 3개", 3, 4558, 36000, 22500, None, 23500, "IB-00501_3"),
    ("올인원 수세미 4개", 4, 6078, 48000, 27600, None, 28600, "IB-00501_4"),
    ("올인원 수세미 6개", 6, 7597, 60000, 30000, None, 31000, "IB-00501_6"),
    ("다목적 세정제 1개", 1, 2739, 16900, 7900, None, 8900, "IB-00201"),
    ("다목적 세정제 2개(1+1)", 2, 5478, 33800, 13800, None, 14800, "IB-00201_2"),
    ("다목적 세정제 3개(2+1)", 3, 8218, 50700, 17700, None, 18700, "IB-00201_3"),
    ("다목적 세정제 4개(2+2)", 4, 10956, 67600, 23600, None, 24600, "IB-00201_4"),
    ("하트 집게", 1, 493, 4000, 3000, None, 3000, "하트집게"),
    ("하트 틴케이스", 1, 1339, 10000, 6000, None, 8000, "하트틴케이스"),
    ("세제 보관함", 1, 1473, 6000, 5000, None, 5000, "세제보관함"),
    ("하트 식세기세제 6정 샘플", 1, 736, 2000, 900, None, 900, "IB-00101Hs"),
]

CHANNELS = [
    # name, commission_rate, vat_rate, sort
    ("자사몰", 0.06, 0.10, 1),
    ("쿠팡", 0.06, 0.10, 2),
    ("스마트스토어", 0.06, 0.10, 3),
]

conn = sqlite3.connect(DB)
c = conn.cursor()

c.executescript("""
DROP TABLE IF EXISTS price_cells;
DROP TABLE IF EXISTS price_items;
CREATE TABLE IF NOT EXISTS price_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    commission_rate REAL NOT NULL DEFAULT 0,
    vat_rate REAL NOT NULL DEFAULT 0.1,
    sort_order INTEGER DEFAULT 0
);
CREATE TABLE price_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    name TEXT NOT NULL,
    group_name TEXT,
    pack INTEGER DEFAULT 1,
    cost INTEGER,
    consumer INTEGER,
    sort_order INTEGER DEFAULT 0
);
CREATE TABLE price_cells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    sale_price INTEGER,
    UNIQUE(item_id, channel_id),
    FOREIGN KEY(item_id) REFERENCES price_items(id) ON DELETE CASCADE,
    FOREIGN KEY(channel_id) REFERENCES price_channels(id)
);
""")

c.execute("DELETE FROM price_channels")

ch_ids = {}
for name, comm, vat, sort in CHANNELS:
    c.execute("INSERT INTO price_channels (name, commission_rate, vat_rate, sort_order) VALUES (?,?,?,?)",
              (name, comm, vat, sort))
    ch_ids[name] = c.lastrowid

for i, (name, pack, cost, consumer, ja, cp, ss, code) in enumerate(ITEMS):
    c.execute("INSERT INTO price_items (code, name, group_name, pack, cost, consumer, sort_order) VALUES (?,?,?,?,?,?,?)",
              (code, name, group_of(name), pack, cost, consumer, i))
    item_id = c.lastrowid
    for chname, price in (("자사몰", ja), ("쿠팡", cp), ("스마트스토어", ss)):
        c.execute("INSERT INTO price_cells (item_id, channel_id, sale_price) VALUES (?,?,?)",
                  (item_id, ch_ids[chname], price))

conn.commit()
print("채널:", [r for r in c.execute("SELECT name, commission_rate FROM price_channels")])
print("품목 수:", c.execute("SELECT COUNT(*) FROM price_items").fetchone()[0])
print("셀 수:", c.execute("SELECT COUNT(*) FROM price_cells").fetchone()[0])
conn.close()
print("시드 완료 ✅")
