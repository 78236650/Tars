#!/bin/bash
# 双击运行（macOS）：在系统终端启动测试数据库
cd "$(dirname "$0")"
chmod +x scripts/*.sh
export DOCKER_HOST=unix:///Users/daobanxiang/.docker/run/docker.sock

echo "=========================================="
echo " InsightForge 测试库启动"
echo " 请确保 Docker Desktop 已打开且为 Running"
echo "=========================================="

if ! docker info >/dev/null 2>&1; then
  echo ""
  echo "[错误] 无法连接 Docker。"
  echo "  1. 打开「Docker Desktop」并等待引擎启动"
  echo "  2. 若仍失败，在终端执行: ls -la ~/.docker/run/docker.sock"
  echo "  3. Cursor 内置终端可能报 permission denied，请用本脚本或系统终端"
  echo ""
  read -p "按回车退出..."
  exit 1
fi

./scripts/up.sh
echo ""
read -p "完成。按回车关闭窗口..."
