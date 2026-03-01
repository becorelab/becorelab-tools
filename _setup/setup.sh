#!/bin/bash
# iLBiA Claude Code 환경 셋업 스크립트
# 사용법: bash _setup/setup.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== iLBiA Claude Code 환경 셋업 ==="

# 1. 전역 CLAUDE.md 복사
mkdir -p ~/.claude
cp "$SCRIPT_DIR/global_CLAUDE.md" ~/.claude/CLAUDE.md
echo "[OK] ~/.claude/CLAUDE.md"

# 2. 메모리 파일 복사 (프로젝트 경로 자동 감지)
#    Claude Code는 프로젝트 경로를 기반으로 메모리 폴더를 만듦
#    예: /Users/kymac/claude → -Users-kymac-claude
#       /home/user/claude  → -home-user-claude
MEMORY_DIR="$HOME/.claude/projects/$(echo "$REPO_DIR" | sed 's|^/||; s|/|-|g')/memory"
mkdir -p "$MEMORY_DIR"
cp "$SCRIPT_DIR/MEMORY.md" "$MEMORY_DIR/MEMORY.md"
cp "$SCRIPT_DIR/alibaba_notes.md" "$MEMORY_DIR/alibaba_notes.md"
echo "[OK] $MEMORY_DIR/"

echo ""
echo "=== 셋업 완료! ==="
echo "이제 각 프로젝트 폴더에서 claude 실행하세요:"
echo "  cd $REPO_DIR/sourcing && claude"
echo "  cd $REPO_DIR/rocket && claude"
echo "  cd $REPO_DIR/instagram && claude"
