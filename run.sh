#!/usr/bin/env bash
# YOUKAI 仅启动 Web UI（不安装依赖、不克隆）
# 使用前请已安装依赖：pip install -r requirements.txt

set -e
cd "$(dirname "$0")"

if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

echo "启动 YOUKAI Web UI..."
echo "浏览器打开: http://127.0.0.1:8000"
echo ""

exec uvicorn web.app:app --host 0.0.0.0 --port 8000
