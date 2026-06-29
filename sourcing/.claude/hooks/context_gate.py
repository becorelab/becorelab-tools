#!/usr/bin/env python3
"""맥락 관문 hook (UserPromptSubmit) — 소싱 하치 전용.

작업 프로토콜 "맥락 관문"을 하치의 의지가 아니라 시스템으로 강제한다.
대표님 프롬프트가 '작업성'이고, 관련 과거 기록(세션노트/parking_lot/방법론/메모리)이
실제로 존재할 때만, 그 기록을 하치 컨텍스트에 자동 주입한다.

설계 원칙
- 잡담/짧은 답/인사엔 침묵 (작업 키워드 없거나 매칭 0 → 무출력)
- 매칭된 기록이 있을 때만, 상위 몇 개만 간결히 (노이즈 최소)
- 출력은 stdout → Claude 컨텍스트에만 주입 (대표님 화면엔 안 보임)
"""
import sys, json, os, re, glob

VAULT_NOTES = ("/Users/macmini_ky/Library/CloudStorage/GoogleDrive-cky2833@gmail.com/"
               "내 드라이브/Claude AI work space/remotely-save/비코어랩/"
               "01. Becorelab AI Agent Team/3️⃣ Resources/📝 Agent Notes")
SOURCING_DIR = "/Users/macmini_ky/ClaudeAITeam/sourcing"
MEM_DIRS = [
    "/Users/macmini_ky/.claude/projects/-Users-macmini-ky-ClaudeAITeam/memory",
    "/Users/macmini_ky/.claude/projects/-Users-macmini-ky/memory",
]

# 작업 키워드가 아닌 흔한 말 (이것만 있으면 침묵)
STOP = set(
    "하치 하치야 대표 대표님 해줘 해주 해줄 그거 이거 저거 그게 이게 어떻게 어떤 그리고 그래 그러면 "
    "우리 지금 오늘 내일 어제 너는 니가 너가 제발 진짜 정말 그냥 좀더 이제 다시 그건 이건 부탁 "
    "보자 그럼 근데 그런데 그래서 아니 응응 네네 이제부터 라고 라는 에서 으로 한테 까지 부터 처럼 "
    "맞아 맞고 알겠 알았 좋아 좋은 싫어 멍청 보지 이따 이거부터 고쳐 고쳐봐 안그 어기 했어 했네 한거 했잖아".split()
)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    prompt = (data.get("prompt") or "").strip()
    if len(prompt) < 6:
        return

    words = re.findall(r"[가-힣A-Za-z]{2,}", prompt)
    seen = []
    for w in words:
        if w in STOP or w in seen:
            continue
        seen.append(w)
    kws = [w for w in seen if len(w) >= 2]
    if not kws:
        return

    # 검색 대상 파일
    targets = []
    targets += glob.glob(os.path.join(SOURCING_DIR, "*.md"))
    targets += glob.glob(os.path.join(VAULT_NOTES, "**", "*.md"), recursive=True)
    for m in MEM_DIRS:
        targets += glob.glob(os.path.join(m, "*.md"))

    hits = {}
    for f in targets:
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except Exception:
            continue
        base = os.path.basename(f)
        score = 0
        for kw in kws:
            if kw in base:
                score += 3          # 파일명 매칭은 강한 신호
            c = content.count(kw)
            if c:
                score += min(c, 3)  # 본문 매칭 (포화)
        if score >= 4:              # 임계 — 우연한 단어 1개로는 발동 안 함
            lines = []
            for line in content.splitlines():
                s = line.strip()
                if len(s) > 4 and sum(1 for kw in kws if kw in s) >= 1:
                    lines.append(s[:110])
                if len(lines) >= 2:
                    break
            hits[f] = (score, lines)

    if not hits:
        return

    ranked = sorted(hits.items(), key=lambda x: -x[1][0])[:6]
    out = [
        "🔒 [맥락 관문] 이 작업과 관련된 과거 기록이 있습니다. "
        "추측·재구현·'처음부터 새로' 전에 **아래를 먼저 읽으세요** (작업 프로토콜 강제):"
    ]
    for f, (score, lines) in ranked:
        out.append(f"• {f}")
        for ln in lines:
            out.append(f"    ↳ {ln}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
