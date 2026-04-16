"""
미오 옵시디언 히스토리 작성
대화가 끝났거나 에스컬레이션 시 Claude 디자인 노트 생성
"""
import re
from pathlib import Path
from datetime import datetime

VAULT_ROOT = Path(r"C:\Users\info\Documents\비코어랩\01. Becorelab AI Agent Team")

CATEGORY_FOLDER = {
    "alibaba": VAULT_ROOT / "1️⃣ Projects" / "🔍 소싱 파이프라인" / "미오 대화",
    # 향후 추가: "youtube", "customer" 등
}

STYLE_BLOCK = """<style>
.claude-doc { font-family: -apple-system,'Segoe UI',system-ui,sans-serif; color:#1F1E1B; line-height:1.65; }
.claude-doc h2 { font-family:'Iowan Old Style',Georgia,serif; font-size:20px; font-weight:600; margin-top:28px; padding-bottom:8px; border-bottom:1px solid #E8E5DD; }
.meta-box { background:#FAF7F2; border:1px solid #E8E2D8; border-left:4px solid #D97757; border-radius:8px; padding:14px 18px; margin:14px 0; font-size:13px; }
.msg { background:#FFFFFF; border:1px solid #E8E5DD; border-radius:8px; padding:12px 16px; margin:10px 0; }
.msg.supplier { border-left:3px solid #5A7A9E; }
.msg.mio { border-left:3px solid #D97757; background:#FFF8F3; }
.msg.owner { border-left:3px solid #5A8E5C; background:#F2F7F2; }
.msg .role { font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:#6E6B66; font-weight:600; margin-bottom:6px; }
.msg .ts { font-size:11px; color:#8C887F; float:right; }
.escalation { background:#FBF6EE; border:1px solid #ECE0CC; border-left:3px solid #C97D3C; border-radius:8px; padding:12px 16px; margin:10px 0; font-size:13px; }
</style>
"""


def _safe_filename(name: str) -> str:
    return re.sub(r'[^\w가-힣\-_]', '_', name)[:80]


def _role_label(role: str) -> str:
    return {"supplier": "🏭 공급업체", "mio": "🐰 미오", "owner": "👤 대표님"}.get(role, role)


def write_history(state: dict) -> Path:
    """
    대화 상태를 옵시디언 노트로 저장
    파일명: {업체명}_{YYYY-MM-DD}.md
    """
    category = state.get("category", "unknown")
    folder = CATEGORY_FOLDER.get(category, VAULT_ROOT / "🤖 미오 대화" / category)
    folder.mkdir(parents=True, exist_ok=True)

    subject = state.get("subject", "unknown")
    created = state.get("created_at", datetime.now().isoformat())[:10]
    filename = f"{_safe_filename(subject)}_{created}.md"
    path = folder / filename

    lines = [STYLE_BLOCK, '<div class="claude-doc">', "",
             f"# {subject}", ""]

    # 메타 박스
    meta_lines = [
        f"**카테고리**: {category}",
        f"**현재 단계**: {state.get('stage', '-')}",
        f"**생성**: {state.get('created_at', '-')[:19]}",
        f"**최종 수정**: {state.get('updated_at', '-')[:19]}",
    ]
    if state.get("target_spec"):
        meta_lines.append(f"**타겟 스펙**: {state['target_spec']}")
    if state.get("target_price"):
        meta_lines.append(f"**타겟 가격**: {state['target_price']}")
    lines.append('<div class="meta-box">' + "<br>".join(meta_lines) + '</div>')
    lines.append("")

    # 메시지 로그
    lines.append("<h2>💬 대화 기록</h2>")
    for msg in state.get("messages", []):
        role = msg.get("role", "")
        ts = msg.get("timestamp", "")[:19].replace("T", " ")
        content = (msg.get("content", "") or "").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(
            f'<div class="msg {role}">'
            f'<span class="ts">{ts}</span>'
            f'<div class="role">{_role_label(role)}</div>'
            f'<div>{content}</div>'
            f'</div>'
        )

    # 에스컬레이션 로그
    if state.get("escalations"):
        lines.append("<h2>🚨 에스컬레이션</h2>")
        for esc in state["escalations"]:
            ts = esc.get("timestamp", "")[:19].replace("T", " ")
            reason = esc.get("reason", "")
            owner = esc.get("owner_reply") or "(답변 대기)"
            lines.append(
                f'<div class="escalation">'
                f'<b>[{ts}]</b> {reason}<br>'
                f'<b>대표님 답변</b>: {owner}'
                f'</div>'
            )

    lines.append("</div>")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
