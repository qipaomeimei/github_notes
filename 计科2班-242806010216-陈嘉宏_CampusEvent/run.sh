#!/bin/sh
# 云端启动脚本：在 dist/ 目录内执行，监听平台注入的 PORT
set -eu

cd "$(dirname "$0")"
PORT="${PORT:-8000}"
export PORT
export HOST="0.0.0.0"
exec node src/server.js
