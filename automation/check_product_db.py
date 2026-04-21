from pathlib import Path

BASE = Path(r"C:\Users\User\Documents\비코어랩\01. Becorelab AI Agent Team\3️⃣ Resources\🗂️ 상품 DB\상품 상세")

skip = {"| - |", "|  |", "[ ]", "---", "#", ">", "tags:", "상품명:", "기회점수:", "단계:", "타임보드", "최종 판단", "빠른 정보"}

results = []
for folder in sorted(BASE.iterdir()):
    if not folder.is_dir():
        continue
    f = folder / "상품 정보.md"
    if not f.exists():
        continue
    lines = f.read_text(encoding="utf-8").splitlines()
    filled = [l for l in lines if l.strip() and not any(s in l for s in skip)]
    score = float("nan")
    for l in lines:
        if "기회점수:" in l:
            try: score = float(l.split("`")[1])
            except: pass
    results.append((score, folder.name, len(filled)))

results.sort(key=lambda x: -x[0] if x[0]==x[0] else 0)
print(f"{'상품명':<20} {'기회점수':>6}  {'채움 여부'}")
print("-" * 45)
for score, name, cnt in results:
    status = "비어있음" if cnt < 5 else f"일부 채움({cnt}줄)"
    print(f"{name:<20} {score:>6.1f}  {status}")
