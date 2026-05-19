#!/usr/bin/env bash
# 在本机「系统终端」运行（Cursor Agent 内 git 往往无 DNS，无法代推）
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 仓库: $(pwd)"
echo "==> 分支: $(git branch --show-current) @ $(git rev-parse --short HEAD)"
echo "==> 远程 gitee: $(git remote get-url gitee)"

git fetch gitee

echo "==> 推送 feature 分支..."
git push -u gitee feat/v4.1.4-memory-entity-tree

echo "==> 推送 v4.1.1（含已合并的记忆树）..."
git push gitee v4.1.1

OWNER_REPO="william.oschina.net/tars"
NEW_MR="https://gitee.com/${OWNER_REPO}/pulls/new?source_branch=feat%2Fv4.1.4-memory-entity-tree&target_branch=v4.1.1"

echo ""
echo "✅ 推送完成。"
echo "👉 在浏览器打开创建 Pull Request（合并请求）："
echo "   ${NEW_MR}"
echo ""
echo "合并后本地同步："
echo "   git checkout v4.1.1 && git pull gitee v4.1.1"
