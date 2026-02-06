#!/usr/bin/env bash
set -euo pipefail

# Usage:
# ./deploy/deploy_vps.sh <user@host> <remote_app_dir> [ssh_key] [server_name]
# Example:
# ./deploy/deploy_vps.sh root@1.2.3.4 /opt/119wizard ~/.ssh/id_rsa api.example.com

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <user@host> <remote_app_dir> [ssh_key] [server_name]"
  exit 1
fi

LOCAL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$1"
REMOTE_DIR="$2"
SSH_KEY="${3:-}"
SERVER_NAME="${4:-_}"

SSH_OPTS="-o StrictHostKeyChecking=accept-new"
if [[ -n "$SSH_KEY" ]]; then
  SSH_OPTS="$SSH_OPTS -i $SSH_KEY"
fi

echo "[1/6] Sync project to VPS: $TARGET:$REMOTE_DIR"
if ssh $SSH_OPTS "$TARGET" "command -v rsync >/dev/null 2>&1"; then
  rsync -az --delete \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '.DS_Store' \
    --exclude 'venv' \
    --exclude '*.pyc' \
    -e "ssh $SSH_OPTS" \
    "$LOCAL_ROOT/" "$TARGET:$REMOTE_DIR/"
else
  echo "Remote rsync not found, fallback to tar+ssh sync"
  ssh $SSH_OPTS "$TARGET" "mkdir -p '$REMOTE_DIR'"
  tar -C "$LOCAL_ROOT" -czf - \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.DS_Store' \
    --exclude='venv' \
    --exclude='*.pyc' \
    . | ssh $SSH_OPTS "$TARGET" "tar -xzf - -C '$REMOTE_DIR'"
fi

echo "[1.5/6] Verify deployment files"
ssh $SSH_OPTS "$TARGET" "test -f '$REMOTE_DIR/deploy/119wizard.service' && test -f '$REMOTE_DIR/requirements.txt'"

echo "[2/6] Install runtime packages"
ssh $SSH_OPTS "$TARGET" "bash -lc '
set -e
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip nginx
elif command -v yum >/dev/null 2>&1; then
  sudo yum install -y python3 python3-pip nginx
else
  echo Unsupported package manager
  exit 1
fi
'"

echo "[3/6] Create venv and install python deps"
ssh $SSH_OPTS "$TARGET" "bash -lc '
set -e
cd $REMOTE_DIR
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt gunicorn
'"

echo "[4/6] Install systemd service"
ssh $SSH_OPTS "$TARGET" "bash -lc '
set -e
APP_USER=\$(whoami)
TMP_SERVICE=/tmp/119wizard.service
sed -e "s#__APP_USER__#\$APP_USER#g" -e "s#__APP_DIR__#$REMOTE_DIR#g" $REMOTE_DIR/deploy/119wizard.service > \$TMP_SERVICE
sudo cp \$TMP_SERVICE /etc/systemd/system/119wizard.service
sudo systemctl daemon-reload
sudo systemctl enable 119wizard
sudo systemctl restart 119wizard
sudo systemctl --no-pager --full status 119wizard | head -n 30
'"

echo "[5/6] Configure nginx"
ssh $SSH_OPTS "$TARGET" "bash -lc '
set -e
TMP_NGINX=/tmp/119wizard.nginx.conf
sed -e "s#__SERVER_NAME__#$SERVER_NAME#g" $REMOTE_DIR/deploy/nginx.119wizard.conf > \$TMP_NGINX
# Debian/Ubuntu style: sites-available + sites-enabled
if [[ -d /etc/nginx/sites-available && -d /etc/nginx/sites-enabled ]]; then
  sudo cp \$TMP_NGINX /etc/nginx/sites-available/119wizard.conf
  sudo ln -sf /etc/nginx/sites-available/119wizard.conf /etc/nginx/sites-enabled/119wizard.conf
  if [[ -f /etc/nginx/conf.d/119wizard.conf ]]; then
    sudo rm -f /etc/nginx/conf.d/119wizard.conf
  fi
else
  # RHEL/CentOS style: conf.d
  sudo mkdir -p /etc/nginx/conf.d
  sudo cp \$TMP_NGINX /etc/nginx/conf.d/119wizard.conf
  if [[ -L /etc/nginx/sites-enabled/119wizard.conf ]]; then
    sudo rm -f /etc/nginx/sites-enabled/119wizard.conf
  fi
fi
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
'"

echo "[6/6] Done"
echo "Service URL: http://$SERVER_NAME"
echo "If SERVER_NAME is '_', use your VPS IP directly."
