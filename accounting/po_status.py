# -*- coding: utf-8 -*-
"""ERP 발주 현황 터미널 조회 (정산 하치 SCM 도구, 2026-07-07)
사용: python3 po_status.py [키워드] [--all]
  기본 = 진행 중(미입고) 발주만 납기순. 키워드로 품목 필터. --all이면 완료 포함 최근 30건."""
import sqlite3, sys, re, datetime

DB = "/Users/macmini_ky/ClaudeAITeam/erp/erp.db"
kw = next((a for a in sys.argv[1:] if not a.startswith("--")), "")
show_all = "--all" in sys.argv

def short(name):
    n = re.sub(r'\[비코어랩\]\s*|일비아\s*', '', name or '')
    n = re.sub(r'\s*/\s*\d+차.*$', '', n)
    return n.strip()[:38]

conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
q = """SELECT po.po_number, po.po_date, po.delivery_date, po.status,
       COALESCE(p.name, pol.product_name) pname, pol.qty_ordered, pol.qty_received
       FROM purchase_order_lines pol
       JOIN purchase_orders po ON po.id = pol.po_id
       LEFT JOIN products p ON p.id = pol.product_id"""
rows = conn.execute(q + " ORDER BY po.delivery_date IS NULL, po.delivery_date").fetchall()
conn.close()

today = datetime.date.today()
out = []
for r in rows:
    if kw and kw not in (r["pname"] or ""): continue
    pending = (r["qty_received"] or 0) < (r["qty_ordered"] or 0) and r["status"] not in ("completed", "cancelled")
    if not show_all and not pending: continue
    dday = ""
    if r["delivery_date"]:
        d = (datetime.date.fromisoformat(r["delivery_date"]) - today).days
        dday = f"D-{d}" if d >= 0 else f"⚠️{-d}일 지남"
    out.append((r["delivery_date"] or "-", r["po_number"], short(r["pname"]), r["qty_ordered"], r["qty_received"] or 0, r["status"], dday))

if show_all: out = out[-30:]
W = "─" * 92
print(f"\n📦 발주 현황 — {'전체(최근 30)' if show_all else '진행 중(미입고)'}{f' · 필터:{kw}' if kw else ''}  ({today})")
print(W)
print(f"{'납품예정':10s}  {'D-day':9s} {'품목':38s} {'수량':>7s} {'기입고':>6s}  {'발주번호':20s}")
print(W)
for d, po, nm, qo, qr, st, dd in out:
    print(f"{d:10s}  {dd:9s} {nm:38s} {qo:>7,} {qr:>6,}  {po:20s}")
print(W)
print(f"총 {len(out)}건 / 발주 수량 합계 {sum(x[3] for x in out):,}개")
