#!/bin/bash
set -Eeuo pipefail

COZE_WORKSPACE_PATH="${COZE_WORKSPACE_PATH:-$(pwd)}"

cd "${COZE_WORKSPACE_PATH}"

echo "Installing dependencies..."
pnpm install --prefer-frozen-lockfile

echo "Building the Next.js project..."
pnpm next build

# 复制所有必要的文件到 standalone 输出目录
if [ -d ".next/standalone" ]; then
    cp -r .next/static .next/standalone/.next/static 2>/dev/null || true
    cp -r public .next/standalone/public 2>/dev/null || true
    
    # 如果有单独的服务文件也复制
    if [ -d ".next/server" ]; then
        cp -r .next/server .next/standalone/.next/server 2>/dev/null || true
    fi
fi

echo "Build completed successfully!"
