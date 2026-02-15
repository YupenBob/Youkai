#!/usr/bin/env bash
# YOUKAI 一条龙：克隆（可选）→ 安装依赖 → 启动 Web UI
# 用法一（已在仓库内）：./install_and_run.sh
# 用法二（从零开始）：./install_and_run.sh https://github.com/你的用户名/youkai.git

set -e
REPO_URL="${1:-}"

if [ -n "$REPO_URL" ]; then
  echo "[1/4] 正在克隆仓库..."
  DIR_NAME="${REPO_URL##*/}"
  DIR_NAME="${DIR_NAME%.git}"
  if [ -d "$DIR_NAME" ]; then
    echo "      目录 $DIR_NAME 已存在，进入并继续安装..."
    cd "$DIR_NAME"
  else
    git clone "$REPO_URL" "$DIR_NAME"
    cd "$DIR_NAME"
  fi
else
  echo "[1/4] 未传入仓库地址，假定当前目录即为项目根目录..."
  cd "$(dirname "$0")"
fi

echo "[2/4] 创建虚拟环境并安装依赖..."
python3 -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "[3/4] 依赖已就绪。"
echo "[4/4] 启动 Web UI（Ctrl+C 停止）..."
echo ""
echo "  在浏览器打开: http://127.0.0.1:8000"
echo "  首次使用请进入「设置」配置 API Key（推荐 DeepSeek），保存后即可扫描。"
echo ""

uvicorn web.app:app --host 0.0.0.0 --port 8000
