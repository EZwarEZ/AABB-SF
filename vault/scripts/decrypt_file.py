#!/usr/bin/env python3
# decrypt_file.py - PQC decryption (AES256-GCM + Kyber768)
# Usage: python3 decrypt_file.py <file.pqc> [--out-dir /path/to/dir]

import os
import sys
import struct
import hashlib
import ctypes
import getpass
import argparse
from kyber import Kyber768
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import keywrap, hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
KYBER_PRIV_FILE = os.path.expanduser("~/.vault/keys/private.kyber")

backend = default_backend()

# ── Key loading ───────────────────────────────────────────────────────────────

def load_private_key(passphrase: bytearray) -> bytearray:
    if not os.path.exists(KYBER_PRIV_FILE):
        raise FileNotFoundError(f"Private key not found: {KYBER_PRIV_FILE}\nRun: python3 gen_keys.py")
    with open(KYBER_PRIV_FILE, "rb") as f:
        wrapped = f.read()
    salt = wrapped[:16]
    iv   = wrapped[16:28]
    tag  = wrapped[28:44]
    ct   = wrapped[44:]
    kdf  = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=600_000, backend=backend)
    key  = kdf.derive(bytes(passphrase))
    cipher    = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=backend)
    decryptor = cipher.decryptor()
    return bytearray(decryptor.update(ct) + decryptor.finalize())


# ── Decryption ────────────────────────────────────────────────────────────────

def decrypt_file(pqc_path: str, out_dir: str = None) -> str:
    """
    Decrypt a .pqc file produced by encrypt_file.py.
    Restores original filename. If out_dir is None, writes alongside the .pqc file.
    """
    if not os.path.isfile(pqc_path):
        raise FileNotFoundError(f"Input file not found: {pqc_path}")
    if not pqc_path.endswith(".pqc"):
        raise ValueError("Input file must have .pqc extension")

    # Prompt passphrase securely
    passphrase_str = getpass.getpass("Passphrase for private key: ")
    passphrase     = bytearray(passphrase_str.encode())
    passphrase_str = None

    sk = load_private_key(passphrase)

    with open(pqc_path, "rb") as f:
        bundle = f.read()

    # ── Parse bundle ──────────────────────────────────────────────────────────
    pos = 0

    magic = bundle[pos:pos+4];   pos += 4
    if magic != b"PQCV":
        raise ValueError("Not a valid PQCV bundle (bad magic bytes)")

    version = bundle[pos];       pos += 1
    if version != 0x01:
        raise ValueError(f"Unsupported bundle version: {version}")

    pt_hash_stored = bundle[pos:pos+32];  pos += 32
    iv             = bundle[pos:pos+12];  pos += 12
    tag            = bundle[pos:pos+16];  pos += 16

    ct_len = struct.unpack(">I", bundle[pos:pos+4])[0];  pos += 4
    ct     = bundle[pos:pos+ct_len];                     pos += ct_len

    wdek_len   = struct.unpack(">I", bundle[pos:pos+4])[0];  pos += 4
    wrapped_dek = bundle[pos:pos+wdek_len];                  pos += wdek_len

    kyber_ct_len = struct.unpack(">I", bundle[pos:pos+4])[0];  pos += 4
    kyber_ct     = bundle[pos:pos+kyber_ct_len];               pos += kyber_ct_len

    # Original filename (null-terminated)
    null_idx  = bundle.index(b"\x00", pos)
    orig_name = bundle[pos:null_idx].decode("utf-8")

    # ── KEM decapsulate ───────────────────────────────────────────────────────
    kek = Kyber768.dec(bytes(sk), kyber_ct)
    dek = bytearray(keywrap.aes_key_unwrap_with_padding(kek, wrapped_dek, backend))

    # ── AES-GCM decrypt ───────────────────────────────────────────────────────
    cipher    = Cipher(algorithms.AES(bytes(dek)), modes.GCM(iv, tag), backend=backend)
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ct) + decryptor.finalize()

    # ── Integrity check ───────────────────────────────────────────────────────
    pt_hash_actual = hashlib.sha256(plaintext).digest()
    if pt_hash_actual != pt_hash_stored:
        raise ValueError("INTEGRITY FAILURE: plaintext hash mismatch — file may be corrupted or tampered")

    # ── Write output ──────────────────────────────────────────────────────────
    if out_dir is None:
        out_dir = os.path.dirname(os.path.abspath(pqc_path))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, orig_name)

    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(plaintext)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] DECRYPTED  {os.path.basename(pqc_path)}")
    print(f"  → {out_path}")
    print(f"  Integrity: OK (SHA-256 verified)")

    # ── Zero sensitive buffers ────────────────────────────────────────────────
    ctypes.memset((ctypes.c_char * len(dek)).from_buffer(dek), 0, len(dek))
    ctypes.memset((ctypes.c_char * len(sk)).from_buffer(sk), 0, len(sk))
    ctypes.memset((ctypes.c_char * len(passphrase)).from_buffer(passphrase), 0, len(passphrase))

    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PQC file decryptor (AES256-GCM + Kyber768)")
    parser.add_argument("input",     help=".pqc file to decrypt")
    parser.add_argument("--out-dir", default=None,
                        help="Output directory (default: same folder as .pqc file)")
    args = parser.parse_args()

    try:
        out = decrypt_file(args.input, args.out_dir)
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
