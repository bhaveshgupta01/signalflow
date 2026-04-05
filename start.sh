#!/bin/bash
# Production start script — runs agent + dashboard in one container
# Used by Railway / Docker / any hosting platform

set -e

echo "SignalFlow starting..."

# Initialize database
python -c "import sys; sys.path.insert(0,'.'); from db import init_db; init_db(); print('DB initialized')"

# Start the agent in background
echo "Starting agent..."
PYTHONUNBUFFERED=1 python runner.py &
AGENT_PID=$!
echo "Agent PID: $AGENT_PID"

# Give agent a few seconds to connect
sleep 5

# Start dashboard in foreground (Railway needs one foreground process)
echo "Starting dashboard on port ${PORT:-8501}..."
exec streamlit run dashboard.py \
    --server.port="${PORT:-8501}" \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
