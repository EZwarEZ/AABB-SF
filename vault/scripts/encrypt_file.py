#!/usr/bin/env python3
# encrypt_file.py - Per-file PQC encryption (AES256-GCM + Kyber768)
# Usage: python3 encrypt_file.py <input_file> <output_vault_dir>

import os
import sys
import secrets
import struct
import hashlib
import argparse
from datetime import datetime
from kyber import Kyber768
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import keywrap
from cryptography.hazmat.backends import default_backend

# ── Config ────────────────────────────────────────────────────────────────────
KYBER_PUB_FILE  = os.path.expanduser("~/.vault/keys/public.kyber")
VAULT_DIR       = os.path.expanduser("~/.vault/store")
KYBER_PK_LEN    = 1184   # ML-KEM-768

backend = default_backend()

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_public_key() -> bytes:
    if not os.path.exists(KYBER_PUB_FILE):
        raise FileNotFoundError(f"Public key not found: {KYBER_PUB_FILE}\nRun: python3 gen_keys.py")
    with open(KYBER_PUB_FILE, "rb") as f:
        pk = f.read()
    if len(pk) != KYBER_PK_LEN:
        raise ValueError(f"Invalid public key length {len(pk)} (expected {KYBER_PK_LEN})")
    return pk


def encrypt_file(input_path: str, vault_dir: str = VAULT_DIR) -> str:
    """
    Encrypt a single file with AES256-GCM, wrap the DEK with Kyber768 KEM.
    Output file: <vault_dir>/<original_filename>.pqc
    Bundle layout (all big-endian lengths):
        [4]  magic "PQCV"
        [1]  version = 0x01
        [32] SHA-256 of plaintext (integrity pre-check on decrypt)
        [12] AES-GCM IV
        [16] AES-GCM tag
        [4]  ciphertext length
        [N]  ciphertext
        [4]  wrapped DEK length
        [M]  AES-wrapped DEK
        [4]  Kyber ciphertext length
        [K]  Kyber ciphertext
        [len(name)+1] original filename (null-terminated UTF-8)
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    pk = load_public_key()
    os.makedirs(vault_dir, mode=0o700, exist_ok=True)

    with open(input_path, "rb") as f:
        plaintext = f.read()

    # Hash of plaintext for integrity verification on decrypt
    pt_hash = hashlib.sha256(plaintext).digest()

    # Generate DEK and encrypt plaintext
    dek = secrets.token_bytes(32)
    iv  = secrets.token_bytes(12)
    cipher    = Cipher(algorithms.AES(dek), modes.GCM(iv), backend=backend)
    encryptor = cipher.encryptor()
    ct  = encryptor.update(plaintext) + encryptor.finalize()
    tag = encryptor.tag

    # KEM: encapsulate DEK with Kyber768
    kyber_ct, kek = Kyber768.enc(pk)
    wrapped_dek   = keywrap.aes_key_wrap_with_padding(kek, dek, backend)

    # Build bundle
    orig_name = os.path.basename(input_path).encode("utf-8") + b"\x00"
    bundle = (
        b"PQCV"                                  # magic
        + b"\x01"                                # version
        + pt_hash                                # 32 bytes
        + iv                                     # 12 bytes
        + tag                                    # 16 bytes
        + struct.pack(">I", len(ct))
        + ct
        + struct.pack(">I", len(wrapped_dek))
        + wrapped_dek
        + struct.pack(">I", len(kyber_ct))
        + kyber_ct
        + orig_name
    )

    out_filename = os.path.basename(input_path) + ".pqc"
    out_path     = os.path.join(vault_dir, out_filename)

    # Write with restrictive permissions
    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(bundle)

    file_hash = hashlib.sha256(bundle).hexdigest()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ENCRYPTED  {os.path.basename(input_path)}")
    print(f"  → {out_path}")
    print(f"  SHA-256: {file_hash}")
    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PQC file encryptor (AES256-GCM + Kyber768)")
    parser.add_argument("input",  help="File to encrypt")
    parser.add_argument("--vault", default=VAULT_DIR, help=f"Vault output dir (default: {VAULT_DIR})")
    args = parser.parse_args()

    try:
        out = encrypt_file(args.input, args.vault)
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
