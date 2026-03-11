#!/bin/bash
# sync.sh - Encrypt any pending files in vault and push to GitHub
# Scheduled via cron at 4AM Central Time
# Manual run: bash sync.sh

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
VAULT_DIR="$HOME/.vault/store"
REPO_DIR="$HOME/Documents/AABB-SF"          # Your cloned repo path
VAULT_IN_REPO="$REPO_DIR/vault"             # Vault subfolder inside repo
LOG_FILE="$HOME/.vault/logs/sync.log"
GIT_BRANCH="main"

# ── Setup ─────────────────────────────────────────────────────────────────────
mkdir -p "$VAULT_IN_REPO" "$(dirname "$LOG_FILE")"
chmod 700 "$VAULT_IN_REPO"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Sync job started"

# ── Sanity checks ─────────────────────────────────────────────────────────────
if [[ ! -d "$REPO_DIR/.git" ]]; then
    log "ERROR: $REPO_DIR is not a git repository"
    exit 1
fi

if [[ ! -d "$VAULT_DIR" ]]; then
    log "ERROR: Vault directory not found: $VAULT_DIR"
    exit 1
fi

# ── Copy .pqc files from vault to repo ───────────────────────────────────────
PQC_COUNT=0
while IFS= read -r -d '' pqc_file; do
    filename=$(basename "$pqc_file")
    dest="$VAULT_IN_REPO/$filename"

    # Only copy if new or changed
    if [[ ! -f "$dest" ]] || ! cmp -s "$pqc_file" "$dest"; then
        cp "$pqc_file" "$dest"
        chmod 600 "$dest"
        log "STAGED    $filename"
        ((PQC_COUNT++)) || true
    fi
done < <(find "$VAULT_DIR" -maxdepth 1 -name "*.pqc" -print0)

if [[ $PQC_COUNT -eq 0 ]]; then
    log "No new or changed .pqc files to sync"
    log "Sync job complete (nothing to push)"
    exit 0
fi

log "$PQC_COUNT file(s) staged for commit"

# ── Git operations ────────────────────────────────────────────────────────────
cd "$REPO_DIR"

# Confirm we're on the right branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT_BRANCH" != "$GIT_BRANCH" ]]; then
    log "WARNING: On branch '$CURRENT_BRANCH', expected '$GIT_BRANCH' — switching"
    git checkout "$GIT_BRANCH" >> "$LOG_FILE" 2>&1
fi

git add vault/ >> "$LOG_FILE" 2>&1

# Only commit if there are staged changes
if git diff --cached --quiet; then
    log "No staged changes after git add (files may be identical)"
    log "Sync job complete (nothing to commit)"
    exit 0
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')
git commit -m "PQC vault sync — $TIMESTAMP [$PQC_COUNT file(s)]" >> "$LOG_FILE" 2>&1
log "Committed: PQC vault sync — $TIMESTAMP"

git push origin "$GIT_BRANCH" >> "$LOG_FILE" 2>&1
log "Pushed to origin/$GIT_BRANCH"

log "Sync job complete ✓"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
