#!/bin/bash
set -Eeuo pipefail

echo "Starting Next.js on port 5000..."
PORT=5000 node .next/standalone/server.js
