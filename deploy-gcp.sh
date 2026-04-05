#!/bin/bash
# Deploy SignalFlow to Google Cloud Compute Engine
# Uses your existing GCP project and credits
#
# Prerequisites:
#   1. gcloud CLI installed: https://cloud.google.com/sdk/docs/install
#   2. Authenticated: gcloud auth login
#   3. Project set: gcloud config set project YOUR_PROJECT_ID
#
# Usage:
#   ./deploy-gcp.sh

set -e

# ── Config ──
PROJECT_ID=$(gcloud config get project 2>/dev/null)
ZONE="us-central1-a"
INSTANCE_NAME="signalflow"
MACHINE_TYPE="e2-small"  # 2 vCPU, 2GB RAM — ~$13/month, covered by credits

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "Deploying SignalFlow to GCP..."
echo "  Project:  $PROJECT_ID"
echo "  Zone:     $ZONE"
echo "  Machine:  $MACHINE_TYPE"
echo ""

# ── Step 1: Enable APIs ──
echo "1. Enabling APIs..."
gcloud services enable compute.googleapis.com artifactregistry.googleapis.com --quiet

# ── Step 2: Create the VM ──
echo "2. Creating VM..."
gcloud compute instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=20GB \
    --tags=http-server \
    --metadata=startup-script='#!/bin/bash
    # This runs on first boot
    apt-get update
    apt-get install -y python3-pip python3-venv nodejs npm docker.io docker-compose-v2
    systemctl enable docker
    systemctl start docker
    ' \
    2>/dev/null || echo "  VM may already exist, continuing..."

# ── Step 3: Open firewall for Streamlit ──
echo "3. Opening port 8501..."
gcloud compute firewall-rules create allow-streamlit \
    --allow=tcp:8501 \
    --target-tags=http-server \
    --description="Allow Streamlit dashboard" \
    2>/dev/null || echo "  Firewall rule may already exist, continuing..."

# ── Step 4: Copy project files ──
echo "4. Uploading project..."
# Create a tarball excluding unnecessary files
tar czf /tmp/signalflow.tar.gz \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='signalflow.db*' \
    --exclude='.env' \
    --exclude='node_modules' \
    -C "$(dirname "$0")" .

gcloud compute scp /tmp/signalflow.tar.gz $INSTANCE_NAME:~/signalflow.tar.gz --zone=$ZONE

# ── Step 5: Setup and run on VM ──
echo "5. Setting up on VM..."
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='
    mkdir -p ~/signalflow && cd ~/signalflow
    tar xzf ~/signalflow.tar.gz

    # Install Python deps
    pip3 install google-genai mcp pydantic streamlit streamlit-autorefresh python-dotenv pandas plotly 2>/dev/null

    # Install Boba CLI
    npm install -g @tradeboba/cli@latest 2>/dev/null || true

    echo ""
    echo "Setup complete. Now:"
    echo "  1. SSH in:    gcloud compute ssh signalflow --zone=us-central1-a"
    echo "  2. Add .env:  cd ~/signalflow && nano .env"
    echo "  3. Login:     boba login"
    echo "  4. Run:       cd ~/signalflow && ./start.sh"
'

# Get the external IP
EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "========================================="
echo "  VM CREATED: $INSTANCE_NAME"
echo "========================================="
echo ""
echo "  IP: $EXTERNAL_IP"
echo "  Dashboard will be at: http://$EXTERNAL_IP:8501"
echo ""
echo "  Next steps:"
echo "  1. SSH into the VM:"
echo "     gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo ""
echo "  2. Create your .env file:"
echo "     cd ~/signalflow"
echo "     cat > .env << 'ENVEOF'"
echo "     GEMINI_API_KEY=your-key"
echo "     BOBA_API_KEY=your-boba-key"
echo "     GCP_PROJECT=$PROJECT_ID"
echo "     GCP_LOCATION=us-central1"
echo "     USE_VERTEX=true"
echo "     ENVEOF"
echo ""
echo "  3. Login to Boba:"
echo "     npx @tradeboba/cli@latest login"
echo ""
echo "  4. Start SignalFlow:"
echo "     cd ~/signalflow && nohup ./start.sh > signalflow.log 2>&1 &"
echo ""
echo "  5. Open dashboard:"
echo "     http://$EXTERNAL_IP:8501"
echo "========================================="
