#!/bin/bash
# watcher.sh - Watch drop folder, encrypt any new file automatically
# Requires: inotify-tools (sudo apt install inotify-tools)
# Run as service or start manually: bash watcher.sh &

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
DROP_DIR="$HOME/.vault/drop"
VAULT_DIR="$HOME/.vault/store"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$HOME/.vault/logs/watcher.log"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# ── Setup ─────────────────────────────────────────────────────────────────────
mkdir -p "$DROP_DIR" "$VAULT_DIR" "$(dirname "$LOG_FILE")"
chmod 700 "$DROP_DIR" "$VAULT_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ── Dependency check ──────────────────────────────────────────────────────────
if ! command -v inotifywait &>/dev/null; then
    echo "ERROR: inotify-tools not installed."
    echo "Fix:   sudo apt install inotify-tools"
    exit 1
fi

log "Vault watcher started. Watching: $DROP_DIR"
log "Encrypted output:               $VAULT_DIR"

# ── Watch loop ────────────────────────────────────────────────────────────────
inotifywait -m -e close_write -e moved_to --format "%f" "$DROP_DIR" 2>>"$LOG_FILE" \
| while IFS= read -r filename; do

    filepath="$DROP_DIR/$filename"

    # Skip hidden files, temp files, and already encrypted files
    if [[ "$filename" == .* ]] || [[ "$filename" == *.pqc ]] || [[ "$filename" == *.tmp ]]; then
        log "SKIP  $filename (hidden/temp/already encrypted)"
        continue
    fi

    # Brief pause — ensure file is fully written before reading
    sleep 0.5

    if [[ ! -f "$filepath" ]]; then
        log "SKIP  $filename (no longer exists)"
        continue
    fi

    log "DETECTED  $filename — encrypting..."

    if "$PYTHON_BIN" "$SCRIPTS_DIR/encrypt_file.py" "$filepath" --vault "$VAULT_DIR" >> "$LOG_FILE" 2>&1; then
        log "SUCCESS   $filename → $VAULT_DIR/${filename}.pqc"
    else
        log "ERROR     Failed to encrypt $filename — see log above"
    fi

done
