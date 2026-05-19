#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
LOG="/tmp/tars-memory-tree-pr.log"
: > "$LOG"

log() { echo "$@" | tee -a "$LOG"; }

log "==> $(date) push-memory-tree-pr"
log "==> branch: $(git branch --show-current) @ $(git rev-parse --short HEAD)"

REMOTE=origin
if ! git fetch "$REMOTE" >>"$LOG" 2>&1; then
  log "==> origin fetch failed, trying gitee..."
  REMOTE=gitee
  git fetch "$REMOTE" >>"$LOG" 2>&1
fi

git push -u "$REMOTE" feat/v4.1.4-memory-entity-tree >>"$LOG" 2>&1
git push "$REMOTE" v4.1.1 >>"$LOG" 2>&1
log "==> pushed to $REMOTE"

if command -v gh >/dev/null 2>&1; then
  PR_NUM=$(gh pr list --head feat/v4.1.4-memory-entity-tree --base v4.1.1 --json number -q '.[0].number' 2>/dev/null || true)
  if [[ -z "$PR_NUM" || "$PR_NUM" == "null" ]]; then
    gh pr create --base v4.1.1 --head feat/v4.1.4-memory-entity-tree \
      --title "feat(v4.1.4): Memory Entity Tree" \
      --body "## Summary
- 记忆实体树 API（实体 / 谱系 / 搜索 / 关系）
- 记忆页「实体」Tab

## Test plan
- [x] pytest tests/test_memory_tree_api.py
- [ ] /memory 实体 Tab 验收" >>"$LOG" 2>&1
    PR_NUM=$(gh pr list --head feat/v4.1.4-memory-entity-tree --base v4.1.1 --json number -q '.[0].number')
  fi
  gh pr merge "$PR_NUM" --merge >>"$LOG" 2>&1
  log "==> PR merged: #$PR_NUM"
  gh pr view "$PR_NUM" --json url -q .url | tee -a "$LOG"
else
  log "==> gh not installed; push only. Open PR in browser."
fi

log "==> DONE"
