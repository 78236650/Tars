#!/usr/bin/env bash
# 下载会议助手 Whisper 模型到 backend/data/models/whisper-small（约 460MB）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
MODEL_DIR="$BACKEND/data/models/whisper-small"
PYTHON="${BACKEND}/.venv/bin/python3"

if [[ ! -x "$PYTHON" ]]; then
  echo "未找到 $PYTHON，请先创建 backend/.venv" >&2
  exit 1
fi

export HF_HUB_OFFLINE=0
export TRANSFORMERS_OFFLINE=0
# 国内可选用镜像：export HF_ENDPOINT=https://hf-mirror.com

SIZE="${1:-small}"
mkdir -p "$BACKEND/data/models"

echo "正在下载 faster-whisper 模型: $SIZE -> $MODEL_DIR"
"$PYTHON" -c "
from faster_whisper import download_model
path = download_model('$SIZE', '$MODEL_DIR')
import os
bin_path = os.path.join(path, 'model.bin')
if not os.path.isfile(bin_path):
    raise SystemExit('model.bin 未找到，下载可能不完整')
print('完成:', path)
print('model.bin 大小:', os.path.getsize(bin_path), 'bytes')
"

echo "已在 meeting.yaml 配置 model_path: data/models/whisper-small"
