#!/bin/bash
set -Eeuo pipefail

PORT="${PORT:-5000}"

echo "Starting Next.js on port ${PORT}..."
PORT=${PORT} node .next/standalone/server.js
