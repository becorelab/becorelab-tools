"""옵시디언 보고서 렌더러 — Claude 라이트 스타일 HTML
- 매출 일일 보고서 (render_sales)
- 재고 일일 보고서 (render_inventory)
"""
from datetime import datetime

CLAUDE_STYLE = """<style>
.claude-doc {
  font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
  color: #1F1E1B;
  line-height: 1.65;
  max-width: 920px;
}
.claude-doc h1, .claude-doc h2, .claude-doc h3 {
  font-family: 'Iowan Old Style', 'Times New Roman', Georgia, serif;
  color: #1F1E1B;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.claude-doc h1 { font-size: 30px; margin-top: 24px; margin-bottom: 8px; }
.claude-doc h2 { font-size: 22px; margin-top: 36px; padding-bottom: 8px; border-bottom: 1px solid #E8E5DD; }
.claude-doc h3 { font-size: 17px; margin-top: 24px; color: #3D3929; }
.claude-doc .sub { color: #6E6B66; font-size: 13px; margin-top: 0; }
.hero-box {
  background: #FAF7F2;
  border: 1px solid #E8E2D8;
  border-left: 4px solid #D97757;
  border-radius: 10px;
  padding: 22px 26px;
  margin: 20px 0;
  font-size: 15px;
  color: #3D3929;
}
.hero-box b { color: #C15F3C; font-weight: 600; }
.hero-box .label { color: #6E6B66; font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; display: block; }
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin: 22px 0;
}
.metric {
  background: #FFFFFF;
  border: 1px solid #E8E5DD;
  border-radius: 12px;
  padding: 18px 20px;
  position: relative;
}
.metric::before {
  content: '';
  position: absolute;
  left: 0; top: 18px; bottom: 18px;
  width: 3px;
  background: #D97757;
  border-radius: 0 3px 3px 0;
}
.metric .m-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6E6B66;
  font-weight: 600;
  margin-bottom: 8px;
  margin-left: 12px;
}
.metric .m-value {
  font-family: 'Iowan Old Style', Georgia, serif;
  font-size: 26px;
  font-weight: 600;
  color: #1F1E1B;
  margin-bottom: 4px;
  margin-left: 12px;
  letter-spacing: -0.02em;
}
.metric .m-sub {
  font-size: 12px;
  color: #6E6B66;
  margin-left: 12px;
  line-height: 1.4;
}
.metric.coral::before { background: #D97757; }
.metric.warm::before  { background: #C97D3C; }
.metric.sage::before  { background: #5A8E5C; }
.metric.slate::before { background: #5A7A9E; }
.metric.dusty::before { background: #B0654A; }
.callout {
  background: #FAF7F2;
  border: 1px solid #E8E2D8;
  border-left: 3px solid #D97757;
  border-radius: 8px;
  padding: 14px 18px;
  margin: 16px 0;
  font-size: 14.5px;
  color: #3D3929;
}
.callout.info    { border-left-color: #5A7A9E; background: #F4F6FA; border-color: #DCE2EC; }
.callout.warn    { border-left-color: #C97D3C; background: #FBF6EE; border-color: #ECE0CC; }
.callout.danger  { border-left-color: #C45252; background: #FBF2F0; border-color: #ECD5D0; }
.callout.success { border-left-color: #5A8E5C; background: #F2F7F2; border-color: #D8E5D6; }
.callout b { color: #1F1E1B; font-weight: 600; }
.callout .ctitle {
  font-family: 'Iowan Old Style', Georgia, serif;
  font-size: 14px;
  font-weight: 600;
  display: block;
  margin-bottom: 6px;
  color: #1F1E1B;
}
.callout ul { margin: 6px 0 0 0; padding-left: 18px; }
.callout li { margin: 3px 0; }
.claude-doc table {
  border-collapse: collapse;
  width: 100%;
  margin: 18px 0;
  font-size: 14px;
  background: #FFFFFF;
  border: 1px solid #E8E5DD;
  border-radius: 8px;
  overflow: hidden;
}
.claude-doc th {
  background: #FAF7F2;
  color: #3D3929;
  font-weight: 600;
  font-size: 12.5px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid #E8E5DD;
}
.claude-doc td {
  padding: 11px 14px;
  border-bottom: 1px solid #F2EFE9;
  color: #3D3929;
}
.claude-doc tr:last-child td { border-bottom: none; }
.claude-doc td.num { text-align: right; font-variant-numeric: tabular-nums; }
.claude-doc td.ctr { text-align: center; }
.tag {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  margin-right: 4px;
}
.tag.coral { background: #FAF7F2; color: #C15F3C; border: 1px solid #ECD9CC; }
.tag.sage  { background: #F2F7F2; color: #5A8E5C; border: 1px solid #D8E5D6; }
.tag.warn  { background: #FBF6EE; color: #C97D3C; border: 1px solid #ECE0CC; }
.tag.dusty { background: #FBF2F0; color: #C45252; border: 1px solid #ECD5D0; }
.claude-doc .foot { color: #8E8B86; font-size: 12px; margin-top: 28px; padding-top: 12px; border-top: 1px solid #F2EFE9; }
</style>
"""


def _fmt_won(n):
    try:
        return f"₩{int(n):,}"
    except Exception:
        return str(n)


def _esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_sales(data):
    """매출 일일 보고서 HTML 렌더링
    data 예시:
      {
        "date": "2026-04-16", "weekday": "목",
        "settlement": 2405203, "amount": 2535420, "count": 177,
        "change_str": "▼60.9%", "change_kind": "down" | "up" | "none",
        "month": 4, "month_total": 43251563, "month_days": 16,
        "channels": [{"name": "카페24", "count": 141, "settlement": 1851290}, ...],
        "products_top5": [{"name": "...", "qty": 168, "settlement": 1674315}, ...],
        "alerts_red": ["이염방지시트 — -34개", ...],
        "alerts_yellow": ["스타배송 건조기 — 1개", ...]
      }
    """
    date = data.get("date", "")
    weekday = data.get("weekday", "")
    settlement = data.get("settlement", 0)
    amount = data.get("amount", 0)
    count = data.get("count", 0)
    change_str = data.get("change_str", "")
    change_kind = data.get("change_kind", "none")
    month = data.get("month", "")
    month_total = data.get("month_total", 0)
    month_days = data.get("month_days", 0)
    channels = data.get("channels", [])
    products_top5 = data.get("products_top5", [])
    alerts_red = data.get("alerts_red", [])
    alerts_yellow = data.get("alerts_yellow", [])

    change_class = "coral" if change_kind == "up" else ("dusty" if change_kind == "down" else "slate")

    out = []
    out.append(CLAUDE_STYLE)
    out.append('<div class="claude-doc">')
    out.append(f'<h1>📊 매출 일일 보고서 — {_esc(date)} ({_esc(weekday)})</h1>')
    out.append(f'<p class="sub">자동 생성: {datetime.now().strftime("%Y-%m-%d %H:%M")} · iLBiA 물류 시스템</p>')

    # Hero
    out.append('<div class="hero-box">')
    out.append('<span class="label">오늘의 핵심</span>')
    out.append(f'총 정산 <b>{_fmt_won(settlement)}</b> · 전일 대비 <b>{_esc(change_str)}</b> · 주문 <b>{count:,}건</b><br>')
    out.append(f'{_esc(month)}월 누적 <b>{_fmt_won(month_total)}</b> ({month_days}일간)')
    out.append('</div>')

    # KPI grid
    out.append('<div class="metric-grid">')
    out.append(f'<div class="metric {change_class}"><div class="m-label">총 정산</div><div class="m-value">{_fmt_won(settlement)}</div><div class="m-sub">전일 대비 {_esc(change_str)}</div></div>')
    out.append(f'<div class="metric slate"><div class="m-label">총 판매</div><div class="m-value">{_fmt_won(amount)}</div><div class="m-sub">참고 (할인·수수료 전)</div></div>')
    out.append(f'<div class="metric warm"><div class="m-label">주문 수</div><div class="m-value">{count:,}건</div><div class="m-sub">일일 주문 총수</div></div>')
    out.append(f'<div class="metric sage"><div class="m-label">{_esc(month)}월 누적</div><div class="m-value">{_fmt_won(month_total)}</div><div class="m-sub">{month_days}일간 합계</div></div>')
    out.append('</div>')

    # 채널별
    if channels:
        out.append('<h2>📈 채널별 매출 (정산금액 큰 순)</h2>')
        out.append('<table><thead><tr><th>채널</th><th style="text-align:right">주문</th><th style="text-align:right">정산</th></tr></thead><tbody>')
        for ch in channels:
            out.append(f'<tr><td>{_esc(ch.get("name",""))}</td><td class="num">{ch.get("count",0):,}건</td><td class="num">{_fmt_won(ch.get("settlement",0))}</td></tr>')
        out.append('</tbody></table>')

    # 상품 TOP 5
    if products_top5:
        out.append('<h2>🏷️ 상품 TOP 5 (정산금액)</h2>')
        out.append('<table><thead><tr><th>상품명</th><th style="text-align:right">판매 수량</th><th style="text-align:right">정산</th></tr></thead><tbody>')
        for p in products_top5:
            out.append(f'<tr><td>{_esc(p.get("name",""))}</td><td class="num">{p.get("qty",0):,}개</td><td class="num">{_fmt_won(p.get("settlement",0))}</td></tr>')
        out.append('</tbody></table>')

    # 재고 알림
    if alerts_red or alerts_yellow:
        out.append('<h2>🚨 재고 알림</h2>')
        if alerts_red:
            out.append('<div class="callout danger"><span class="ctitle">🔴 마이너스 재고</span><ul>')
            for a in alerts_red:
                out.append(f'<li>{_esc(a)}</li>')
            out.append('</ul></div>')
        if alerts_yellow:
            out.append('<div class="callout warn"><span class="ctitle">⚠️ 재고 부족 (10개 이하)</span><ul>')
            for a in alerts_yellow:
                out.append(f'<li>{_esc(a)}</li>')
            out.append('</ul></div>')
    else:
        out.append('<div class="callout success"><span class="ctitle">✅ 재고 양호</span>모든 상품이 안전 재고 이상입니다.</div>')

    out.append('<p class="foot">자동 생성 by iLBiA 물류 시스템</p>')
    out.append('</div>')
    return "\n".join(out)


def render_inventory(data):
    """재고 일일 보고서 HTML 렌더링
    data 예시:
      {
        "date": "2026-04-17", "weekday": "금",
        "window": 90, "lead": 30, "safety": 30,
        "cache_ts": "2026-04-17T04:16",
        "urgent_count": 7, "warning_count": 5, "ok_count": 4,
        "urgent": [{"name":..., "current_stock":..., "days_to_stockout":..., "recommend_qty":..., "pending_qty":...}, ...],
        "warning": [...],
        "all_items": [{...}]  (정렬된 전체)
      }
    """
    date = data.get("date", "")
    weekday = data.get("weekday", "")
    window = data.get("window", 90)
    lead = data.get("lead", 30)
    safety = data.get("safety", 30)
    cache_ts = data.get("cache_ts", "")
    urgent_count = data.get("urgent_count", 0)
    warning_count = data.get("warning_count", 0)
    ok_count = data.get("ok_count", 0)
    urgent = data.get("urgent", [])
    warning = data.get("warning", [])
    all_items = data.get("all_items", [])

    out = []
    out.append(CLAUDE_STYLE)
    out.append('<div class="claude-doc">')
    out.append(f'<h1>📦 재고 일일 보고서 — {_esc(date)} ({_esc(weekday)})</h1>')
    out.append(f'<p class="sub">데이터 수집: {_esc(cache_ts[:16] if cache_ts else "알 수 없음")} · 분석 기간 {window}일 · 리드타임 {lead}일 + 안전재고 {safety}일</p>')

    # Hero 요약
    out.append('<div class="hero-box">')
    out.append('<span class="label">오늘의 핵심</span>')
    out.append(f'<b>🔴 {urgent_count}개</b> 즉시 발주 필요 · <b>🟡 {warning_count}개</b> 30일 내 발주 · <b>🟢 {ok_count}개</b> 재고 양호')
    out.append('</div>')

    # KPI grid
    out.append('<div class="metric-grid">')
    out.append(f'<div class="metric dusty"><div class="m-label">즉시 발주</div><div class="m-value">{urgent_count}개</div><div class="m-sub">🔴 Urgent</div></div>')
    out.append(f'<div class="metric warm"><div class="m-label">30일 내 발주</div><div class="m-value">{warning_count}개</div><div class="m-sub">🟡 Warning</div></div>')
    out.append(f'<div class="metric sage"><div class="m-label">재고 양호</div><div class="m-value">{ok_count}개</div><div class="m-sub">🟢 OK</div></div>')
    out.append('</div>')

    # 발주 필요 품목
    if urgent:
        out.append('<h2>⚠️ 즉시 발주 필요</h2>')
        out.append('<div class="callout danger"><ul>')
        for r in urgent:
            pend = f' <span class="tag warn">발주중 {r.get("pending_qty",0):,}개</span>' if r.get("pending_qty", 0) > 0 else ""
            dts = r.get("days_to_stockout")
            dts_str = f"{dts:.0f}일" if dts is not None else "-"
            out.append(f'<li><b>{_esc(r.get("name",""))}</b> — 재고 {r.get("current_stock",0):,}개, 잔여 {dts_str}, 권장 발주 {r.get("recommend_qty",0):,}개{pend}</li>')
        out.append('</ul></div>')

    if warning:
        out.append('<h2>🟡 30일 내 발주 필요</h2>')
        out.append('<div class="callout warn"><ul>')
        for r in warning:
            pend = f' <span class="tag sage">발주중 {r.get("pending_qty",0):,}개</span>' if r.get("pending_qty", 0) > 0 else ""
            dts = r.get("days_to_stockout")
            dts_str = f"{dts:.0f}일" if dts is not None else "-"
            out.append(f'<li><b>{_esc(r.get("name",""))}</b> — 재고 {r.get("current_stock",0):,}개, 잔여 {dts_str}{pend}</li>')
        out.append('</ul></div>')

    # 전체 품목 현황
    if all_items:
        out.append('<h2>📋 전체 품목 현황</h2>')
        out.append('<table><thead><tr><th>상품명</th><th style="text-align:right">현재고</th><th style="text-align:right">전일 출고</th><th style="text-align:right">일평균</th><th style="text-align:right">잔여</th><th style="text-align:center">상태</th></tr></thead><tbody>')
        status_emoji = {"urgent": "🔴", "warning": "🟡", "ok": "🟢", "unknown": "⚪"}
        for r in all_items:
            stock = f"{r.get('current_stock'):,}" if r.get("current_stock") is not None else "-"
            yq = f"{r.get('yesterday_qty'):,}" if r.get("yesterday_qty") else "-"
            avg_v = r.get("daily_avg", 0) or 0
            avg_str = f"{avg_v:.1f}" if avg_v > 0 else "-"
            dts = r.get("days_to_stockout")
            dts_str = f"{dts:.0f}일" if dts is not None and dts < 999 else "충분"
            emoji = status_emoji.get(r.get("status", "unknown"), "⚪")
            out.append(f'<tr><td>{_esc(r.get("name",""))}</td><td class="num">{stock}</td><td class="num">{yq}</td><td class="num">{avg_str}</td><td class="num">{dts_str}</td><td class="ctr">{emoji}</td></tr>')
        out.append('</tbody></table>')

    out.append('<p class="foot">자동 생성 by iLBiA 물류 시스템</p>')
    out.append('</div>')
    return "\n".join(out)
