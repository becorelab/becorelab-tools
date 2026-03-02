#!/bin/bash
# iLBiA Claude Code 환경 셋업 스크립트
# 사용법: bash _setup/setup.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== iLBiA Claude Code 환경 셋업 ==="

# 1. 전역 CLAUDE.md + settings.json 복사
mkdir -p ~/.claude
cp "$SCRIPT_DIR/global_CLAUDE.md" ~/.claude/CLAUDE.md
cp "$SCRIPT_DIR/settings.json" ~/.claude/settings.json
echo "[OK] ~/.claude/CLAUDE.md"
echo "[OK] ~/.claude/settings.json (권한 설정)"

# 2. 메모리 파일 복사 (프로젝트 경로 자동 감지)
#    Claude Code는 프로젝트 경로를 기반으로 메모리 폴더를 만듦
#    예: /Users/kymac/claude → -Users-kymac-claude
#       /home/user/claude  → -home-user-claude
# 루트 메모리 (~/claude/)
ROOT_MEMORY="$HOME/.claude/projects/$(echo "$REPO_DIR" | sed 's|^/||; s|/|-|g')/memory"
mkdir -p "$ROOT_MEMORY"
cp "$SCRIPT_DIR/MEMORY.md" "$ROOT_MEMORY/MEMORY.md"
cp "$SCRIPT_DIR/alibaba_notes.md" "$ROOT_MEMORY/alibaba_notes.md"
echo "[OK] $ROOT_MEMORY/"

# 폴더별 메모리 (logistics)
LOGISTICS_MEMORY="$HOME/.claude/projects/$(echo "$REPO_DIR/logistics" | sed 's|^/||; s|/|-|g')/memory"
mkdir -p "$LOGISTICS_MEMORY"
cp "$SCRIPT_DIR/logistics_MEMORY.md" "$LOGISTICS_MEMORY/MEMORY.md"
echo "[OK] $LOGISTICS_MEMORY/"

echo ""
echo "=== 셋업 완료! ==="
echo "이제 각 프로젝트 폴더에서 claude 실행하세요:"
echo "  cd $REPO_DIR/sourcing && claude"
echo "  cd $REPO_DIR/rocket && claude"
echo "  cd $REPO_DIR/instagram && claude"
