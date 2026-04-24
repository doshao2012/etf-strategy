#!/bin/bash
set -Eeuo pipefail

COZE_WORKSPACE_PATH="${COZE_WORKSPACE_PATH:-$(pwd)}"

PORT=5000
DEPLOY_RUN_PORT="${DEPLOY_RUN_PORT:-$PORT}"

# 使用 fuser 清理端口（psmisc 包提供）
cleanup_port() {
    local port=$1
    echo "Checking port $port..."
    # 使用 fuser 杀死占用端口的进程
    fuser -k $port/tcp 2>/dev/null || true
    sleep 1
}

start_service() {
    cd "${COZE_WORKSPACE_PATH}"
    
    # 清理端口
    cleanup_port 3000
    
    # 启动 FastAPI 后端（端口 3000）
    echo "Starting FastAPI backend on port 3000..."
    cd server
    python3 -m uvicorn main:app --host 0.0.0.0 --port 3000 &
    cd ..
    
    # 等待后端启动
    sleep 3
    
    echo "Starting HTTP service on port ${DEPLOY_RUN_PORT} for deploy..."
    PORT=${DEPLOY_RUN_PORT} node dist/server.js
}

echo "Starting HTTP service on port ${DEPLOY_RUN_PORT} for deploy..."
start_service
