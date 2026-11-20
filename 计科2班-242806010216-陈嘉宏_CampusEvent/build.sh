#!/bin/sh
# 云端构建脚本：收集运行时文件到 dist/
set -eu

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$ROOT_DIR/dist"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

cp -R "$ROOT_DIR/project/src" "$DIST_DIR/src"
cp -R "$ROOT_DIR/project/public" "$DIST_DIR/public"
cp -R "$ROOT_DIR/project/vendor" "$DIST_DIR/vendor"
if [ -f "$ROOT_DIR/project/package.json" ]; then
  cp "$ROOT_DIR/project/package.json" "$DIST_DIR/package.json"
else
  cp "$ROOT_DIR/package.json" "$DIST_DIR/package.json"
fi
cp "$ROOT_DIR/run.sh" "$DIST_DIR/run.sh"
chmod 755 "$DIST_DIR/run.sh"

echo "构建完成：$DIST_DIR"
