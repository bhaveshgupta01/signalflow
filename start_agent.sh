#!/bin/bash
# Railway startup — Boba proxy + trading agent
# Dashboard runs separately on Vercel.
set -e

echo "=== SignalFlow Agent ==="
echo "Starting at $(date -u)"

# Validate Supabase connection
python -c "from db import init_db; init_db(); print('Supabase connected')"

# Start Boba MCP proxy in background
echo "Starting Boba proxy on port 3456..."
npx -y @tradeboba/cli@latest proxy --port 3456 &
BOBA_PID=$!

# Wait for proxy to become healthy (max 60s)
echo "Waiting for Boba proxy..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:3456/health > /dev/null 2>&1; then
    echo "Boba proxy ready (attempt $i)"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Boba proxy failed to start after 60s"
    exit 1
  fi
  sleep 2
done

# Run agent in foreground (Railway needs one foreground process)
echo "Starting trading agent..."
exec python -u runner.py
