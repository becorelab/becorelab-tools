"""
NotebookLM 연동 모듈
- 리뷰 텍스트를 NotebookLM 노트북에 업로드
- 노트북 기반 질문/답변
- nlm CLI 래퍼 (PYTHONUTF8=1 필수)
"""

import subprocess
import json
import os
import re

NLM_PATH = r"C:\Users\pnp28\.local\bin\nlm.exe"
NLM_ENV = {**os.environ, "PYTHONUTF8": "1"}


def _nlm(args: list, input_text: str = None, timeout: int = 60) -> dict:
    """nlm CLI 실행 → JSON 파싱 결과 반환"""
    # nlm이 없으면 PATH에서 탐색
    cmd = [NLM_PATH] + args if os.path.exists(NLM_PATH) else ["nlm"] + args

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=NLM_ENV,
        timeout=timeout,
        input=input_text,
    )
    output = (result.stdout or "") + (result.stderr or "")

    # JSON 블록 추출 시도
    json_match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', output)
    if json_match:
        try:
            return {"ok": True, "data": json.loads(json_match.group())}
        except json.JSONDecodeError:
            pass

    # JSON 없으면 텍스트 그대로
    return {"ok": result.returncode == 0, "text": output.strip()}


def is_available() -> bool:
    """nlm 설치 + 로그인 여부 확인"""
    try:
        r = _nlm(["list", "notebooks"], timeout=15)
        return r.get("ok", False)
    except Exception:
        return False


def create_notebook(title: str) -> str:
    """노트북 생성 → notebook_id 반환"""
    # create 후 list에서 title 매칭으로 ID 찾기
    _nlm(["create", "notebook", title], timeout=30)

    r = _nlm(["list", "notebooks"], timeout=15)
    if r.get("ok") and isinstance(r.get("data"), list):
        for nb in r["data"]:
            if nb.get("title") == title:
                return nb["id"]
    return ""


def add_text_source(notebook_id: str, text: str, title: str = "") -> str:
    """텍스트 소스 추가 → source_id 반환"""
    args = ["add", "text", notebook_id, text]
    if title:
        args += ["--title", title]
    r = _nlm(args, timeout=120)

    # "Source ID: xxx" 패턴 파싱
    text_out = r.get("text", "")
    id_match = re.search(r'Source ID:\s*([a-f0-9-]{36})', text_out)
    if id_match:
        return id_match.group(1)

    # JSON에서 id 추출 시도
    if r.get("ok") and isinstance(r.get("data"), dict):
        return r["data"].get("id", "")
    return ""


def query(notebook_id: str, question: str, conversation_id: str = "", timeout: int = 120) -> dict:
    """노트북에 질문 → {answer, conversation_id, citations} 반환"""
    args = ["query", "notebook", notebook_id, question]
    if conversation_id:
        args += ["--conversation-id", conversation_id]

    r = _nlm(args, timeout=timeout)

    if r.get("ok") and isinstance(r.get("data"), dict):
        value = r["data"].get("value", r["data"])
        return {
            "answer": value.get("answer", ""),
            "conversation_id": value.get("conversation_id", ""),
            "citations": value.get("references", []),
        }

    # 텍스트 응답 폴백
    return {"answer": r.get("text", "응답 없음"), "conversation_id": "", "citations": []}


def get_or_create_notebook(scan_id: int, keyword: str) -> str:
    """스캔 ID에 해당하는 노트북 찾기 → 없으면 생성"""
    title_prefix = f"[소싱콕] {keyword}"

    r = _nlm(["list", "notebooks"], timeout=15)
    if r.get("ok") and isinstance(r.get("data"), list):
        for nb in r["data"]:
            if nb.get("title", "").startswith(title_prefix):
                return nb["id"]

    # 없으면 생성
    import datetime
    date_str = datetime.date.today().strftime("%y%m%d")
    title = f"{title_prefix} 리뷰분석_{date_str}"
    return create_notebook(title)


def build_review_text(reviews_by_product: dict, keyword: str) -> str:
    """상품별 리뷰 딕셔너리 → NotebookLM 업로드용 텍스트 변환"""
    lines = [f"# {keyword} 쿠팡 상위 상품 리뷰 데이터\n"]

    for product_name, reviews in reviews_by_product.items():
        lines.append(f"\n## 상품: {product_name}")
        lines.append(f"리뷰 수: {len(reviews)}개\n")
        for i, rv in enumerate(reviews, 1):
            rating = rv.get("rating") or rv.get("score", "")
            content = rv.get("content") or rv.get("text") or rv.get("reviewContent", "")
            if content:
                lines.append(f"{i}. [별점 {rating}] {content[:300]}")

    return "\n".join(lines)
