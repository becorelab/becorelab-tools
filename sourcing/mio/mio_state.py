"""
미오 대화 상태 관리
업체별/업무별 대화 히스토리와 현재 단계를 JSON으로 저장
"""
import json
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent / "conversations"


def _safe_name(name: str) -> str:
    """파일명에 안전한 문자만 남김"""
    return re.sub(r'[^\w가-힣\-_]', '_', name)[:60]


def get_conversation_path(category: str, supplier_or_subject: str) -> Path:
    """category: 'alibaba', 'youtube' 등 / 업체명 or 주제"""
    folder = BASE_DIR / category
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{_safe_name(supplier_or_subject)}.json"


def load_conversation(category: str, supplier_or_subject: str) -> dict:
    """기존 대화 로드. 없으면 빈 구조 반환"""
    path = get_conversation_path(category, supplier_or_subject)
    if not path.exists():
        return {
            "category": category,
            "subject": supplier_or_subject,
            "created_at": datetime.now().isoformat(),
            "stage": "initial",  # initial → inquired → negotiating → sampled → ordered → closed
            "target_spec": {},
            "target_price": None,
            "messages": [],
            "escalations": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_conversation(state: dict) -> None:
    """대화 상태 저장"""
    path = get_conversation_path(state["category"], state["subject"])
    state["updated_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def append_message(state: dict, role: str, content: str, extra: dict = None) -> None:
    """
    role: 'supplier' (업체), 'mio' (미오 답장), 'owner' (대표님 지시)
    """
    msg = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    if extra:
        msg.update(extra)
    state["messages"].append(msg)


def append_escalation(state: dict, reason: str, owner_reply: str = None) -> None:
    """에스컬레이션 이력 추가"""
    state["escalations"].append({
        "reason": reason,
        "owner_reply": owner_reply,
        "timestamp": datetime.now().isoformat(),
    })


def list_conversations(category: str = None) -> list:
    """전체 대화 목록"""
    result = []
    scan_dirs = [BASE_DIR / category] if category else [d for d in BASE_DIR.iterdir() if d.is_dir()]
    for d in scan_dirs:
        if not d.exists():
            continue
        for f in d.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result.append({
                    "category": data.get("category"),
                    "subject": data.get("subject"),
                    "stage": data.get("stage"),
                    "last_update": data.get("updated_at", data.get("created_at")),
                    "path": str(f),
                })
            except Exception:
                continue
    return sorted(result, key=lambda x: x.get("last_update") or "", reverse=True)
