#!/bin/bash
set -Eeuo pipefail

PORT="${PORT:-5000}"
DEPLOY_RUN_PORT="${DEPLOY_RUN_PORT:-$PORT}"

echo "Starting Next.js on port ${PORT}..."
node .next/standalone/server.js
