#!/usr/bin/env python3
# gen_keys.py - Generate Kyber768 keypair, private key wrapped with AES256-GCM+PBKDF2
# Run ONCE: python3 gen_keys.py
# Keys stored in ~/.vault/keys/

import os
import sys
import secrets
import ctypes
import getpass
from kyber import Kyber768
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

KYBER_PRIV_FILE = os.path.expanduser("~/.vault/keys/private.kyber")
KYBER_PUB_FILE  = os.path.expanduser("~/.vault/keys/public.kyber")

backend = default_backend()

def gen_keys():
    # Safety check — don't overwrite existing keys silently
    if os.path.exists(KYBER_PRIV_FILE) or os.path.exists(KYBER_PUB_FILE):
        print("WARNING: Keys already exist at:")
        print(f"  {KYBER_PRIV_FILE}")
        print(f"  {KYBER_PUB_FILE}")
        confirm = input("Overwrite? This will make all existing .pqc files unrecoverable. [yes/NO]: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    # Get and confirm passphrase
    while True:
        passphrase_str = getpass.getpass("Enter passphrase for private key: ")
        confirm_str    = getpass.getpass("Confirm passphrase: ")
        if passphrase_str == confirm_str:
            break
        print("Passphrases do not match. Try again.\n")

    passphrase     = bytearray(passphrase_str.encode())
    passphrase_str = None
    confirm_str    = None

    print("\nGenerating Kyber768 keypair...")
    pk, sk = Kyber768.keygen()

    # Wrap private key: PBKDF2 → AES-256-GCM
    salt = secrets.token_bytes(16)
    kdf  = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=600_000, backend=backend)
    key  = kdf.derive(bytes(passphrase))
    iv   = secrets.token_bytes(12)
    cipher    = Cipher(algorithms.AES(key), modes.GCM(iv), backend=backend)
    encryptor = cipher.encryptor()
    ct  = encryptor.update(sk) + encryptor.finalize()
    tag = encryptor.tag

    # Write private key (wrapped): salt|iv|tag|ciphertext
    os.makedirs(os.path.dirname(KYBER_PRIV_FILE), exist_ok=True)
    fd = os.open(KYBER_PRIV_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(salt + iv + tag + ct)

    # Write public key (plaintext — safe to distribute)
    fd_pub = os.open(KYBER_PUB_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    with os.fdopen(fd_pub, "wb") as f:
        f.write(pk)

    # Zero sensitive buffers
    ctypes.memset((ctypes.c_char * len(passphrase)).from_buffer(passphrase), 0, len(passphrase))
    del passphrase

    print(f"\n✓ Private key (wrapped): {KYBER_PRIV_FILE}")
    print(f"✓ Public key:            {KYBER_PUB_FILE}")
    print("\nIMPORTANT: Back up your passphrase securely.")
    print("If you lose it, all encrypted files are permanently unrecoverable.")


if __name__ == "__main__":
    gen_keys()
