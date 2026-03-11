# AABB-SF PQC Vault System
## AES-256-GCM + Kyber768 Post-Quantum File Encryption

---

## Architecture

```
~/.vault/drop/          ← DROP FILES HERE (auto-encrypted on arrival)
       ↓  watcher.sh (inotifywait)
~/.vault/store/         ← VAULT (only .pqc encrypted files)
       ↓  sync.sh (cron 4AM Central)
GitHub: EZwarEZ/AABB-SF/vault/
```

---

## First-Time Setup

### 1. Run the installer
```bash
bash install.sh
```

### 2. Generate your Kyber keys (run once — keep passphrase safe)
```bash
python3 gen_keys.py
```

### 3. Verify the watcher is running
```bash
systemctl --user status vault-watcher
```

---

## Daily Use

### Encrypt a file (automatic)
Drop any file into `~/.vault/drop/` — it encrypts automatically within 1 second.
Original file is kept in drop folder. Encrypted `.pqc` appears in `~/.vault/store/`.

### Encrypt a file (manual)
```bash
python3 encrypt_file.py /path/to/yourfile.pdf
```

### Decrypt a file
```bash
python3 decrypt_file.py ~/.vault/store/yourfile.pdf.pqc
```
You will be prompted for your passphrase. The decrypted file appears alongside the `.pqc` file.

### Force a GitHub sync now (don't wait for 4AM)
```bash
bash sync.sh
```

---

## File Structure

| Path | Purpose |
|------|---------|
| `~/.vault/keys/private.kyber` | AES-wrapped Kyber768 private key (chmod 600) |
| `~/.vault/keys/public.kyber` | Kyber768 public key (used for encryption) |
| `~/.vault/drop/` | Watch folder — drop files here |
| `~/.vault/store/` | Encrypted vault — .pqc files only |
| `~/.vault/logs/watcher.log` | Watcher activity log |
| `~/.vault/logs/sync.log` | GitHub sync log |

---

## Encryption Details

| Layer | Algorithm | Purpose |
|-------|-----------|---------|
| Symmetric | AES-256-GCM | File encryption with authentication tag |
| KEM | Kyber768 (ML-KEM) | Encapsulate the AES data encryption key |
| Key wrap | AES Key Wrap w/ Padding | Protect DEK inside bundle |
| Private key protection | PBKDF2-SHA256 (600,000 iter) + AES-256-GCM | Passphrase-protect private key at rest |
| Integrity | SHA-256 of plaintext (stored in bundle) | Verified on every decryption |

NIST compliance: Kyber768 = ML-KEM-768 per FIPS 203. Resistant to harvest-now-decrypt-later attacks.

---

## Bundle Format (.pqc files)

```
[4]   Magic: "PQCV"
[1]   Version: 0x01
[32]  SHA-256 of original plaintext
[12]  AES-GCM IV
[16]  AES-GCM authentication tag
[4]   Ciphertext length
[N]   Ciphertext
[4]   Wrapped DEK length
[M]   AES-wrapped Data Encryption Key
[4]   Kyber ciphertext length
[K]   Kyber768 ciphertext
[?]   Original filename (null-terminated UTF-8)
```

---

## Logs

```bash
# Watch watcher activity live
tail -f ~/.vault/logs/watcher.log

# Watch sync activity live
tail -f ~/.vault/logs/sync.log
```

---

## Troubleshooting

**Watcher not running:**
```bash
systemctl --user restart vault-watcher
systemctl --user status vault-watcher
```

**GitHub push failing:**
```bash
# Verify git credentials
cd ~/Documents/AABB-SF && git push origin main
```

**Decryption fails with integrity error:**
File may be corrupted or tampered. Do not trust its contents.

---

## Security Notes

- Never commit `~/.vault/keys/` to GitHub — keys stay local only
- Private key is AES-256-GCM encrypted with your passphrase — passphrase is never stored
- If passphrase is lost, encrypted files are permanently unrecoverable — back it up offline
- GitHub receives only `.pqc` bundles — plaintext never leaves your machine
