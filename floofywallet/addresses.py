"""Legacy FloofyChain mainnet address format helpers.

This validation verifies Base58Check and network prefix only; it cannot tell
whether an address belongs to the intended recipient.
"""

from .base58check import decode, encode
from .network_params import MAINNET


def encode_p2pkh(pubkey_hash: bytes) -> str:
    if len(pubkey_hash) != 20:
        raise ValueError("P2PKH public-key hash must be 20 bytes")
    return encode(bytes([MAINNET.p2pkh_prefix]) + pubkey_hash)


def validate_address(address: str) -> bool:
    try:
        payload = decode(address)
    except (ValueError, TypeError):
        return False
    if len(payload) != 21:
        return False
    return payload[0] in (MAINNET.p2pkh_prefix, MAINNET.p2sh_prefix)
