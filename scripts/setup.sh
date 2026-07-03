#!/usr/bin/env bash
# 开发环境安装（Mac mini / 任何开发机）
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 拉取 OpenMontage 子模块"
git submodule update --init --recursive

echo "==> Python 依赖"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

echo "==> OpenMontage 依赖（需要 ffmpeg、Node 18+）"
command -v ffmpeg >/dev/null || echo "!! 请先安装 ffmpeg: brew install ffmpeg"
command -v node >/dev/null || echo "!! 请先安装 Node.js 18+"
if [ -d openmontage ]; then
  pip install -r openmontage/requirements.txt
  (cd openmontage/remotion-composer && npm install)
fi

echo "==> 完成。运行 pytest tests/ 验证。"
