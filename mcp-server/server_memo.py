#!/usr/bin/env python3
"""
비코어랩 Memo MCP 서버 — 옵시디언 + 이미지 생성

메모/문서/이미지 작업 전용. 평소 켜둬도 가벼움.
도구 약 8개.
"""
import httpx
from mcp.server.fastmcp import FastMCP

from config import TIMEOUT
from apps import obsidian, image_gen

mcp = FastMCP(
    "becorelab-memo",
    instructions="""비코어랩 메모/문서/이미지 서버.

## 옵시디언 볼트 (사무실 PC: C:\\Users\\info\\Documents\\비코어랩)
- obsidian_list_files(folder) — 폴더 안 파일 목록
- obsidian_read_file(path) — 파일 읽기
- obsidian_write_file(path, content) — 새로 쓰기/덮어쓰기
- obsidian_append_file(path, content) — 끝에 추가
- obsidian_search(keyword) — 키워드 검색
- obsidian_recent_files — 최근 수정 파일

## 이미지 생성 (Gemini Nano Banana)
- generate_image(prompt) — 일반 이미지
- generate_banner(prompt, ratio) — 배너용 (16:9, 1:1 등)

## 사용 팁
- 인수인계 메모: '01. Becorelab AI Agent Team/' 폴더 활용
- 일일 작업 기록: '하치 일지/' 같은 폴더에 날짜별 저장
"""
)
client = httpx.AsyncClient(timeout=TIMEOUT)

obsidian.register(mcp, client)
image_gen.register(mcp, client)

if __name__ == "__main__":
    mcp.run()
