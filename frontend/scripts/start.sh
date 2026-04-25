#!/bin/sh
set -e

PORT="${PORT:-5000}"

echo "Starting Next.js on port ${PORT}..."
pnpm next start -p ${PORT}
