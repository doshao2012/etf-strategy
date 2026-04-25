#!/bin/bash
set -Eeuo pipefail

PORT=5000
DEPLOY_RUN_PORT="${DEPLOY_RUN_PORT:-$PORT}"

echo "Starting Next.js on port ${DEPLOY_RUN_PORT}..."
PORT=${DEPLOY_RUN_PORT} node .next/standalone/server.js
