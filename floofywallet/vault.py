"""Experimental encrypted single-key vault. Never send secrets to an explorer.

The password is not stored. This format is NOT independently security-audited.
"""
import json
import os
from pathlib import Path
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .keys import SECP256K1_ORDER, address_from_private, decode_wif, encode_wif

FORMAT = "floofywallet-vault-v1"
AAD = b"floofywallet-vault-v1"
SALT_BYTES = 16
NONCE_BYTES = 12


class VaultError(ValueError):
    """Invalid vault, password, or key."""


def _derive(password, salt):
    if not isinstance(password, str) or len(password) < 12:
        raise VaultError("Password must contain at least 12 characters")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def generate_wallet():
    """Return a random mainnet WIF and its public address."""
    key = secrets.randbelow(SECP256K1_ORDER - 1) + 1
    private = key.to_bytes(32, "big")
    return encode_wif(private), address_from_private(private)


def address_from_wif(wif):
    private, compressed = decode_wif(wif)
    return address_from_private(private, compressed=compressed)


def encrypt_wif(wif, password):
    """Produce a portable JSON-serializable encrypted vault, never plaintext WIF."""
    address = address_from_wif(wif)
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(_derive(password, salt)).encrypt(nonce, wif.encode("ascii"), AAD)
    return {
        "format": FORMAT,
        "address": address,
        "kdf": "scrypt",
        "cipher": "AES-256-GCM",
        "salt": salt.hex(),
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
    }


def decrypt_wif(vault, password):
    """Return WIF after authenticated decryption; do not log or display by default."""
    if not isinstance(vault, dict) or vault.get("format") != FORMAT or vault.get("kdf") != "scrypt" or vault.get("cipher") != "AES-256-GCM":
        raise VaultError("Unsupported vault format")
    try:
        salt = bytes.fromhex(vault["salt"])
        nonce = bytes.fromhex(vault["nonce"])
        ciphertext = bytes.fromhex(vault["ciphertext"])
        if len(salt) != SALT_BYTES or len(nonce) != NONCE_BYTES or not 40 <= len(ciphertext) <= 256:
            raise ValueError("Invalid vault lengths")
        key = _derive(password, salt)
        wif = AESGCM(key).decrypt(nonce, ciphertext, AAD).decode("ascii")
        if address_from_wif(wif) != vault["address"]:
            raise ValueError("Address mismatch")
        return wif
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise VaultError("Wrong password or damaged vault") from exc


def save_vault(path, vault):
    """Create a new vault file without overwriting an existing one."""
    path = Path(path)
    payload = json.dumps(vault, indent=2).encode("utf-8")
    # Exclusive creation avoids accidental destruction of an existing wallet.
    with path.open("xb") as file:
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())


def load_vault(path):
    path = Path(path)
    if path.stat().st_size > 4096:
        raise VaultError("Vault file too large")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise VaultError("Invalid vault file") from exc
