#!/bin/bash
# install.sh - One-shot setup for AABB-SF PQC vault system
# Run once: bash install.sh
# Then: python3 gen_keys.py

set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_BASE="$HOME/.vault"
LOG_FILE="$VAULT_BASE/logs/install.log"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
fail() { echo -e "${RED}✗${NC}  $*"; exit 1; }
step() { echo -e "\n${YELLOW}──${NC} $*"; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   AABB-SF PQC Vault Installer            ║"
echo "║   AES256-GCM + Kyber768 File Encryption  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

mkdir -p "$VAULT_BASE/logs"
exec > >(tee -a "$LOG_FILE") 2>&1

# ── Step 1: Create directory structure ───────────────────────────────────────
step "Creating vault directory structure"
mkdir -p \
    "$VAULT_BASE/drop" \
    "$VAULT_BASE/store" \
    "$VAULT_BASE/keys" \
    "$VAULT_BASE/logs"
chmod 700 "$VAULT_BASE" "$VAULT_BASE/drop" "$VAULT_BASE/store" "$VAULT_BASE/keys"
chmod 755 "$VAULT_BASE/logs"
ok "Vault directories: $VAULT_BASE"

# ── Step 2: System dependencies ──────────────────────────────────────────────
step "Checking system dependencies"

if ! command -v inotifywait &>/dev/null; then
    warn "inotify-tools not found — installing..."
    sudo apt-get install -y inotify-tools
    ok "inotify-tools installed"
else
    ok "inotify-tools already installed"
fi

if ! command -v git &>/dev/null; then
    warn "git not found — installing..."
    sudo apt-get install -y git
    ok "git installed"
else
    ok "git already installed"
fi

# ── Step 3: Python dependencies ───────────────────────────────────────────────
step "Installing Python dependencies"

if ! python3 -c "import kyber" 2>/dev/null; then
    warn "kyber-py not found — installing..."
    pip3 install kyber-py --break-system-packages
    ok "kyber-py installed"
else
    ok "kyber-py already installed"
fi

if ! python3 -c "from cryptography.hazmat.primitives.ciphers import Cipher" 2>/dev/null; then
    warn "cryptography not found — installing..."
    pip3 install cryptography --break-system-packages
    ok "cryptography installed"
else
    ok "cryptography already installed"
fi

# ── Step 4: Make scripts executable ──────────────────────────────────────────
step "Setting script permissions"
chmod +x "$SCRIPTS_DIR/encrypt_file.py"
chmod +x "$SCRIPTS_DIR/decrypt_file.py"
chmod +x "$SCRIPTS_DIR/gen_keys.py"
chmod +x "$SCRIPTS_DIR/watcher.sh"
chmod +x "$SCRIPTS_DIR/sync.sh"
ok "All scripts executable"

# ── Step 5: Install systemd service for watcher ──────────────────────────────
step "Installing vault-watcher systemd service"

SERVICE_FILE="$HOME/.config/systemd/user/vault-watcher.service"
mkdir -p "$(dirname "$SERVICE_FILE")"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=AABB-SF PQC Vault File Watcher
After=network.target

[Service]
Type=simple
ExecStart=/bin/bash $SCRIPTS_DIR/watcher.sh
Restart=on-failure
RestartSec=5
StandardOutput=append:$VAULT_BASE/logs/watcher.log
StandardError=append:$VAULT_BASE/logs/watcher.log

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable vault-watcher.service
systemctl --user start vault-watcher.service
ok "vault-watcher service installed and started"

# ── Step 6: Install cron job for 4AM Central sync ────────────────────────────
step "Installing 4AM Central cron job"

# 4AM Central = 10:00 UTC (CDT, UTC-5 in winter = 09:00 UTC)
# Using 09:00 UTC which covers CST (UTC-6 → 3AM) / CDT (UTC-5 → 4AM)
# Adjust if needed: CST=10:00 UTC, CDT=09:00 UTC
CRON_LINE="0 9 * * * /bin/bash $SCRIPTS_DIR/sync.sh >> $VAULT_BASE/logs/sync.log 2>&1"

# Add only if not already present
(crontab -l 2>/dev/null | grep -v "sync.sh"; echo "$CRON_LINE") | crontab -
ok "Cron job installed: 4AM Central daily sync"

# ── Step 7: Git config check ──────────────────────────────────────────────────
step "Checking git configuration"
REPO_DIR="$HOME/Documents/AABB-SF"
if [[ -d "$REPO_DIR/.git" ]]; then
    ok "Git repo found: $REPO_DIR"
else
    warn "Git repo not found at $REPO_DIR"
    warn "Update REPO_DIR in sync.sh after cloning your repo"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Installation Complete                                       ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  NEXT STEP (required):                                       ║"
echo "║    python3 $SCRIPTS_DIR/gen_keys.py"
echo "║                                                              ║"
echo "║  Drop files here to auto-encrypt:                           ║"
echo "║    $VAULT_BASE/drop/                            "
echo "║                                                              ║"
echo "║  Encrypted .pqc files stored here:                          ║"
echo "║    $VAULT_BASE/store/                           "
echo "║                                                              ║"
echo "║  To decrypt a file manually:                                 ║"
echo "║    python3 decrypt_file.py <file.pqc>                       ║"
echo "║                                                              ║"
echo "║  GitHub sync: daily at 4AM Central (cron)                   ║"
echo "║  Watcher service: systemctl --user status vault-watcher     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
