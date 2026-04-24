#!/bin/bash
set -Eeuo pipefail

COZE_WORKSPACE_PATH="${COZE_WORKSPACE_PATH:-$(pwd)}"

PORT=5000
DEPLOY_RUN_PORT="${DEPLOY_RUN_PORT:-$PORT}"

# 清理占用端口的进程
cleanup_port() {
    local port=$1
    local pids=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "Killing processes on port $port: $pids"
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

start_service() {
    cd "${COZE_WORKSPACE_PATH}"
    
    # 清理端口
    cleanup_port 3000
    cleanup_port $DEPLOY_RUN_PORT
    
    # 启动 FastAPI 后端（端口 3000）
    echo "Starting FastAPI backend on port 3000..."
    cd server
    python3 -m uvicorn main:app --host 0.0.0.0 --port 3000 &
    cd ..
    
    # 等待后端启动
    sleep 2
    
    echo "Starting HTTP service on port ${DEPLOY_RUN_PORT} for deploy..."
    PORT=${DEPLOY_RUN_PORT} node dist/server.js
}

echo "Starting HTTP service on port ${DEPLOY_RUN_PORT} for deploy..."
start_service
