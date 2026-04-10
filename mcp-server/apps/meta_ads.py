"""메타 광고 API MCP 도구 — 파이프보드 없이 직접 조회"""
import json as _json
import httpx

# config는 automation 폴더에 있으므로 여기서 직접 정의
META_ACCESS_TOKEN = "EAA8FG3lEZC18BRF9zom757dImMO9LwK5hF2Deja0tez1GTnHPoaZAZCuAFPLN7EZArT5UOozqcIcjBt8ngFmvs0ls3YKcosOx0JVmHbkYKRQ7ROio2wio7ZA0PuzgYotDrZAxPNtb9uuRq0S64yfncvj4Hf49uAorOZA0Gqy0mhH0ed99ic45hlFA58cFKJS9wxeAZDZD"
META_API_VERSION = "v21.0"
META_BASE = f"https://graph.facebook.com/{META_API_VERSION}"
AD_ACCOUNTS = {
    "일비아": "act_939432264476274",
    "세탁제품": "act_1374146073384332",
}


async def _meta_get(client: httpx.AsyncClient, endpoint: str, params: dict = None):
    p = {"access_token": META_ACCESS_TOKEN}
    if params:
        p.update(params)
    resp = await client.get(f"{META_BASE}/{endpoint}", params=p, timeout=30)
    return resp.json()


def _extract_action(actions, action_type):
    if not actions:
        return 0
    for a in actions:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0


def _extract_action_value(action_values, action_type):
    if not action_values:
        return 0
    for a in action_values:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0


def _format_insights(rows):
    """인사이트 데이터를 보기 좋게 정리"""
    results = []
    for row in rows:
        spend = float(row.get("spend", 0))
        actions = row.get("actions", [])
        action_values = row.get("action_values", [])

        purchases = _extract_action(actions, "purchase")
        purchase_value = _extract_action_value(action_values, "purchase")
        atc = _extract_action(actions, "add_to_cart")
        ic = _extract_action(actions, "initiate_checkout")
        link_clicks = _extract_action(actions, "link_click")

        roas = purchase_value / spend if spend > 0 else 0
        cpp = spend / purchases if purchases > 0 else 0
        aov = purchase_value / purchases if purchases > 0 else 0
        click_to_atc = (atc / link_clicks * 100) if link_clicks > 0 else 0

        entry = {
            "campaign_name": row.get("campaign_name", ""),
            "ad_name": row.get("ad_name", ""),
            "spend": f"{spend:,.0f}원",
            "purchases": f"{int(purchases)}건",
            "purchase_value": f"{purchase_value:,.0f}원",
            "roas": f"{roas:.2f}",
            "cpp": f"{cpp:,.0f}원" if purchases > 0 else "-",
            "aov": f"{aov:,.0f}원" if purchases > 0 else "-",
            "cpc": f"{float(row.get('cpc', 0)):,.0f}원",
            "ctr": f"{float(row.get('ctr', 0)):.1f}%",
            "cpm": f"{float(row.get('cpm', 0)):,.0f}원",
            "impressions": int(row.get("impressions", 0)),
            "clicks": int(row.get("clicks", 0)),
            "link_clicks": int(link_clicks),
            "atc": int(atc),
            "ic": int(ic),
            "click_to_atc": f"{click_to_atc:.1f}%",
            "frequency": f"{float(row.get('frequency', 0)):.2f}",
            "reach": int(row.get("reach", 0)),
        }
        results.append(entry)
    return results


def register(mcp, client):
    """메타 광고 MCP 도구 등록"""

    @mcp.tool()
    async def meta_ad_accounts() -> str:
        """메타 광고 계정 목록 조회. 일비아(act_939432264476274), 세탁제품(act_1374146073384332)"""
        results = {}
        for name, account_id in AD_ACCOUNTS.items():
            data = await _meta_get(client, account_id, {"fields": "name,account_status,balance,currency"})
            results[name] = data
        return _json.dumps(results, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def meta_ad_campaigns(account: str = "일비아") -> str:
        """광고 계정의 캠페인 목록 조회.
        account: '일비아' 또는 '세탁제품'"""
        account_id = AD_ACCOUNTS.get(account, AD_ACCOUNTS["일비아"])
        data = await _meta_get(client, f"{account_id}/campaigns", {
            "fields": "name,status,daily_budget,objective,bid_strategy",
            "limit": "50",
        })
        return _json.dumps(data.get("data", []), ensure_ascii=False, indent=2)

    @mcp.tool()
    async def meta_ad_insights(
        account: str = "일비아",
        date_preset: str = "",
        since: str = "",
        until: str = "",
        level: str = "campaign",
    ) -> str:
        """메타 광고 성과 데이터 조회 (핵심 도구!).

        account: '일비아' 또는 '세탁제품'
        date_preset: 'today', 'yesterday', 'last_7d', 'last_30d' 등
        since/until: 'YYYY-MM-DD' 형식 (date_preset 대신 사용)
        level: 'campaign', 'adset', 'ad'

        반환: 캠페인/광고별 지출, 전환수, ROAS, CPC, CTR, CPM, AOV, 퍼널(ATC/IC/Purchase)
        """
        account_id = AD_ACCOUNTS.get(account, AD_ACCOUNTS["일비아"])
        fields = ",".join([
            "campaign_name", "campaign_id",
            "spend", "impressions", "clicks", "cpc", "cpm", "ctr",
            "actions", "action_values", "cost_per_action_type",
            "frequency", "reach",
        ])
        if level == "ad":
            fields += ",ad_name,ad_id"

        params = {"fields": fields, "level": level, "limit": "100"}
        if date_preset:
            params["date_preset"] = date_preset
        elif since and until:
            params["time_range"] = _json.dumps({"since": since, "until": until})
        else:
            params["date_preset"] = "yesterday"

        data = await _meta_get(client, f"{account_id}/insights", params)
        rows = data.get("data", [])
        formatted = _format_insights(rows)
        return _json.dumps(formatted, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def meta_ad_insights_all(
        date_preset: str = "",
        since: str = "",
        until: str = "",
    ) -> str:
        """두 계정(일비아+세탁제품) 캠페인별 성과를 한번에 조회.

        date_preset: 'today', 'yesterday', 'last_7d', 'last_30d' 등
        since/until: 'YYYY-MM-DD' 형식

        반환: 계정별 캠페인 성과 + 합산 요약
        """
        all_results = {}
        total_spend = 0
        total_purchases = 0
        total_value = 0

        for name, account_id in AD_ACCOUNTS.items():
            fields = ",".join([
                "campaign_name", "campaign_id",
                "spend", "impressions", "clicks", "cpc", "cpm", "ctr",
                "actions", "action_values", "cost_per_action_type",
                "frequency", "reach",
            ])
            params = {"fields": fields, "level": "campaign", "limit": "100"}
            if date_preset:
                params["date_preset"] = date_preset
            elif since and until:
                params["time_range"] = _json.dumps({"since": since, "until": until})
            else:
                params["date_preset"] = "yesterday"

            data = await _meta_get(client, f"{account_id}/insights", params)
            rows = data.get("data", [])
            formatted = _format_insights(rows)
            all_results[name] = formatted

            for row in rows:
                total_spend += float(row.get("spend", 0))
                total_purchases += _extract_action(row.get("actions", []), "purchase")
                total_value += _extract_action_value(row.get("action_values", []), "purchase")

        total_roas = total_value / total_spend if total_spend > 0 else 0
        all_results["합산"] = {
            "총지출": f"{total_spend:,.0f}원",
            "총전환": f"{int(total_purchases)}건",
            "총매출": f"{total_value:,.0f}원",
            "ROAS": f"{total_roas:.2f}",
        }
        return _json.dumps(all_results, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def meta_ad_creatives(
        account: str = "일비아",
        campaign_id: str = "",
    ) -> str:
        """광고 소재(크리에이티브) 목록 조회.
        account: '일비아' 또는 '세탁제품'
        campaign_id: 특정 캠페인 ID (선택)"""
        account_id = AD_ACCOUNTS.get(account, AD_ACCOUNTS["일비아"])
        if campaign_id:
            endpoint = f"{campaign_id}/ads"
        else:
            endpoint = f"{account_id}/ads"
        data = await _meta_get(client, endpoint, {
            "fields": "name,status,creative{title,body,image_url,thumbnail_url}",
            "limit": "50",
        })
        return _json.dumps(data.get("data", []), ensure_ascii=False, indent=2)
