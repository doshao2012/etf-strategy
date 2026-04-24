#!/bin/bash
set -Eeuo pipefail

COZE_WORKSPACE_PATH="${COZE_WORKSPACE_PATH:-$(pwd)}"

PORT=5000
DEPLOY_RUN_PORT="${DEPLOY_RUN_PORT:-$PORT}"

start_service() {
    cd "${COZE_WORKSPACE_PATH}"
    
    # 启动 FastAPI 后端（端口 3000）
    echo "Starting FastAPI backend on port 3000..."
    cd server
    python3 -m uvicorn main:app --host 0.0.0.0 --port 3000 &
    cd ..
    
    # 等待后端启动
    sleep 2
    
    echo "Starting Next.js on port ${DEPLOY_RUN_PORT}..."
    PORT=${DEPLOY_RUN_PORT} node .next/standalone/server.js
}

echo "Starting service on port ${DEPLOY_RUN_PORT}..."
start_service
