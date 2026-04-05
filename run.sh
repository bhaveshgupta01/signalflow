#!/bin/bash
# SignalFlow — one-command launcher
# Starts Boba proxy, agent, and dashboard

set -e

BOBA_BIN=$(find ~/.npm/_npx -name "boba" -path "*/bin/*" 2>/dev/null | head -1)
if [ -z "$BOBA_BIN" ]; then
    echo "Installing Boba CLI..."
    npx -y @tradeboba/cli@latest --help >/dev/null 2>&1
    BOBA_BIN=$(find ~/.npm/_npx -name "boba" -path "*/bin/*" 2>/dev/null | head -1)
fi

if [ -z "$BOBA_BIN" ]; then
    echo "ERROR: Could not find boba binary. Run: npx -y @tradeboba/cli@latest login"
    exit 1
fi

echo "Starting SignalFlow..."
echo "  Boba: $BOBA_BIN"

# Check if proxy is already running
if pgrep -f "boba proxy" > /dev/null 2>&1 || pgrep -f "boba mcp" > /dev/null 2>&1; then
    echo "  Boba proxy already running"
else
    echo "  Starting Boba proxy..."
    script -q /dev/null "$BOBA_BIN" proxy --port 3456 &
    PROXY_PID=$!
    sleep 5
    if kill -0 $PROXY_PID 2>/dev/null; then
        echo "  Boba proxy started (PID $PROXY_PID)"
    else
        echo "  WARNING: Boba proxy may not have started. Check credentials."
    fi
fi

# Find Python
PYTHON=$(which python3.13 2>/dev/null || which python3 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3 not found"
    exit 1
fi

# Start agent
echo "  Starting agent..."
PYTHONUNBUFFERED=1 $PYTHON runner.py > /tmp/signalflow_agent.log 2>&1 &
AGENT_PID=$!
echo "  Agent started (PID $AGENT_PID)"

# Wait for agent to connect
sleep 5

# Start dashboard
echo "  Starting dashboard..."
$PYTHON -m streamlit run dashboard.py --server.port 8501 --server.headless true > /tmp/signalflow_dashboard.log 2>&1 &
DASH_PID=$!
echo "  Dashboard started (PID $DASH_PID)"

echo ""
echo "========================================="
echo "  SignalFlow is LIVE"
echo "========================================="
echo "  Dashboard:  http://localhost:8501"
echo "  Agent log:  tail -f /tmp/signalflow_agent.log"
echo "  Agent PID:  $AGENT_PID"
echo "  Dash PID:   $DASH_PID"
echo ""
echo "  Press Ctrl+C to stop everything"
echo "========================================="

# Wait and cleanup on exit
trap "echo 'Stopping...'; kill $AGENT_PID $DASH_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait $AGENT_PID
