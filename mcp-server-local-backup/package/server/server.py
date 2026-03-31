"""
비코어랩 MCP 서버 — Claude 데스크탑에서 앱 데이터 조회
물류(8082) + 소싱콕(8090) API 연동
"""
import json
import sys
import urllib.request
import urllib.error


def call_api(url, method="GET", timeout=30):
    """로컬 API 호출"""
    try:
        req = urllib.request.Request(url, method=method)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def call_api_text(url, timeout=30):
    """텍스트 API 호출"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        return f"오류: {e}"


# MCP 도구 정의
TOOLS = [
    {
        "name": "daily_report",
        "description": "일매출 보고서 조회. 어제 매출, 채널별 매출, 재고 알림 등",
        "inputSchema": {"type": "object", "properties": {"date": {"type": "string", "description": "날짜 (YYYY-MM-DD). 생략하면 어제"}}, "required": []}
    },
    {
        "name": "inventory_report",
        "description": "재고 보고서. 재고 부족/마이너스 알림 포함",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "order_analysis",
        "description": "발주 분석. 즉시발주/30일내/양호 품목 분류",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "sales_monthly",
        "description": "월간 매출 누적",
        "inputSchema": {"type": "object", "properties": {"month": {"type": "string", "description": "월 (YYYY-MM). 생략하면 이번달"}}, "required": []}
    },
    {
        "name": "go_items",
        "description": "GO 판정 소싱 아이템 목록. 기회점수 높은 순",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "scan_keyword",
        "description": "키워드로 쿠팡 시장 스캔 시작",
        "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string", "description": "스캔할 키워드"}}, "required": ["keyword"]}
    },
    {
        "name": "scan_detail",
        "description": "특정 스캔 ID의 상세 데이터 (상품목록, 키워드, 기회점수)",
        "inputSchema": {"type": "object", "properties": {"scan_id": {"type": "integer", "description": "스캔 ID"}}, "required": ["scan_id"]}
    },
    {
        "name": "goldbox_products",
        "description": "오늘 골드박스 상품 목록",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "goldbox_autoscan_results",
        "description": "골드박스 자동 스캔 결과 (기회점수 TOP)",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "settlements",
        "description": "월별 매출 정산 데이터 조회",
        "inputSchema": {"type": "object", "properties": {"month": {"type": "string", "description": "월 (YYYY-MM)"}}, "required": ["month"]}
    },
]


def handle_tool(name, args):
    """도구 실행"""
    if name == "daily_report":
        date = args.get("date", "")
        url = f"http://localhost:8082/api/daily-report?format=text"
        if date:
            url += f"&date={date}"
        return call_api_text(url)

    elif name == "inventory_report":
        return call_api_text("http://localhost:8082/api/inventory-report?format=text")

    elif name == "order_analysis":
        return call_api_text("http://localhost:8082/api/order-analysis?format=text")

    elif name == "sales_monthly":
        month = args.get("month", "")
        url = "http://localhost:8082/api/sales-monthly"
        if month:
            url += f"?month={month}"
        data = call_api(url)
        if "error" in data:
            return f"오류: {data['error']}"
        return f"월간 매출 ({data.get('month', '')}): 정산 {data.get('total_settlement', 0):,}원 / 판매 {data.get('total_amount', 0):,}원 / {data.get('days_with_data', 0)}일 데이터"

    elif name == "go_items":
        data = call_api("http://localhost:8090/api/opportunities?status=go")
        items = data.get("opportunities", [])
        if not items:
            return "GO 판정 아이템이 없습니다."
        lines = [f"GO 판정 아이템 {len(items)}개:\n"]
        for i, item in enumerate(items[:20], 1):
            lines.append(f"{i}. {item.get('keyword', '')} — 기회점수 {item.get('opportunity_score', 0)}점, 월매출 {item.get('avg_revenue', 0):,}원")
        return "\n".join(lines)

    elif name == "scan_keyword":
        keyword = args.get("keyword", "")
        url = "http://localhost:8090/api/scan/manual"
        data = json.dumps({"keyword": keyword}).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            return f"스캔 시작! scan_id: {result.get('scan_id', '')} — {result.get('message', '')}"
        except Exception as e:
            return f"스캔 실패: {e}"

    elif name == "scan_detail":
        scan_id = args.get("scan_id", 0)
        data = call_api(f"http://localhost:8090/api/scan/{scan_id}")
        if not data.get("success"):
            return f"스캔 {scan_id} 데이터 없음"
        scan = data.get("scan", {})
        products = data.get("products", [])[:10]
        lines = [f"키워드: {scan.get('keyword', '')} | 기회점수: {scan.get('opportunity_score', 0)} | 상태: {scan.get('status', '')}\n"]
        lines.append(f"상위 상품 {len(products)}개:")
        for i, p in enumerate(products, 1):
            lines.append(f"  {i}. {p.get('product_name', '')[:40]} — {p.get('price', 0):,}원, 월매출 {p.get('revenue_monthly', 0):,}원")
        return "\n".join(lines)

    elif name == "goldbox_products":
        data = call_api("http://localhost:8090/api/goldbox/products")
        products = data.get("products", [])
        if not products:
            return "오늘 골드박스 상품이 없습니다. 수집이 필요해요."
        lines = [f"골드박스 상품 {len(products)}개:\n"]
        for i, p in enumerate(products[:15], 1):
            name = p.get("name", p.get("product_name", ""))[:40]
            price = p.get("price", 0)
            lines.append(f"{i}. {name} — {price:,}원")
        return "\n".join(lines)

    elif name == "goldbox_autoscan_results":
        data = call_api("http://localhost:8090/api/goldbox/auto-scan/results")
        scans = data.get("scans", [])
        if not scans:
            return "골드박스 자동 스캔 결과가 없습니다."
        lines = [f"골드박스 스캔 결과 TOP 10:\n"]
        for i, s in enumerate(scans[:10], 1):
            lines.append(f"{i}. {s.get('keyword', '')} — 기회점수 {s.get('opportunity_score', 0)}점")
        return "\n".join(lines)

    elif name == "settlements":
        month = args.get("month", "")
        data = call_api(f"http://localhost:8082/api/settlements/{month}")
        if data.get("status") != "ok":
            return f"{month} 정산 데이터 없음"
        channels = data.get("data", {}).get("channels", {})
        lines = [f"{month} 매출 정산:\n"]
        for ch, info in channels.items():
            summary = info.get("summary", {})
            lines.append(f"  {ch}: 정산 {summary.get('settlement', 0):,}원 / {summary.get('qty', 0)}개")
        return "\n".join(lines)

    return f"알 수 없는 도구: {name}"


# MCP 프로토콜 (stdio)
def main():
    for line in sys.stdin:
        try:
            msg = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        msg_id = msg.get("id")
        method = msg.get("method", "")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "becorelab-mcp", "version": "1.0.0"}
                }
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS}
            }
        elif method == "tools/call":
            tool_name = msg.get("params", {}).get("name", "")
            tool_args = msg.get("params", {}).get("arguments", {})
            result_text = handle_tool(tool_name, tool_args)
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}]
                }
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {}
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
