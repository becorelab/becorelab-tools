"""옵시디언 대시보드 자동 갱신 유틸
- 마커 사이 영역을 스크립트가 교체해서 최근 보고서 목록/상태 callout을 최신화
- 매출·재고·광고 세 대시보드가 공통 호출
"""
import os
import re
from datetime import datetime

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _replace_markers(text, marker_name, new_content):
    """<!-- {marker_name}_START --> ... <!-- {marker_name}_END --> 사이를 교체
    마커가 없으면 원본 그대로 반환"""
    pattern = re.compile(
        rf"(<!--\s*{marker_name}_START\s*-->)(.*?)(<!--\s*{marker_name}_END\s*-->)",
        re.DOTALL,
    )
    if not pattern.search(text):
        return text, False
    new_text = pattern.sub(lambda m: f"{m.group(1)}\n{new_content}\n{m.group(3)}", text)
    return new_text, True


def list_recent_reports(folders, limit=7, recurse=False):
    """폴더(단일 또는 리스트) 안에서 YYYY-MM-DD로 시작하는 .md 파일을
    날짜 내림차순으로 반환 (최신 먼저, limit개)
    recurse=True면 하위 폴더까지 스캔 (광고 연도 폴더용)"""
    if isinstance(folders, str):
        folders = [folders]

    found = []  # (date_str, basename_without_ext)
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        if recurse:
            for root, _, files in os.walk(folder):
                for name in files:
                    if not name.endswith(".md"):
                        continue
                    m = DATE_RE.match(name)
                    if m:
                        found.append((m.group(1), name[:-3]))
        else:
            for name in os.listdir(folder):
                if not name.endswith(".md"):
                    continue
                m = DATE_RE.match(name)
                if m:
                    found.append((m.group(1), name[:-3]))

    found.sort(key=lambda x: x[0], reverse=True)
    seen = set()
    unique = []
    for date_str, basename in found:
        if basename in seen:
            continue
        seen.add(basename)
        unique.append((date_str, basename))
    return unique[:limit]


def render_recent_block(reports, empty_msg="> 아직 생성된 보고서가 없습니다."):
    if not reports:
        return empty_msg
    lines = []
    for i, (date_str, basename) in enumerate(reports):
        tag = " — 최신" if i == 0 else ""
        lines.append(f"- [[{basename}]]{tag}")
    return "\n".join(lines)


def render_status_block(last_date, callout_class="", label="정상 운영 중"):
    """상단 상태 — 옵시디언 네이티브 callout"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if last_date:
        return f"> [!success] ✅ {label}\n> 마지막 생성: {last_date} · 갱신 {now}"
    return f"> [!warning] ⚠️ 보고서 없음\n> 최근 기록을 찾지 못했어요 · 갱신 {now}"


def update_dashboard(dashboard_path, reports_folders, limit=7, recurse=False, status_label="정상 운영 중"):
    """대시보드 파일의 STATUS / RECENT 마커 사이를 갱신
    반환: (updated: bool, last_date: str|None, count: int)"""
    if not os.path.isfile(dashboard_path):
        return False, None, 0

    with open(dashboard_path, encoding="utf-8") as f:
        text = f.read()

    reports = list_recent_reports(reports_folders, limit=limit, recurse=recurse)
    last_date = reports[0][0] if reports else None

    recent_block = render_recent_block(reports)
    status_block = render_status_block(last_date, label=status_label)

    text, r1 = _replace_markers(text, "RECENT", recent_block)
    text, r2 = _replace_markers(text, "STATUS", status_block)

    if r1 or r2:
        import tempfile, shutil, subprocess
        try:
            with open(dashboard_path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            subprocess.run(["xattr", "-cr", dashboard_path], capture_output=True)
            try:
                with open(dashboard_path, "w", encoding="utf-8") as f:
                    f.write(text)
            except OSError:
                tmp_dir = os.path.dirname(dashboard_path)
                fd, tmp_path = tempfile.mkstemp(dir=tmp_dir, suffix=".md")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(text)
                os.replace(tmp_path, dashboard_path)
    return (r1 or r2), last_date, len(reports)
