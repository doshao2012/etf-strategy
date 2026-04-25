#!/bin/sh
set -e

COZE_WORKSPACE_PATH="${COZE_WORKSPACE_PATH:-$(pwd)}"

cd "${COZE_WORKSPACE_PATH}"

echo "Installing dependencies..."
pnpm install --prefer-frozen-lockfile

echo "Building the Next.js project..."
pnpm next build

echo "Build completed successfully!"
