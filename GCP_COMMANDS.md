# SignalFlow — GCP Deployment Commands

**VM:** `signalflow` | **Zone:** `us-central1-a` | **IP:** changes on restart — run `gcloud compute instances describe signalflow --zone=us-central1-a --format='get(networkInterfaces[0].accessConfigs[0].natIP)'`
**Dashboard:** http://<VM_IP>:8501

---

## SSH into the VM

```bash
gcloud compute ssh signalflow --zone=us-central1-a
```

---

## Agent Controls

```bash
# Check agent status
gcloud compute ssh signalflow --zone=us-central1-a --command='pgrep -a -f runner.py'

# View live agent logs
gcloud compute ssh signalflow --zone=us-central1-a --command='tail -50 /tmp/agent.log'

# Stream agent logs (Ctrl+C to stop)
gcloud compute ssh signalflow --zone=us-central1-a -- tail -f /tmp/agent.log

# Restart agent via systemd
gcloud compute ssh signalflow --zone=us-central1-a --command='sudo systemctl restart signalflow'

# Stop agent
gcloud compute ssh signalflow --zone=us-central1-a --command='sudo systemctl stop signalflow'

# Start agent
gcloud compute ssh signalflow --zone=us-central1-a --command='sudo systemctl start signalflow'

# Check systemd service status
gcloud compute ssh signalflow --zone=us-central1-a --command='sudo systemctl status signalflow'

# View systemd logs
gcloud compute ssh signalflow --zone=us-central1-a --command='journalctl -u signalflow --no-pager -n 50'
```

---

## Dashboard Controls

```bash
# Check dashboard status
gcloud compute ssh signalflow --zone=us-central1-a --command='pgrep -a -f streamlit'

# View dashboard logs
gcloud compute ssh signalflow --zone=us-central1-a --command='tail -20 /tmp/dash.log'

# Restart dashboard
gcloud compute ssh signalflow --zone=us-central1-a --command='pkill -f streamlit; sleep 2; cd ~/signalflow && nohup python3 -m streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true > /tmp/dash.log 2>&1 &'
```

---

## Boba Proxy Controls

```bash
# Check proxy status
gcloud compute ssh signalflow --zone=us-central1-a --command='curl -s http://localhost:3456/health'

# Check proxy process
gcloud compute ssh signalflow --zone=us-central1-a --command='pgrep -a -f "boba proxy"'

# Restart proxy (requires dbus + keyring)
gcloud compute ssh signalflow --zone=us-central1-a --command='
pkill -f "boba proxy"; sleep 2
eval $(dbus-launch --sh-syntax)
echo "" | gnome-keyring-daemon --unlock --components=secrets 2>/dev/null
tmux kill-session -t boba 2>/dev/null
export BOBA_AGENT_SECRET="boba_f9e4915aa5db1ce34dfa93c944661dcb81934dc7bac1c9a8ff7a392e346c8222"
tmux new-session -d -s boba "BOBA_AGENT_SECRET=$BOBA_AGENT_SECRET boba proxy --port 3456"
sleep 8 && curl -s http://localhost:3456/health
'
```

---

## Full Restart (everything)

```bash
gcloud compute ssh signalflow --zone=us-central1-a --command='
export BOBA_AGENT_SECRET="boba_f9e4915aa5db1ce34dfa93c944661dcb81934dc7bac1c9a8ff7a392e346c8222"
export PATH=$PATH:$HOME/.local/bin

# Kill everything
pkill -f boba; pkill -f runner.py; pkill -f streamlit; sleep 2

# Start dbus + keyring
eval $(dbus-launch --sh-syntax)
echo "" | gnome-keyring-daemon --unlock --components=secrets 2>/dev/null

# Start proxy
tmux new-session -d -s boba "BOBA_AGENT_SECRET=$BOBA_AGENT_SECRET boba proxy --port 3456"
sleep 8

# Start agent
cd ~/signalflow
PYTHONUNBUFFERED=1 nohup python3 runner.py > /tmp/agent.log 2>&1 &
sleep 10

# Start dashboard
nohup python3 -m streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true > /tmp/dash.log 2>&1 &
sleep 3

# Verify
echo "Proxy:     $(curl -s http://localhost:3456/health | python3 -c \"import sys,json; print(json.load(sys.stdin)[\\\"status\\\"])\" 2>/dev/null || echo FAILED)"
echo "Agent:     $(pgrep -f runner.py > /dev/null && echo OK || echo FAILED)"
echo "Dashboard: $(pgrep -f streamlit > /dev/null && echo OK || echo FAILED)"
echo "URL:       http://34.63.228.68:8501"
'
```

---

## VM Power Controls (billing)

```bash
# Stop VM (stops billing for compute, disk still billed ~$0.80/mo)
gcloud compute instances stop signalflow --zone=us-central1-a

# Start VM
gcloud compute instances start signalflow --zone=us-central1-a

# Check VM status
gcloud compute instances describe signalflow --zone=us-central1-a --format='get(status)'

# Get external IP (changes after stop/start)
gcloud compute instances describe signalflow --zone=us-central1-a --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

---

## Delete Everything (stop all billing)

```bash
# Delete VM completely
gcloud compute instances delete signalflow --zone=us-central1-a

# Delete firewall rule
gcloud compute firewall-rules delete allow-streamlit
```

---

## Update Code on VM

```bash
# From your local machine (in the signalflow directory):
cd ~/signalflow

# Create tarball
tar czf /tmp/signalflow.tar.gz --exclude='.git' --exclude='__pycache__' --exclude='signalflow.db*' --exclude='.env' --exclude='node_modules' .

# Upload
gcloud compute scp /tmp/signalflow.tar.gz signalflow:~/signalflow.tar.gz --zone=us-central1-a

# Extract and restart on VM
gcloud compute ssh signalflow --zone=us-central1-a --command='
cd ~/signalflow && tar xzf ~/signalflow.tar.gz
sudo systemctl restart signalflow
sleep 5 && head -5 /tmp/agent.log
'
```

---

## DB Inspection

```bash
# Check trade count and P&L
gcloud compute ssh signalflow --zone=us-central1-a --command='
cd ~/signalflow && python3 -c "
import sys; sys.path.insert(0,\".\")
from db import init_db, get_stats, get_open_positions, get_all_positions
from config import PAPER_WALLET_STARTING_BALANCE
from models import PositionStatus
init_db()
s = get_stats()
p = get_all_positions(limit=200)
o = get_open_positions()
c = [x for x in p if x.status != PositionStatus.OPEN]
w = [x for x in c if x.pnl > 0]
bal = PAPER_WALLET_STARTING_BALANCE + s[\"total_pnl\"]
print(f\"Balance:  \${bal:.2f}\")
print(f\"PnL:      \${s[\"total_pnl\"]:+.2f}\")
print(f\"Trades:   {len(p)} ({len(o)} open, {len(c)} closed)\")
print(f\"Win rate: {len(w)/len(c)*100:.0f}%\" if c else \"Win rate: N/A\")
for x in p[:10]:
    print(f\"  #{x.id} {x.direction.value:5s} {x.asset:4s} \${x.size_usd:.0f} pnl=\${x.pnl:+.2f} [{x.status.value}]\")
"
'

# Reset database (fresh start)
gcloud compute ssh signalflow --zone=us-central1-a --command='
cd ~/signalflow
sudo systemctl stop signalflow
rm -f signalflow.db
python3 -c "import sys; sys.path.insert(0,\".\"); from db import init_db; init_db(); print(\"Fresh DB created\")"
sudo systemctl start signalflow
'
```

---

## Costs

| Resource | Cost |
|----------|------|
| e2-small VM (running) | ~$13/month |
| e2-small VM (stopped) | $0 compute, ~$0.80/month disk |
| Network egress | minimal |
| **Total while running** | **~$13-14/month** |
| **Total while stopped** | **~$0.80/month** |
