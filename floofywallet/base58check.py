"""Minimal Base58Check decoder/encoder for address-format checks.

No private-key generation, signing, or network calls occur here. Parsing a
valid address does not imply it exists on the blockchain or is owned by anyone.
"""

from __future__ import annotations

import hashlib

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _checksum(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]


def encode(payload: bytes) -> str:
    if not payload:
        raise ValueError("Payload cannot be empty")
    n = int.from_bytes(payload + _checksum(payload), "big")
    chars: list[str] = []
    while n:
        n, rem = divmod(n, 58)
        chars.append(ALPHABET[rem])
    zeros = len(payload + _checksum(payload)) - len((payload + _checksum(payload)).lstrip(b"\x00"))
    return "1" * zeros + "".join(reversed(chars))


def decode(value: str) -> bytes:
    if not value or value.strip() != value:
        raise ValueError("Invalid Base58Check text")
    n = 0
    for char in value:
        if char not in ALPHABET:
            raise ValueError("Invalid Base58Check character")
        n = n * 58 + ALPHABET.index(char)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    raw = b"\x00" * (len(value) - len(value.lstrip("1"))) + raw
    if len(raw) < 5:
        raise ValueError("Base58Check value too short")
    payload, checksum = raw[:-4], raw[-4:]
    if _checksum(payload) != checksum:
        raise ValueError("Base58Check checksum mismatch")
    return payload
