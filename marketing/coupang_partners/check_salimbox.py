"""살림박스 채널 최근 영상 제목 확인 — 결과를 파일로 저장."""
import os, sys, json
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv(os.path.join(_DIR, "..", "..", "sourcing", "analyzer", ".env"))
from youtube_crawler import enrich_full

ch = enrich_full("UC_b570p2suB2Auc1n2DO2Kg")
out_path = os.path.join(_DIR, "salimbox_titles.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"채널명: {ch.get('title')}\n")
    f.write(f"구독자: {ch.get('subscriber_count'):,}\n\n")
    f.write(f"최근 영상 {len(ch.get('recent_videos', []))}개:\n")
    for i, v in enumerate(ch.get("recent_videos", []), 1):
        title = v.get("title", "")
        views = v.get("view_count", 0)
        f.write(f"  {i}. [{views:>8,} views] {title}\n")
print(f"저장: {out_path}")
