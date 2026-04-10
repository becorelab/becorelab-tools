"""옵시디언 볼트 파일 시스템 MCP 도구
두리가 모바일/PC 어디서든 옵시디언 볼트 읽고 쓰기 가능
"""
import os
import json as _json
from pathlib import Path

# 옵시디언 볼트 경로
VAULT_ROOT = Path(r"C:\Users\info\Documents\비코어랩")


def _safe_path(rel_path: str) -> Path:
    """경로 정규화 + 볼트 밖 접근 차단"""
    # 절대 경로면 볼트 루트 기준 상대 경로로 변환
    rel_path = rel_path.lstrip("/").lstrip("\\")
    full = (VAULT_ROOT / rel_path).resolve()
    # 볼트 밖 접근 차단
    try:
        full.relative_to(VAULT_ROOT.resolve())
    except ValueError:
        raise ValueError(f"볼트 밖 접근 차단: {rel_path}")
    return full


def register(mcp, client):
    """옵시디언 MCP 도구 등록"""

    @mcp.tool()
    async def obsidian_list_files(folder: str = "") -> str:
        """옵시디언 볼트의 폴더 안 파일/폴더 목록 조회.
        folder: 볼트 루트 기준 상대 경로 (예: '01. Becorelab AI Agent Team/📢 Ad Performance/2026')
        비어있으면 볼트 루트
        """
        try:
            target = _safe_path(folder) if folder else VAULT_ROOT
            if not target.exists():
                return f"[오류] 폴더 없음: {folder}"
            if not target.is_dir():
                return f"[오류] 폴더가 아님: {folder}"

            items = []
            for item in sorted(target.iterdir()):
                if item.name.startswith("."):
                    continue
                rel = item.relative_to(VAULT_ROOT).as_posix()
                if item.is_dir():
                    items.append(f"📂 {rel}/")
                else:
                    size = item.stat().st_size
                    items.append(f"📄 {rel} ({size:,} bytes)")
            return "\n".join(items) if items else "(빈 폴더)"
        except Exception as e:
            return f"[오류] {e}"

    @mcp.tool()
    async def obsidian_read_file(file_path: str) -> str:
        """옵시디언 볼트의 파일 내용 읽기.
        file_path: 볼트 루트 기준 상대 경로
        예: '01. Becorelab AI Agent Team/📢 Ad Performance/캠페인 현황.md'
        """
        try:
            target = _safe_path(file_path)
            if not target.exists():
                return f"[오류] 파일 없음: {file_path}"
            if not target.is_file():
                return f"[오류] 파일이 아님: {file_path}"
            with open(target, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"[오류] {e}"

    @mcp.tool()
    async def obsidian_write_file(file_path: str, content: str) -> str:
        """옵시디언 볼트에 파일 쓰기 (덮어쓰기).
        file_path: 볼트 루트 기준 상대 경로
        content: 파일 내용 (마크다운)
        """
        try:
            target = _safe_path(file_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return f"[OK] 저장 완료: {file_path} ({len(content)} chars)"
        except Exception as e:
            return f"[오류] {e}"

    @mcp.tool()
    async def obsidian_append_file(file_path: str, content: str) -> str:
        """옵시디언 볼트 파일에 내용 추가 (append).
        파일이 없으면 새로 만들고, 있으면 끝에 추가.
        file_path: 볼트 루트 기준 상대 경로
        content: 추가할 내용
        """
        try:
            target = _safe_path(file_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "a", encoding="utf-8") as f:
                f.write(content)
            return f"[OK] 추가 완료: {file_path} ({len(content)} chars)"
        except Exception as e:
            return f"[오류] {e}"

    @mcp.tool()
    async def obsidian_search(keyword: str, folder: str = "") -> str:
        """옵시디언 볼트에서 키워드로 파일 검색 (파일 이름 + 내용).
        keyword: 검색 키워드
        folder: 검색 범위 (생략 시 전체)
        """
        try:
            search_root = _safe_path(folder) if folder else VAULT_ROOT
            if not search_root.exists():
                return f"[오류] 폴더 없음: {folder}"

            results = []
            for md_file in search_root.rglob("*.md"):
                if md_file.name.startswith("."):
                    continue
                rel = md_file.relative_to(VAULT_ROOT).as_posix()
                # 파일 이름 매칭
                if keyword.lower() in md_file.name.lower():
                    results.append(f"📄 {rel} (이름 일치)")
                    continue
                # 내용 매칭
                try:
                    content = md_file.read_text(encoding="utf-8")
                    if keyword.lower() in content.lower():
                        # 매칭 라인 추출
                        lines = content.split("\n")
                        matches = [
                            f"  L{i+1}: {line.strip()[:100]}"
                            for i, line in enumerate(lines)
                            if keyword.lower() in line.lower()
                        ][:3]
                        results.append(f"📄 {rel}\n" + "\n".join(matches))
                except Exception:
                    continue

                if len(results) >= 20:
                    results.append("(20개 이상, 결과 잘림)")
                    break

            return "\n\n".join(results) if results else f"'{keyword}' 검색 결과 없음"
        except Exception as e:
            return f"[오류] {e}"

    @mcp.tool()
    async def obsidian_recent_files(folder: str = "", limit: int = 10) -> str:
        """옵시디언 볼트의 최근 수정된 파일 목록.
        folder: 검색 범위 (생략 시 전체)
        limit: 반환 개수
        """
        try:
            search_root = _safe_path(folder) if folder else VAULT_ROOT
            files = []
            for md_file in search_root.rglob("*.md"):
                if md_file.name.startswith(".") or "/.obsidian/" in md_file.as_posix():
                    continue
                files.append((md_file.stat().st_mtime, md_file))

            files.sort(reverse=True)
            results = []
            from datetime import datetime
            for mtime, f in files[:limit]:
                rel = f.relative_to(VAULT_ROOT).as_posix()
                dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                results.append(f"📄 [{dt}] {rel}")
            return "\n".join(results) if results else "파일 없음"
        except Exception as e:
            return f"[오류] {e}"
