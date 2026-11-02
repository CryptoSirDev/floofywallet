"""Legacy FloofyChain key-to-address helpers (experimental).

These primitives do not create a wallet, store secrets, or sign transactions.
Never log or send private keys/WIFs to a remote service.
"""

from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .addresses import encode_p2pkh
from .base58check import decode, encode
from .network_params import MAINNET

SECP256K1_ORDER = int(
    "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16
)


def _check_private_key(private_key: bytes) -> int:
    if not isinstance(private_key, bytes) or len(private_key) != 32:
        raise ValueError("Private key must be exactly 32 bytes")
    value = int.from_bytes(private_key, "big")
    if not 1 <= value < SECP256K1_ORDER:
        raise ValueError("Private key is outside the secp256k1 range")
    return value


def public_key_from_private(private_key: bytes, *, compressed: bool = True) -> bytes:
    """Derive a public key using cryptography's secp256k1 implementation."""
    scalar = _check_private_key(private_key)
    public_key = ec.derive_private_key(scalar, ec.SECP256K1()).public_key()
    point_format = (
        serialization.PublicFormat.CompressedPoint
        if compressed else serialization.PublicFormat.UncompressedPoint
    )
    return public_key.public_bytes(serialization.Encoding.X962, point_format)


def address_from_public_key(public_key: bytes) -> str:
    """Return a legacy P2PKH address for a validated secp256k1 public key."""
    if not isinstance(public_key, bytes):
        raise ValueError("Public key must be bytes")
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), public_key)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid secp256k1 public key") from exc
    if len(public_key) not in (33, 65):
        raise ValueError("Unsupported public key encoding")
    digest = hashlib.new("ripemd160", hashlib.sha256(public_key).digest()).digest()
    return encode_p2pkh(digest)


def address_from_private(private_key: bytes, *, compressed: bool = True) -> str:
    return address_from_public_key(public_key_from_private(private_key, compressed=compressed))


def encode_wif(private_key: bytes, *, compressed: bool = True) -> str:
    _check_private_key(private_key)
    payload = bytes([MAINNET.wif_prefix]) + private_key + (b"\\x01" if compressed else b"")
    return encode(payload)


def decode_wif(wif: str) -> tuple[bytes, bool]:
    """Validate a mainnet WIF; return (private_key, compressed). Keep it secret."""
    payload = decode(wif)
    if not payload or payload[0] != MAINNET.wif_prefix:
        raise ValueError("Not a FloofyChain mainnet WIF")
    if len(payload) == 33:
        compressed = False
    elif len(payload) == 34 and payload[-1] == 1:
        compressed = True
    else:
        raise ValueError("Invalid WIF payload")
    key = payload[1:33]
    _check_private_key(key)
    return key, compressed
