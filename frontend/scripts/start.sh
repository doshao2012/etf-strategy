#!/bin/bash
set -Eeuo pipefail

echo "Starting Next.js on 0.0.0.0:5000..."
HOSTNAME=0.0.0.0 PORT=5000 node .next/standalone/server.js
